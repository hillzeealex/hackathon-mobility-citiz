"""
Carte d'accessibilité d'une ville -> data/processed/<ville>/
  coverage_v1.npz [, coverage_v2.npz]  carreaux × points d'offre (lignes = access_cells.parquet, colonnes = offer.parquet)
  access_cells.parquet               carreaux habités + indicateurs V1 [/ V2] (A = n_options, B = acces_1000), par mode
  access_iris.parquet                agrégat IRIS (affichage public)
  access_comparaison.json            V1 [vs V2, avec / sans poids free-floating]
  docs/figures/<ville>/acces_*.png   cartes

    python -m src.features.build_access --ville nantes [--sans-v2]

La V2 (réseau piéton) demande l'extrait OSM de la région (cities.<ville>.osm_region).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import scipy.sparse as sp

from src.common.config import ROOT, city_from_args, city_processed, current_city, load_settings
from src.features.accessibility import (coverage_buffer, coverage_network, indicators, offer_weights,
                                        options_by_type, weighted_share)
from src.features.network import load_walk_edges, to_graph
from src.ingest.archives import ign_gpkg
from src.ingest.zone import load_zone

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TC = ["bus", "tram", "metro", "train", "telepherique"]


def summary(cov, w, pop, offer, label) -> dict:
    ind = indicators(cov, w, pop)
    tc = options_by_type(cov, offer["type"])
    has_tc = tc[[c for c in tc if c[2:] in TC]].sum(axis=1).to_numpy() > 0
    return {"version": label,
            "part_pop_au_moins_1_option": round(weighted_share(ind.n_points.to_numpy() > 0, pop), 4),
            "part_pop_au_moins_1_TC": round(weighted_share(has_tc, pop), 4),
            "part_pop_citiz": round(weighted_share(tc.get("n_citiz", 0) > 0, pop), 4),
            "options_moyennes_par_habitant": round(float((ind.n_options * pop).sum() / pop.sum()), 2),
            "paires_couvertes": int(sp.csr_matrix(cov).nnz)}


def plot_map(cells, col, title, path, zone, vmax=None, cmap="RdYlBu_r"):
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    zone.boundary.plot(ax=ax, color="#888", lw=0.4)
    v = cells[col]
    cells.plot(ax=ax, column=col, cmap=cmap, vmin=0, vmax=vmax or np.nanpercentile(v, 98), legend=True,
               legend_kwds={"shrink": 0.6, "label": col})
    ax.set_title(title, fontsize=10)
    ax.set_axis_off()
    minx, miny, maxx, maxy = cells.total_bounds
    ax.set_xlim(minx - 500, maxx + 500)
    ax.set_ylim(miny - 500, maxy + 500)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def coverage_by_type(cov, offer, pop) -> dict:
    out = {}
    for t in sorted(offer["type"].unique()):
        m = (offer["type"] == t).to_numpy()
        out[t] = round(weighted_share(np.asarray(cov[:, m].sum(axis=1)).ravel() > 0, pop), 3)
    return out


def build_access(with_v2: bool = True) -> dict:
    s = load_settings()
    r = s["walk"]["radius_m"]
    zone = load_zone()
    cells = gpd.read_parquet(city_processed("population.parquet"))
    cells = cells[cells["pop_calee"] > 0].reset_index(drop=True)   # lignes des matrices = access_cells.parquet
    offer = gpd.read_parquet(city_processed("offer.parquet")).reset_index(drop=True)
    pop = cells["pop_calee"].to_numpy(float)
    cxy = np.column_stack([cells.centroid.x, cells.centroid.y])
    oxy = np.column_stack([offer.geometry.x, offer.geometry.y])
    versions = ["v1"] + (["v2"] if with_v2 else [])

    t0 = time.time()
    cov = {"v1": coverage_buffer(cxy, oxy, r)}
    times = {"duree_v1_s": round(time.time() - t0, 2)}
    snap = None
    if with_v2:
        edges = load_walk_edges()
        t0 = time.time()
        cov["v2"], snap = coverage_network(to_graph(edges), edges, cxy, oxy, r)
        times["duree_v2_s"] = round(time.time() - t0, 1)
    for v in versions:
        sp.save_npz(city_processed(f"coverage_{v}.npz"), cov[v])

    w = offer_weights(offer, s)
    # « sans poids » free-floating : chaque zone au poids normal de son mode (vélo 1, trottinette 0,5)
    w_mode = offer_weights(offer.assign(sous_type=offer["sous_type"].replace("zone_free_floating", "zone")), s)
    out = cells[["idcar_200m", "code_insee", "code_iris", "pop_calee", "ind", "men", "part_sans_voiture",
                 "niveau_vie_moyen", "part_menages_pauvres", "geometry"]].copy()
    for v in versions:
        ind = indicators(cov[v], w, pop)
        out[f"n_options_{v}"] = ind.n_options.to_numpy()
        out[f"n_points_{v}"] = ind.n_points.to_numpy()
        out[f"acces_1000_{v}"] = ind.acces_1000.to_numpy()
    last = versions[-1]
    out[f"n_options_{last}_sans_poids_ff"] = indicators(cov[last], w_mode, pop).n_options.to_numpy()
    for c, val in options_by_type(cov[last], offer["type"]).items():
        out[f"{c}_{last}"] = val.to_numpy()
    out.to_parquet(city_processed("access_cells.parquet"))

    comp = {"ville": current_city(), "rayon_m": r, "carreaux": len(cells), "points_offre": len(offer),
            "jour_type_gtfs": s["offer"]["typical_weekday"], **times}
    for v in versions:
        comp[v] = summary(cov[v], w, pop, offer, {"v1": "buffer", "v2": "réseau"}[v])
    comp["part_pop_couverte_par_type"] = {t: {v: coverage_by_type(cov[v], offer, pop)[t] for v in versions}
                                          for t in sorted(offer["type"].unique())}
    comp[f"options_moyennes_{last}_sans_poids_ff"] = round(
        float((out[f"n_options_{last}_sans_poids_ff"] * pop).sum() / pop.sum()), 2)
    ff = (offer["sous_type"] == "zone_free_floating").to_numpy()
    c_last = cov[last].astype(float)
    comp[f"part_options_free_floating_{last}"] = {
        "avec_poids": round(float((c_last[:, ff] @ w[ff] * pop).sum() / ((c_last @ w) * pop).sum()), 3),
        "sans_poids": round(float((c_last[:, ff] @ w_mode[ff] * pop).sum() / ((c_last @ w_mode) * pop).sum()), 3)}
    if with_v2:
        v1, v2 = cov["v1"], cov["v2"]
        comp["rabattement"] = snap
        comp["paires_v1_non_couvertes_v2"] = int(((v1.astype(int) - v2.astype(int)) > 0).nnz)
        comp["surestimation_paires_pct"] = round(100 * (v1.nnz - v2.nnz) / max(1, v2.nnz), 1)
        comp["surestimation_options_moyennes_pct"] = round(
            100 * (comp["v1"]["options_moyennes_par_habitant"] / comp["v2"]["options_moyennes_par_habitant"] - 1), 1)
        pts_v1, pts_v2 = out["n_points_v1"] > 0, out["n_points_v2"] > 0
        comp["pop_couverte_v1_pas_v2"] = round(float(pop[(pts_v1 & ~pts_v2).to_numpy()].sum()))

    # Agrégat IRIS (version la plus précise disponible)
    iris = gpd.read_file(ign_gpkg("iris"), bbox=tuple(zone.to_crs(4326).total_bounds),
                         columns=["code_iris", "nom_iris", "code_insee"]).to_crs(s["crs"]["metric"])
    iris = iris[iris["code_insee"].isin(zone["code_insee"])]
    w_cols = {f"w_opt_{v}": out[f"n_options_{v}"] * out.pop_calee for v in versions}
    agg = out.assign(**w_cols, w_acc=out[f"acces_1000_{last}"] * out.pop_calee,
                     couvert=(out[f"n_points_{last}"] > 0) * out.pop_calee).groupby("code_iris").agg(
        population=("pop_calee", "sum"), menages=("men", "sum"), w_acc=("w_acc", "sum"), couvert=("couvert", "sum"),
        carreaux=("idcar_200m", "size"), **{k: (k, "sum") for k in w_cols})
    for v in versions:
        agg[f"n_options_{v}"] = agg[f"w_opt_{v}"] / agg.population
    agg[f"acces_1000_{last}"] = agg.w_acc / agg.population
    agg[f"part_pop_couverte_{last}"] = agg.couvert / agg.population
    iris = iris.merge(agg.drop(columns=["w_acc", "couvert", *w_cols]).reset_index(), on="code_iris", how="inner")
    iris.to_parquet(city_processed("access_iris.parquet"))
    comp["iris"] = len(iris)
    city_processed("access_comparaison.json").write_text(json.dumps(comp, indent=1, ensure_ascii=False), encoding="utf-8")

    # Cartes
    fig_dir = ROOT / "docs" / "figures" / current_city()
    fig_dir.mkdir(parents=True, exist_ok=True)
    vmax = float(np.nanpercentile(out.n_options_v1, 98))
    plot_map(out, "n_options_v1", "V1 buffer 400 m : options pondérées accessibles", fig_dir / "acces_v1_buffer.png", zone, vmax)
    if with_v2:
        plot_map(out, "n_options_v2", "V2 réseau piéton 400 m : options pondérées accessibles", fig_dir / "acces_v2_reseau.png", zone, vmax)
        out["perte_v1_v2"] = out.n_options_v1 - out.n_options_v2
        plot_map(out, "perte_v1_v2", "Surestimation du buffer (options V1 − V2)", fig_dir / "acces_v1_moins_v2.png", zone,
                 cmap="Reds")
    plot_map(out, f"n_options_{last}_sans_poids_ff", f"{last.upper()} SANS poids réduit free-floating",
             fig_dir / f"acces_{last}_sans_poids_ff.png", zone, vmax)
    plot_map(out, f"acces_1000_{last}", f"{last.upper()}, options pour 1 000 habitants (2SFCA)", fig_dir / f"acces_{last}_2sfca.png", zone)
    plot_map(iris, f"n_options_{last}", "IRIS : options accessibles par habitant (moyenne pondérée)",
             fig_dir / f"acces_iris_{last}.png", zone)
    print(json.dumps(comp, indent=1, ensure_ascii=False))
    return comp


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    city_from_args()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ville")
    ap.add_argument("--sans-v2", action="store_true", help="V1 seulement (pas de réseau piéton)")
    build_access(with_v2=not ap.parse_args().sans_v2)
