"""
Variables du modèle pour chaque carreau peuplé de France métropolitaine -> data/processed/model/features.parquet

Cible : `cible_citiz_400m` = au moins une station Citiz à 400 m (vol d'oiseau) du centroïde.
Variables (aucune ne dépend de Citiz, pour éviter les fuites) :
  - population : pop_calee, densité du voisinage à 400 m et 800 m (hab./km²)
  - revenus : niveau de vie moyen, part de ménages pauvres, part de propriétaires, part de logements sociaux
  - motorisation : part des ménages sans voiture (IRIS, repli commune)
  - offre de TC et autres mobilités (V1, 400 m) : arrêts de TC, options pondérées hors Citiz
  - équipements BPE 2025 à 400 m : total et par domaine (services, commerces, enseignement, santé, transports,
    sports-loisirs-culture, tourisme)
  - risque : vols liés aux véhicules pour 1 000 hab. (commune ≥ 10 000 hab., sinon EPCI)
Groupe de validation : réseau régional Citiz de l'EPCI (majoritaire parmi ses stations).
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pyogrio

from src.common.config import load_settings, processed, raw
from src.ingest.archives import ign_gpkg
from src.national.common import national, read_parquet_dir

BPE_DOMAINS = {"A": "services", "B": "commerces", "C": "enseignement", "D": "sante", "E": "transports",
               "F": "sports_loisirs", "G": "tourisme"}
FEATURES = ["pop_calee", "densite_400m", "densite_800m", "niveau_vie", "part_menages_pauvres", "part_proprietaires",
            "part_logements_sociaux", "part_sans_voiture", "n_arrets_tc_400m", "options_hors_citiz_400m",
            "equipements_400m", *[f"bpe_{v}_400m" for v in BPE_DOMAINS.values()], "vols_vehicules_1000"]
RISK_MIN_POP = 10_000


def model_path(*parts: str):
    return processed("model", *parts)


def disk_kernel(radius: float, step: float = 200.0) -> np.ndarray:
    k = int(radius // step)
    dy, dx = np.mgrid[-k:k + 1, -k:k + 1]
    return (np.hypot(dx, dy) * step <= radius).astype(np.float32)


def grid_sum(cells_xy: np.ndarray, points_xy: np.ndarray, weights: np.ndarray | None, radius: float,
             step: float = 200.0) -> np.ndarray:
    """Σ des poids des points situés dans les carreaux de 200 m dont le centre est à ≤ radius du carreau.

    Les points sont rangés dans la grille des carreaux (centroïdes Filosofi = coin + 100 m), puis on convolue
    par un disque : exact pour la population des carreaux, approché à ± 100 m pour des points (équipements).
    """
    from scipy.ndimage import convolve
    x0, y0 = cells_xy.min(axis=0) - step / 2
    ci = np.floor((cells_xy - [x0, y0]) / step).astype(int)
    shape = tuple(ci.max(axis=0) + 1)
    pi = np.floor((points_xy - [x0, y0]) / step).astype(int)
    ok = (pi >= 0).all(axis=1) & (pi[:, 0] < shape[0]) & (pi[:, 1] < shape[1])
    grid = np.zeros(shape, np.float32)
    np.add.at(grid, (pi[ok, 0], pi[ok, 1]), 1.0 if weights is None else weights[ok].astype(np.float32))
    out = convolve(grid, disk_kernel(radius, step), mode="constant")
    return out[ci[:, 0], ci[:, 1]].astype(float)


def citiz_network_by_epci() -> pd.Series:
    """EPCI -> jeu GBFS Citiz majoritaire parmi ses stations (groupe de validation spatiale)."""
    import geopandas as gpd

    from src.national.ranking import points_to_epci
    off = pd.read_parquet(national("offer.parquet"), columns=["type", "sous_type", "source", "lon", "lat"])
    cz = off[(off["type"] == "citiz") & (off["sous_type"] == "station")].copy()
    epci = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="epci", columns=["code_siren"]).rename(
        columns={"code_siren": "code_epci"})
    cz["code_epci"] = points_to_epci(cz, gpd.GeoDataFrame(epci, geometry="geometry"))
    cz["reseau"] = cz["source"].str.replace("gbfs:", "", regex=False)
    return cz.dropna(subset=["code_epci"]).groupby("code_epci")["reseau"].agg(lambda s: s.value_counts().index[0])


def risk_by_commune() -> pd.Series:
    from src.national.ranking import security_by_commune, security_rates
    com = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="commune", read_geometry=False,
                                 columns=["code_insee", "population", "codes_siren_des_epci"])
    com["code_epci"] = com["codes_siren_des_epci"].fillna("").str.split(r"[/,; ]+").str[0]
    sec = security_by_commune()
    by_com = security_rates(sec, sec.index)["vols_vehicules_1000"]
    by_epci = security_rates(sec, sec.index.map(com.set_index("code_insee")["code_epci"]))["vols_vehicules_1000"]
    com = com.set_index("code_insee")
    rate = by_com.reindex(com.index)
    small = com["population"].fillna(0) < RISK_MIN_POP
    rate[small | rate.isna()] = com.loc[small | rate.isna(), "code_epci"].map(by_epci)
    return rate


def build_features() -> pd.DataFrame:
    s = load_settings()
    r = s["walk"]["radius_m"]
    cols = ["idcar_200m", "territoire", "dep", "code_insee", "code_iris", "x", "y", "pop_calee", "ind", "men",
            "men_pauv", "ind_snv", "part_sans_voiture", "n_options", "n_tc", "n_citiz"]
    a = read_parquet_dir(national("access"), columns=cols)
    a = a[(a["territoire"] == "met") & (a["pop_calee"] > 0)]
    extra = read_parquet_dir(national("cells"), columns=["idcar_200m", "men_prop", "log_soc"])
    a = a.merge(extra.drop_duplicates("idcar_200m"), on="idcar_200m", how="left").reset_index(drop=True)
    xy = a[["x", "y"]].to_numpy(float)
    pop = a["pop_calee"].to_numpy(float)
    f = a[["idcar_200m", "dep", "code_insee", "code_iris", "x", "y", "pop_calee"]].copy()
    for rad in (r, 2 * r):   # densité du voisinage : population des carreaux à ≤ rad / surface de ces carreaux
        f[f"densite_{rad}m"] = grid_sum(xy, xy, pop, rad) / (disk_kernel(rad).sum() * 0.04)
    f["niveau_vie"] = a["ind_snv"] / a["ind"].replace(0, np.nan)
    f["part_menages_pauvres"] = (a["men_pauv"] / a["men"].replace(0, np.nan)).clip(0, 1)
    f["part_proprietaires"] = (a["men_prop"] / a["men"].replace(0, np.nan)).clip(0, 1)
    f["part_logements_sociaux"] = (a["log_soc"] / a["men"].replace(0, np.nan)).clip(0, 1)
    f["part_sans_voiture"] = a["part_sans_voiture"]
    f["n_arrets_tc_400m"] = a["n_tc"]
    f["options_hors_citiz_400m"] = (a["n_options"] - s["mode_weights"]["citiz"] * a["n_citiz"]).clip(lower=0)

    bpe = pd.read_parquet(raw("insee", "bpe25.parquet"), columns=["DEP", "DOM", "LAMBERT_X", "LAMBERT_Y", "EPSG"])
    bpe = bpe[~bpe["DEP"].astype(str).str.startswith("97") & bpe["LAMBERT_X"].notna()]
    bpe = bpe[bpe["EPSG"].astype(str).str.contains("2154") | bpe["EPSG"].isna()]
    pts = bpe[["LAMBERT_X", "LAMBERT_Y"]].to_numpy(float)
    f["equipements_400m"] = grid_sum(xy, pts, None, r)
    for dom, name in BPE_DOMAINS.items():
        m = (bpe["DOM"] == dom).to_numpy()
        f[f"bpe_{name}_400m"] = grid_sum(xy, pts[m], None, r)

    f["vols_vehicules_1000"] = f["code_insee"].map(risk_by_commune())
    com = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="commune", read_geometry=False,
                                 columns=["code_insee", "codes_siren_des_epci"])
    f["code_epci"] = f["code_insee"].map(com.set_index("code_insee")["codes_siren_des_epci"].fillna("")
                                         .str.split(r"[/,; ]+").str[0])
    f["reseau_citiz"] = f["code_epci"].map(citiz_network_by_epci())
    f["cible_citiz_400m"] = (a["n_citiz"] > 0).astype(int)
    f.to_parquet(model_path("features.parquet"), index=False)
    rep = {"carreaux_metropole": len(f), "carreaux_perimetre_citiz": int(f["reseau_citiz"].notna().sum()),
           "positifs": int(f["cible_citiz_400m"].sum()),
           "positifs_hors_perimetre": int(f.loc[f["reseau_citiz"].isna(), "cible_citiz_400m"].sum()),
           "reseaux": int(f["reseau_citiz"].nunique()), "valeurs_manquantes": f[FEATURES].isna().sum().to_dict()}
    model_path("features_rapport.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return f


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_features()
