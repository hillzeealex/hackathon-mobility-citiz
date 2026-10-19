"""
Niveau 1 : accessibilité V1 (400 m à vol d'oiseau) des 2,3 M carreaux -> data/processed/national/

  access/<dep>.parquet       un carreau par ligne : indicateurs + attributs utiles aux agrégats
  agg_{iris,commune,epci,departement}.parquet

Indicateurs (formules : docs/methodologie.md §4) :
  n_options     Σ_j C_ij w_j            options pondérées accessibles (indicateur principal)
  n_<type>      points accessibles par type
  acces_1000    2SFCA toutes options    1000 Σ_j C_ij w_j / D_j
  citiz_1000    2SFCA Citiz             1000 Σ_j C_ij V_j / D_j   (V_j = véhicules = capacité déclarée)
avec D_j = population calée à moins de R du point j, calculée sur TOUT le territoire (pas seulement le département).
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pyogrio
import scipy.sparse as sp
from scipy.spatial import cKDTree

from src.common.config import load_settings
from src.features.accessibility import offer_weights
from src.ingest.archives import ign_gpkg
from src.national.common import national, read_parquet_dir, save_stages, stage

TYPES = ["bus", "tram", "metro", "train", "telepherique", "velo", "trottinette", "citiz", "autopartage"]
TC = ["bus", "tram", "metro", "train", "telepherique"]
CELL_COLS = ["idcar_200m", "territoire", "dep", "code_insee", "code_iris", "x", "y", "lon", "lat", "ind", "men",
             "men_pauv", "ind_snv", "pop_calee", "part_sans_voiture"]
CHUNK = 50_000


def coverage(cells_xy: np.ndarray, tree: cKDTree, radius: float, n_offer: int) -> sp.csr_matrix:
    """C[i, j] = 1 si le point d'offre j est à moins de `radius` du carreau i (lignes = carreaux)."""
    lists = tree.query_ball_point(cells_xy, radius, return_sorted=False)
    lens = np.fromiter((len(x) for x in lists), dtype=np.int64, count=len(lists))
    cols = np.fromiter((j for x in lists for j in x), dtype=np.int64, count=int(lens.sum()))
    indptr = np.concatenate([[0], np.cumsum(lens)])
    return sp.csr_matrix((np.ones(len(cols), bool), cols, indptr), shape=(len(cells_xy), n_offer))


def demand(offer_xy: np.ndarray, cells_xy: np.ndarray, pop: np.ndarray, radius: float) -> np.ndarray:
    """D_j : population calée à moins de `radius` de chaque point d'offre (par paquets : mémoire bornée)."""
    tree = cKDTree(cells_xy)
    out = np.zeros(len(offer_xy))
    for k in range(0, len(offer_xy), CHUNK):
        lists = tree.query_ball_point(offer_xy[k:k + CHUNK], radius, return_sorted=False)
        out[k:k + CHUNK] = [pop[x].sum() if x else 0.0 for x in lists]
    return out


def build_access() -> dict:
    s = load_settings()
    r = s["walk"]["radius_m"]
    out_dir = national("access")
    out_dir.mkdir(parents=True, exist_ok=True)
    with stage("lecture carreaux + offre"):
        cells = read_parquet_dir(national("cells"), columns=CELL_COLS)
        cells = cells[cells["pop_calee"] > 0].reset_index(drop=True)
        offer = pd.read_parquet(national("offer.parquet"))
        offer["w"] = offer_weights(offer, s)
        offer["v_citiz"] = np.where(offer["type"] == "citiz", offer["capacite"].fillna(1).clip(lower=1), 0.0)
    report = {"carreaux": len(cells), "points_offre": len(offer), "territoires": {}}
    for terr, ct in cells.groupby("territoire"):
        # les CRS métriques des carreaux et de l'offre coïncident par territoire (met 2154, mart 5490, reun 2975)
        ot = offer[offer["territoire"].isin({"met": ["met"], "mart": ["972"], "reun": ["974"]}[terr])].reset_index(drop=True)
        oxy = ot[["x", "y"]].to_numpy()
        with stage(f"demande D_j {terr}"):
            dem = demand(oxy, ct[["x", "y"]].to_numpy(), ct["pop_calee"].to_numpy(), r)
        tree = cKDTree(oxy)
        w = ot["w"].to_numpy()
        ratio_all = np.divide(w, dem, out=np.zeros_like(w), where=dem > 0)
        v = ot["v_citiz"].to_numpy()
        ratio_citiz = np.divide(v, dem, out=np.zeros_like(v), where=dem > 0)
        type_masks = {t: (ot["type"] == t).to_numpy().astype(float) for t in TYPES}
        nnz = 0
        with stage(f"couverture V1 et indicateurs {terr} ({len(ct)} carreaux)"):
            for dep, c in ct.groupby("dep", sort=True):
                cov = coverage(c[["x", "y"]].to_numpy(), tree, r, len(ot)).astype(float)
                nnz += cov.nnz
                res = c.copy()
                res["n_options"] = cov @ w
                res["n_points"] = np.asarray(cov.sum(axis=1)).ravel()
                for t, m in type_masks.items():
                    res[f"n_{t}"] = cov @ m
                res["n_tc"] = res[[f"n_{t}" for t in TC]].sum(axis=1)
                res["acces_1000"] = 1000 * (cov @ ratio_all)
                res["citiz_1000"] = 1000 * (cov @ ratio_citiz)
                res.to_parquet(out_dir / f"{dep}.parquet", index=False)
        report["territoires"][terr] = {"carreaux": len(ct), "points_offre": len(ot), "paires_couvertes": int(nnz)}
    national("access_rapport.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    save_stages("access")
    return report


# ---------------------------------------------------------------------------------------------
def weighted(g: pd.DataFrame, col: str, w: str = "pop_calee") -> float:
    tot = g[w].sum()
    return float((g[col] * g[w]).sum() / tot) if tot else np.nan


def aggregate(a: pd.DataFrame, key: str) -> pd.DataFrame:
    a = a.assign(_sans_option=(a["n_points"] == 0) * a["pop_calee"], _tc=(a["n_tc"] > 0) * a["pop_calee"],
                 _citiz=(a["n_citiz"] > 0) * a["pop_calee"], _opt=a["n_options"] * a["pop_calee"],
                 _acc=a["acces_1000"] * a["pop_calee"], _cz=a["citiz_1000"] * a["pop_calee"],
                 _sv=a["part_sans_voiture"].fillna(0) * a["men"], _svm=a["part_sans_voiture"].notna() * a["men"],
                 _dens=a["pop_calee"] * a["pop_calee"] / 0.04)
    g = a.groupby(key).agg(carreaux=("idcar_200m", "size"), population=("pop_calee", "sum"), menages=("men", "sum"),
                           ind=("ind", "sum"), men_pauv=("men_pauv", "sum"), ind_snv=("ind_snv", "sum"),
                           _sans_option=("_sans_option", "sum"), _tc=("_tc", "sum"), _citiz=("_citiz", "sum"),
                           _opt=("_opt", "sum"), _acc=("_acc", "sum"), _cz=("_cz", "sum"), _sv=("_sv", "sum"),
                           _svm=("_svm", "sum"), _dens=("_dens", "sum"))
    p = g["population"]
    out = pd.DataFrame({"carreaux": g.carreaux, "population": p, "menages": g.menages,
                        "n_options_moyen": g._opt / p, "part_pop_sans_option": g._sans_option / p,
                        "part_pop_avec_tc": g._tc / p, "part_pop_citiz_5min": g._citiz / p,
                        "acces_1000_moyen": g._acc / p, "citiz_1000_moyen": g._cz / p,
                        "part_menages_sans_voiture": g._sv / g._svm.replace(0, np.nan),
                        "niveau_vie_moyen": g.ind_snv / g.ind, "part_menages_pauvres": g.men_pauv / g.menages,
                        "densite_vecue_hab_km2": g._dens / p})
    return out.reset_index()


def build_aggregates() -> dict:
    with stage("agrégats IRIS / commune / EPCI / département"):
        a = read_parquet_dir(national("access"))
        com = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="commune", read_geometry=False,
                                     columns=["code_insee", "codes_siren_des_epci"])
        epci_of = com.set_index("code_insee")["codes_siren_des_epci"].fillna("").str.split(r"[/,; ]+").str[0]
        a["code_epci"] = a["code_insee"].map(epci_of).replace("", np.nan)
        sizes = {}
        for key, name in (("code_iris", "iris"), ("code_insee", "commune"), ("code_epci", "epci"), ("dep", "departement")):
            agg = aggregate(a, key)
            agg.to_parquet(national(f"agg_{name}.parquet"), index=False)
            sizes[name] = len(agg)
        pop = a["pop_calee"].to_numpy()
        tot = {"population": round(float(pop.sum())),
               "part_pop_sans_option": round(float(((a["n_points"] == 0) * pop).sum() / pop.sum()), 4),
               "part_pop_avec_tc": round(float(((a["n_tc"] > 0) * pop).sum() / pop.sum()), 4),
               "part_pop_citiz_5min": round(float(((a["n_citiz"] > 0) * pop).sum() / pop.sum()), 4),
               "n_options_moyen": round(float((a["n_options"] * pop).sum() / pop.sum()), 2),
               "carreaux_sans_epci": int(a["code_epci"].isna().sum())}
    save_stages("aggregates")
    rep = {"niveaux": sizes, "france": tot}
    national("agg_rapport.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return rep


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(build_access(), indent=1))
    build_aggregates()
