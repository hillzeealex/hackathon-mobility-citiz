"""
Population au carreau de 200 m -> data/processed/population.parquet (GeoParquet, Lambert-93)

1. Carreaux Filosofi 2021 dont le CENTROÏDE est dans la zone (pas de double compte en bordure) ;
   commune du carreau = commune contenant le centroïde.
2. Calage : pop_calee = ind × (population recensement de la commune / Σ ind Filosofi de la commune).
   Filosofi ne compte que les ménages fiscaux ordinaires (sans résidences étudiantes, foyers...) ;
   le calage redonne le total communal du recensement en gardant la répartition Filosofi.
   pop_calee sert à toutes les couvertures ; ind est conservé pour comparaison.
3. Motorisation : part de ménages sans voiture = 1 − ménages avec ≥ 1 voiture / ménages (recensement 2023,
   logement par IRIS). Centroïde -> IRIS 2026 (IGN) -> valeur IRIS 2023 ; à défaut (IRIS redécoupé, commune
   non irisée) valeur de la commune. Taux de jointure et replis affichés.

Sorties annexes : population_calage_communes.csv, population_rapport.json
"""
from __future__ import annotations

import json
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from src.common.config import load_settings, processed, raw
from src.ingest.archives import filosofi_gpkg, ign_gpkg
from src.ingest.zone import load_zone

CELL_AREA_KM2 = 0.04
FILOSOFI_COLS = ["idcar_200m", "i_est_200", "ind", "men", "men_pauv", "ind_snv", "men_prop", "log_soc",
                 "ind_0_3", "ind_4_5", "ind_6_10", "ind_11_17", "ind_18_24", "ind_25_39", "ind_40_54",
                 "ind_55_64", "ind_65_79", "ind_80p"]
LOGEMENT_ZIP = "base_ic_logement_2023_iris.zip"


# ---------------------------------------------------------------------------------------------
def load_filosofi(zone: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Carreaux dont le centroïde est dans une commune de la zone, avec le code de cette commune."""
    f = gpd.read_file(filosofi_gpkg(), bbox=tuple(zone.total_bounds), columns=FILOSOFI_COLS)
    f = f.to_crs(zone.crs)
    cent = gpd.GeoDataFrame(f[["idcar_200m"]], geometry=f.centroid, crs=zone.crs)
    j = gpd.sjoin(cent, zone[["code_insee", "geometry"]], how="inner", predicate="within")
    j = j[~j.index.duplicated()]
    return f.loc[j.index].assign(code_insee=j["code_insee"].to_numpy()).reset_index(drop=True)


def calage(cells: pd.DataFrame, communes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajoute pop_calee ; renvoie aussi le ratio recensement / Filosofi par commune."""
    tot = cells.groupby("code_insee")["ind"].sum().rename("ind_filosofi")
    ratio = communes.set_index("code_insee")[["nom", "population"]].join(tot, how="left")
    ratio["ratio"] = ratio["population"] / ratio["ind_filosofi"]
    out = cells.copy()
    out["ratio_calage"] = out["code_insee"].map(ratio["ratio"]).fillna(1.0)
    out["pop_calee"] = out["ind"] * out["ratio_calage"]
    return out, ratio.reset_index().sort_values("ratio", ascending=False)


# ---------------------------------------------------------------------------------------------
def _col(columns, prefix: str) -> str:
    return next(c for c in columns if str(c).strip().startswith(prefix))


def logement_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(par IRIS, par commune) : menages, menages_voiture. Lecture xlsx mise en cache en parquet."""
    cache_iris, cache_com = processed("cache", "logement_iris.parquet"), processed("cache", "logement_com.parquet")
    if cache_iris.exists() and cache_com.exists():
        return pd.read_parquet(cache_iris), pd.read_parquet(cache_com)
    with zipfile.ZipFile(raw("insee", LOGEMENT_ZIP)) as z:
        member = next(n for n in z.namelist() if n.endswith(".xlsx"))
        with z.open(member) as fh:
            sheets = pd.read_excel(fh, sheet_name=["IRIS_2023", "COM_2023_non_irisees"], dtype={0: str})

    def tidy(df: pd.DataFrame, code: str) -> pd.DataFrame:
        return pd.DataFrame({code: df[_col(df.columns, "Code g")].astype(str).str.strip(),
                             "menages": pd.to_numeric(df[_col(df.columns, "Ménages (princ)")], errors="coerce"),
                             "menages_voiture": pd.to_numeric(df[_col(df.columns, "Ménages au moins une voiture")],
                                                              errors="coerce")})
    iris = tidy(sheets["IRIS_2023"], "code_iris")
    com_non_iris = tidy(sheets["COM_2023_non_irisees"], "code_insee")
    com_iris = iris.assign(code_insee=iris["code_iris"].str[:5]).groupby("code_insee")[["menages", "menages_voiture"]].sum().reset_index()
    com = pd.concat([com_iris, com_non_iris[~com_non_iris["code_insee"].isin(com_iris["code_insee"])]], ignore_index=True)
    iris.to_parquet(cache_iris)
    com.to_parquet(cache_com)
    return iris, com


def part_sans_voiture(t: pd.DataFrame) -> pd.Series:
    return (1 - t["menages_voiture"] / t["menages"]).where(t["menages"] > 0).clip(0, 1)


def motorisation(cells: gpd.GeoDataFrame, iris_contours: gpd.GeoDataFrame, iris_tab: pd.DataFrame,
                 com_tab: pd.DataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """Ajoute code_iris, part_sans_voiture, motorisation_source ∈ {iris, commune_non_irisee, repli_commune, absente}."""
    cent = gpd.GeoDataFrame(cells[[]], geometry=cells.centroid, crs=cells.crs)
    j = gpd.sjoin(cent, iris_contours[["code_iris", "geometry"]].to_crs(cells.crs), how="left", predicate="within")
    j = j[~j.index.duplicated()]
    out = cells.copy()
    out["code_iris"] = j["code_iris"].reindex(out.index).to_numpy()
    v_iris = out["code_iris"].map(part_sans_voiture(iris_tab).set_axis(iris_tab["code_iris"]))
    v_com = out["code_insee"].map(part_sans_voiture(com_tab).set_axis(com_tab["code_insee"]))
    out["part_sans_voiture"] = v_iris.fillna(v_com)
    non_irisee = out["code_iris"].fillna("").str.endswith("0000")  # commune non découpée en IRIS : valeur communale
    out["motorisation_source"] = np.select(
        [v_iris.notna(), non_irisee & v_com.notna(), v_com.notna()],
        ["iris", "commune_non_irisee", "repli_commune"], default="absente")
    irisee = ~non_irisee
    rep = {"carreaux": len(out),
           "carreaux_communes_irisees": int(irisee.sum()),
           "jointure_iris_ok": int((irisee & v_iris.notna()).sum()),
           "taux_jointure_iris": round(float(v_iris[irisee].notna().mean()), 4) if irisee.any() else 1.0,
           "repli_commune": int((out["motorisation_source"] == "repli_commune").sum()),
           "commune_non_irisee": int((out["motorisation_source"] == "commune_non_irisee").sum()),
           "sans_valeur": int(out["part_sans_voiture"].isna().sum())}
    return out, rep


# ---------------------------------------------------------------------------------------------
def build_population() -> gpd.GeoDataFrame:
    s = load_settings()
    zone = load_zone()
    if zone.attrs.get("provisoire"):
        raise RuntimeError("zone.gpkg requis (python -m src.ingest.zone)")
    cells = load_filosofi(zone)
    cells, ratio = calage(cells, zone)
    iris_tab, com_tab = logement_tables()
    iris_contours = gpd.read_file(ign_gpkg("iris"), bbox=tuple(zone.to_crs(4326).total_bounds),
                                  columns=["code_iris", "nom_iris"])
    cells, rep = motorisation(cells, iris_contours, iris_tab, com_tab)
    cells["niveau_vie_moyen"] = (cells["ind_snv"] / cells["ind"]).where(cells["ind"] > 0)
    cells["part_menages_pauvres"] = (cells["men_pauv"] / cells["men"]).where(cells["men"] > 0).clip(0, 1)
    cells["densite_hab_km2"] = cells["pop_calee"] / CELL_AREA_KM2
    cells = cells.to_crs(s["crs"]["metric"])
    cells.to_parquet(processed("population.parquet"))
    ratio.to_csv(processed("population_calage_communes.csv"), index=False)

    rep.update({"ind_filosofi": round(float(cells["ind"].sum())), "pop_calee": round(float(cells["pop_calee"].sum())),
                "population_recensement": int(zone["population"].sum()),
                "carreaux_men_lt_11": int((cells["men"] < s["privacy"]["min_households"]).sum()),
                "carreaux_estimes_i_est_200": int((cells["i_est_200"] == 1).sum())})
    processed("population_rapport.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    print("\nCalage par commune (recensement 2023 / Filosofi 2021), 10 ratios les plus élevés :")
    print(ratio.head(10).to_string(index=False, formatters={"ratio": "{:.2f}".format, "ind_filosofi": "{:,.0f}".format}))
    return cells


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_population()
