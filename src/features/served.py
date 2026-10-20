"""
Objectif 2 : population desservie par chaque arrêt / station -> data/processed/<ville>/
  offer_served.parquet   offer.parquet + pop_desservie, pop_seule_option, part_seule_option, version
  served_by_type.csv     par type : points, population desservie (au moins un point du type), médiane par point

    python -m src.features.served --ville nantes

Utilise la matrice de couverture la plus précise disponible (V2 réseau sinon V1 vol d'oiseau).
pop_seule_option : habitants pour qui ce point est la SEULE option à 5 min (le retirer les laisse sans rien).
"""
from __future__ import annotations

import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import scipy.sparse as sp

from src.common.config import city_from_args, city_processed


def population_served(cov: sp.spmatrix, pop: np.ndarray) -> pd.DataFrame:
    """Pour chaque point d'offre j : Σ_i C_ij P_i et Σ_i C_ij P_i [i n'a que j]."""
    c = sp.csr_matrix(cov, dtype=float)
    n_points = np.asarray(c.sum(axis=1)).ravel()
    served = c.T @ pop
    only = c.T @ (pop * (n_points == 1))
    return pd.DataFrame({"pop_desservie": served, "pop_seule_option": only,
                         "part_seule_option": np.divide(only, served, out=np.zeros_like(served), where=served > 0)})


def served_by_type(cov: sp.spmatrix, pop: np.ndarray, offer: pd.DataFrame, per_point: pd.DataFrame) -> pd.DataFrame:
    c = sp.csr_matrix(cov)
    rows = []
    for t, idx in offer.groupby("type").indices.items():
        covered = np.asarray(c[:, idx].sum(axis=1)).ravel() > 0
        in_zone = offer["dans_zone"].to_numpy()[idx] if "dans_zone" in offer else np.ones(len(idx), bool)
        rows.append({"type": t, "points_dans_zone": int(in_zone.sum()),
                     "pop_desservie": round(float(pop[covered].sum())),
                     "part_pop_desservie": round(float(pop[covered].sum() / pop.sum()), 4),
                     "pop_mediane_par_point": round(float(np.median(per_point["pop_desservie"].to_numpy()[idx][in_zone])))
                     if in_zone.any() else 0})
    return pd.DataFrame(rows).sort_values("pop_desservie", ascending=False)


def build_served() -> pd.DataFrame:
    cells = gpd.read_parquet(city_processed("access_cells.parquet"))
    offer = gpd.read_parquet(city_processed("offer.parquet")).reset_index(drop=True)
    version = "v2" if city_processed("coverage_v2.npz").exists() else "v1"
    cov = sp.load_npz(city_processed(f"coverage_{version}.npz"))
    if cov.shape != (len(cells), len(offer)):
        raise ValueError(f"coverage_{version}.npz {cov.shape} ne correspond pas aux tables ({len(cells)}, {len(offer)}) : "
                         "relancer build_access")
    pop = cells["pop_calee"].to_numpy(float)
    per_point = population_served(cov, pop)
    out = pd.concat([offer, per_point], axis=1).assign(version=version)
    out.to_parquet(city_processed("offer_served.parquet"))
    by_type = served_by_type(cov, pop, offer, per_point)
    by_type.to_csv(city_processed("served_by_type.csv"), index=False)
    print(f"Couverture {version} ; population desservie par type :\n{by_type.to_string(index=False)}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    city_from_args()
    build_served()
