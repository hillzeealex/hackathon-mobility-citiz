"""
Génère des données FACTICES au format du contrat de app/data.py, dans data/processed/demo/.
Sert à valider l'ergonomie de l'application avant que le pipeline réel soit prêt.

    python scripts/make_demo_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.spatial import cKDTree
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data import DEMO  # noqa: E402
from src.optim.costs import equipment_cost  # noqa: E402

RNG = np.random.default_rng(42)
X0, Y0, N, SIZE, R = 905_000, 6_448_000, 50, 200, 400   # grille 10 km × 10 km autour de Grenoble (Lambert-93)
TYPES = ["bus", "tram", "velo", "trottinette", "citiz"]
CAND_TYPES = {"citiz_station": "citiz", "bus_stop": "bus", "bike_station": "velo"}


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    # Carreaux : population en deux pôles (centre dense + périphérie)
    ii, jj = np.meshgrid(np.arange(N), np.arange(N))
    cx, cy = X0 + ii.ravel() * SIZE + SIZE / 2, Y0 + jj.ravel() * SIZE + SIZE / 2
    d1 = np.hypot(cx - (X0 + 5000), cy - (Y0 + 5500)) / 1500
    d2 = np.hypot(cx - (X0 + 2500), cy - (Y0 + 2000)) / 1200
    pop = np.round(900 * np.exp(-d1 ** 2) + 350 * np.exp(-d2 ** 2) + RNG.gamma(1.2, 15, N * N))
    keep = pop >= 5
    cells = gpd.GeoDataFrame({"id": [f"c{k}" for k in np.flatnonzero(keep)], "population": pop[keep]},
                             geometry=[box(x - SIZE / 2, y - SIZE / 2, x + SIZE / 2, y + SIZE / 2)
                                       for x, y in zip(cx[keep], cy[keep])], crs=2154)
    cells["menages"] = np.round(cells.population / 2.1, 1)
    xy = np.column_stack([cx[keep], cy[keep]])

    # Offre existante, plus dense au centre
    n_off = 450
    pts = np.column_stack([RNG.normal(X0 + 5000, 2200, n_off), RNG.normal(Y0 + 5000, 2200, n_off)])
    otype = RNG.choice(TYPES, n_off, p=[0.45, 0.12, 0.18, 0.15, 0.10])
    offer = gpd.GeoDataFrame({"id": [f"o{k}" for k in range(n_off)], "type": otype,
                              "sous_type": np.where(np.isin(otype, ["velo", "trottinette"]), "zone_free_floating", "station"),
                              "nom": [f"Point {k}" for k in range(n_off)], "source": "demo",
                              "capacite": RNG.integers(2, 15, n_off).astype(float),
                              "passages_jour": np.where(np.isin(otype, ["bus", "tram"]), RNG.integers(20, 600, n_off), np.nan)},
                             geometry=gpd.points_from_xy(pts[:, 0], pts[:, 1]), crs=2154)
    weights = {"bus": 1.0, "tram": 2.0, "velo": 1.0, "trottinette": 0.5, "citiz": 1.5}
    tree = cKDTree(pts)
    near = tree.query_ball_point(xy, R)
    cells["n_options"] = [sum(weights[otype[k]] for k in ks) for ks in near]
    cells["score_acces"] = 1000 * cells.n_options / cells.population
    for ct, ot in CAND_TYPES.items():
        cells[f"couvert_{ct}"] = [any(otype[k] == ot for k in ks) for ks in near]
    revenu_rel = 1 - (cells.population / cells.population.max()) * RNG.uniform(0.3, 1, len(cells))
    cells["priorite_equite"] = np.clip(0.5 * (1 - np.minimum(cells.n_options, 6) / 6) + 0.5 * revenu_rel, 0, 1).round(3)

    # Population desservie par point d'offre
    cell_tree = cKDTree(xy)
    served = cell_tree.query_ball_point(pts, R)
    only = [[c for c in cs if len(near[c]) == 1] for cs in served]
    offer["pop_desservie"] = [cells.population.to_numpy()[cs].sum() for cs in served]
    offer["pop_seule_option"] = [cells.population.to_numpy()[cs].sum() for cs in only]
    offer["part_seule_option"] = np.where(offer.pop_desservie > 0, offer.pop_seule_option / offer.pop_desservie, 0)

    # IRIS factices : blocs de 1 km
    cells["code_iris"] = [f"38185{int((x - X0) // 1000):02d}{int((y - Y0) // 1000):02d}" for x, y in xy]
    iris = cells.dissolve("code_iris", aggfunc={"population": "sum", "menages": "sum", "n_options": "sum"}).reset_index()
    iris["nom"] = "IRIS " + iris.code_iris.str[-4:]
    iris["score_acces"] = 1000 * iris.n_options / iris.population

    # Candidats : centroïdes de carreaux peuplés + quelques arrêts existants ; couverture 400 m
    idx = RNG.choice(len(cells), 400, replace=False, p=cells.population / cells.population.sum())
    ctype = RNG.choice(list(CAND_TYPES), 400, p=[0.6, 0.25, 0.15])
    cxy = xy[idx] + RNG.normal(0, 30, (400, 2))
    cand = gpd.GeoDataFrame({"id": [f"k{k}" for k in range(400)], "type": ctype,
                             "nom": [f"Candidat {k}" for k in range(400)],
                             "cout": [equipment_cost(t)["total"] for t in ctype],
                             "usage_predit": np.round(RNG.gamma(2, 1.5, 400) * (1 + cells.population.to_numpy()[idx] / 500), 2),
                             "x": cxy[:, 0], "y": cxy[:, 1]},
                            geometry=gpd.points_from_xy(cxy[:, 0], cxy[:, 1]), crs=2154)
    rows, cols = [], []
    for j, cs in enumerate(cell_tree.query_ball_point(cxy, R)):
        rows += cs
        cols += [j] * len(cs)
    cov = sp.csr_matrix((np.ones(len(rows), bool), (rows, cols)), shape=(len(cells), len(cand)))

    cells.to_parquet(DEMO / "cells.parquet")
    iris.to_parquet(DEMO / "iris.parquet")
    offer.to_parquet(DEMO / "offer_served.parquet")
    cand.to_parquet(DEMO / "candidates.parquet")
    sp.save_npz(DEMO / "coverage.npz", cov)
    (DEMO / "meta.json").write_text(json.dumps({"zone": "Grenoble (données FACTICES)", "demo": True,
                                                "rayon_m": R}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(cells)} carreaux, {len(iris)} IRIS, {len(offer)} points d'offre, {len(cand)} candidats -> {DEMO}")


if __name__ == "__main__":
    main()
