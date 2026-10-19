"""
Niveau 1 : carreaux Filosofi 200 m de toute la France -> data/processed/national/cells/<dep>.parquet

Sans lire les polygones : le centroïde se déduit de l'identifiant INSEE
(« CRS3035RES200mN2029400E4259000 » = coin sud-ouest dans le CRS indiqué ; centroïde = +100 m).
Pour chaque département (traitement séquentiel, mémoire bornée) :
  - commune et IRIS = polygone ADMIN EXPRESS / IRIS contenant le centroïde (à défaut : 1re commune de lcog_geo) ;
  - pop_calee = ind × population communale (recensement, ADMIN EXPRESS) / Σ ind de la commune ;
  - part de ménages sans voiture : IRIS, puis commune (mêmes règles que pour Grenoble).
"""
from __future__ import annotations

import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer

from src.ingest.archives import filosofi_gpkg, ign_gpkg
from src.ingest.population import logement_tables, part_sans_voiture
from src.national.common import FILOSOFI_FILES, TERRITORIES, national, save_stages, stage

COLS = ["idcar_200m", "lcog_geo", "i_est_200", "ind", "men", "men_pauv", "men_prop", "ind_snv", "log_soc", "ind_18_24"]
ID_RE = r"CRS(?P<crs>\d+)RES200mN(?P<n>\d+)E(?P<e>\d+)"


def centroids_from_id(ids: pd.Series, target_epsg: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(x, y) dans target_epsg et (lon, lat) WGS84 du centroïde de chaque carreau, à partir de l'identifiant."""
    p = ids.str.extract(ID_RE)
    src = int(p["crs"].iloc[0])
    if (p["crs"] != str(src)).any():
        raise ValueError("identifiants de carreaux dans plusieurs CRS")
    e = p["e"].astype(float).to_numpy() + 100
    n = p["n"].astype(float).to_numpy() + 100
    x, y = Transformer.from_crs(src, target_epsg, always_xy=True).transform(e, n) if src != target_epsg else (e, n)
    lon, lat = Transformer.from_crs(src, 4326, always_xy=True).transform(e, n)
    return np.asarray(x), np.asarray(y), np.asarray(lon), np.asarray(lat)


def load_filosofi(territory: str) -> pd.DataFrame:
    df = pyogrio.read_dataframe(filosofi_gpkg(FILOSOFI_FILES[territory]), columns=COLS, read_geometry=False)
    x, y, lon, lat = centroids_from_id(df["idcar_200m"], TERRITORIES[territory])
    df = df.assign(territoire=territory, x=x, y=y, lon=lon, lat=lat)
    df["dep_indice"] = df["lcog_geo"].str[:2].where(~df["lcog_geo"].str.startswith("97"), df["lcog_geo"].str[:3])
    return df


def assign_polygons(cells: pd.DataFrame, polys: gpd.GeoDataFrame, key: str, crs: int) -> pd.Series:
    """Code `key` du polygone contenant le centroïde de chaque carreau (NaN sinon)."""
    pts = gpd.GeoDataFrame(index=cells.index, geometry=gpd.points_from_xy(cells["x"], cells["y"]), crs=crs)
    j = gpd.sjoin(pts, polys[[key, "geometry"]].to_crs(crs), how="left", predicate="within")
    return j[~j.index.duplicated()][key].reindex(cells.index)


def build_cells() -> dict:
    out_dir = national("cells")
    out_dir.mkdir(parents=True, exist_ok=True)
    ade, iris_gpkg = ign_gpkg("admin_express"), ign_gpkg("iris")
    with stage("logement (motorisation) France"):
        iris_tab, com_tab = logement_tables()
        v_iris = part_sans_voiture(iris_tab).set_axis(iris_tab["code_iris"])
        v_com = part_sans_voiture(com_tab).set_axis(com_tab["code_insee"])
    with stage("départements ADMIN EXPRESS"):
        deps = pyogrio.read_dataframe(ade, layer="departement", columns=["code_insee"], read_geometry=True)
    report = {"departements": {}}
    for territory in ("met", "mart", "reun"):
        crs = TERRITORIES[territory]
        with stage(f"Filosofi {territory} (sans géométrie)"):
            cells = load_filosofi(territory)
        deps_t = deps[deps["code_insee"].isin(["972"] if territory == "mart" else ["974"] if territory == "reun"
                                              else [d for d in deps["code_insee"] if not d.startswith("97")])]
        dep_of = assign_polygons(cells, deps_t.rename(columns={"code_insee": "dep"}), "dep", crs)
        cells["dep"] = dep_of.fillna(cells["dep_indice"])        # centroïde en mer / hors polygone : indice lcog_geo
        for dep, c in cells.groupby("dep", sort=True):
            with stage(f"dep {dep}"):
                c = c.copy()
                com = gpd.read_file(ade, layer="commune", where=f"code_insee_du_departement = '{dep}'",
                                    columns=["code_insee", "population"])
                c["code_insee"] = assign_polygons(c, com, "code_insee", crs)
                miss = c["code_insee"].isna()
                c.loc[miss, "code_insee"] = c.loc[miss, "lcog_geo"].str.split(",").str[0]
                iris = gpd.read_file(iris_gpkg, where=f"code_insee LIKE '{dep}%'", columns=["code_iris"])
                c["code_iris"] = assign_polygons(c, iris, "code_iris", crs)
                tot = c.groupby("code_insee")["ind"].sum()
                ratio = com.set_index("code_insee")["population"] / tot.reindex(com["code_insee"]).to_numpy()
                c["ratio_calage"] = c["code_insee"].map(ratio).replace([np.inf, -np.inf], np.nan).fillna(1.0)
                c["pop_calee"] = c["ind"] * c["ratio_calage"]
                vi = c["code_iris"].map(v_iris)
                vc = c["code_insee"].map(v_com)
                c["part_sans_voiture"] = vi.fillna(vc)
                non_irisee = c["code_iris"].fillna("").str.endswith("0000")
                c["motorisation_source"] = np.select([vi.notna(), non_irisee & vc.notna(), vc.notna()],
                                                     ["iris", "commune_non_irisee", "repli_commune"], "absente")
                c.drop(columns=["dep_indice"]).to_parquet(out_dir / f"{dep}.parquet", index=False)
                report["departements"][dep] = {
                    "carreaux": len(c), "ind": round(float(c["ind"].sum())), "pop_calee": round(float(c["pop_calee"].sum())),
                    "population_recensement": int(com["population"].sum()),
                    "commune_par_repli_lcog": int(miss.sum()), "sans_iris": int(c["code_iris"].isna().sum()),
                    "taux_jointure_iris": round(float(vi[~non_irisee].notna().mean()), 4) if (~non_irisee).any() else None,
                    "sans_motorisation": int(c["part_sans_voiture"].isna().sum())}
        del cells
    d = pd.DataFrame(report["departements"]).T
    report["total"] = {"carreaux": int(d.carreaux.sum()), "ind": int(d.ind.sum()), "pop_calee": int(d.pop_calee.sum()),
                       "population_recensement_deps_couverts": int(d.population_recensement.sum())}
    national("cells_rapport.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    save_stages("cells")
    print(json.dumps(report["total"], indent=1))
    return report


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_cells()
