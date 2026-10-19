"""
Phase 3 : carte d'accessibilité -> data/processed/
  coverage_v1.npz, coverage_v2.npz   carreaux × points d'offre (lignes = population.parquet, colonnes = offer.parquet)
  access_cells.parquet               carreaux + indicateurs V1/V2 (A = n_options, B = acces_1000), par mode
  access_iris.parquet                agrégat IRIS (affichage public)
  access_comparaison.json            V1 vs V2, avec / sans poids free-floating
  docs/figures/acces_*.png           cartes
"""
from __future__ import annotations

import json
import sys
import time

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import scipy.sparse as sp

from src.common.config import ROOT, load_settings, processed
from src.features.accessibility import (coverage_buffer, coverage_network, indicators, offer_weights,
                                        options_by_type, weighted_share)
from src.features.network import load_walk_edges, to_graph
from src.ingest.archives import ign_gpkg
from src.ingest.zone import load_zone

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIG = ROOT / "docs" / "figures"
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


def build_access() -> dict:
    s = load_settings()
    r = s["walk"]["radius_m"]
    zone = load_zone()
    cells = gpd.read_parquet(processed("population.parquet"))
    cells = cells[cells["pop_calee"] > 0].reset_index(drop=True)
    cells.to_parquet(processed("population.parquet"))   # ordre des lignes = lignes des matrices
    offer = gpd.read_parquet(processed("offer.parquet")).reset_index(drop=True)
    pop = cells["pop_calee"].to_numpy(float)
    cxy = np.column_stack([cells.centroid.x, cells.centroid.y])
    oxy = np.column_stack([offer.geometry.x, offer.geometry.y])

    t0 = time.time()
    v1 = coverage_buffer(cxy, oxy, r)
    t_v1 = time.time() - t0
    edges = load_walk_edges()
    t0 = time.time()
    v2, snap = coverage_network(to_graph(edges), edges, cxy, oxy, r)
    t_v2 = time.time() - t0
    sp.save_npz(processed("coverage_v1.npz"), v1)
    sp.save_npz(processed("coverage_v2.npz"), v2)

    w = offer_weights(offer, s)
    # « sans poids » free-floating : chaque zone au poids normal de son mode (vélo 1, trottinette 0,5)
    w_mode = offer_weights(offer.assign(sous_type=offer["sous_type"].replace("zone_free_floating", "zone")), s)
    out = cells[["idcar_200m", "code_insee", "code_iris", "pop_calee", "ind", "men", "part_sans_voiture",
                 "niveau_vie_moyen", "part_menages_pauvres", "geometry"]].copy()
    for label, cov in (("v1", v1), ("v2", v2)):
        ind = indicators(cov, w, pop)
        out[f"n_options_{label}"] = ind.n_options.to_numpy()
        out[f"n_points_{label}"] = ind.n_points.to_numpy()
        out[f"acces_1000_{label}"] = ind.acces_1000.to_numpy()
    out["n_options_v2_sans_poids_ff"] = indicators(v2, w_mode, pop).n_options.to_numpy()
    for c, v in options_by_type(v2, offer["type"]).items():
        out[f"{c}_v2"] = v.to_numpy()
    out.to_parquet(processed("access_cells.parquet"))

    # Comparaison V1 / V2
    comp = {"rayon_m": r, "carreaux": len(cells), "points_offre": len(offer),
            "duree_v1_s": round(t_v1, 2), "duree_v2_s": round(t_v2, 1), "rabattement": snap,
            "v1": summary(v1, w, pop, offer, "buffer"), "v2": summary(v2, w, pop, offer, "réseau")}
    lost = (v1.astype(int) - v2.astype(int)) > 0
    comp["paires_v1_non_couvertes_v2"] = int(lost.nnz)
    comp["surestimation_paires_pct"] = round(100 * (v1.nnz - v2.nnz) / max(1, v2.nnz), 1)
    comp["surestimation_options_moyennes_pct"] = round(
        100 * (comp["v1"]["options_moyennes_par_habitant"] / comp["v2"]["options_moyennes_par_habitant"] - 1), 1)
    pts_v1, pts_v2 = out["n_points_v1"] > 0, out["n_points_v2"] > 0
    comp["pop_couverte_v1_pas_v2"] = round(float(pop[(pts_v1 & ~pts_v2).to_numpy()].sum()))
    by_type = {}
    for t in sorted(offer["type"].unique()):
        m = (offer["type"] == t).to_numpy()
        c1 = np.asarray(v1[:, m].sum(axis=1)).ravel() > 0
        c2 = np.asarray(v2[:, m].sum(axis=1)).ravel() > 0
        by_type[t] = {"v1": round(weighted_share(c1, pop), 3), "v2": round(weighted_share(c2, pop), 3)}
    comp["part_pop_couverte_par_type"] = by_type
    comp["options_moyennes_v2_sans_poids_ff"] = round(float((out["n_options_v2_sans_poids_ff"] * pop).sum() / pop.sum()), 2)
    ff = (offer["sous_type"] == "zone_free_floating").to_numpy()
    comp["part_options_free_floating_v2"] = {
        "avec_poids": round(float((v2[:, ff].astype(float) @ w[ff] * pop).sum() / ((v2.astype(float) @ w) * pop).sum()), 3),
        "sans_poids": round(float((v2[:, ff].astype(float) @ w_mode[ff] * pop).sum() / ((v2.astype(float) @ w_mode) * pop).sum()), 3)}

    # Agrégat IRIS
    iris = gpd.read_file(ign_gpkg("iris"), bbox=tuple(zone.to_crs(4326).total_bounds),
                         columns=["code_iris", "nom_iris", "code_insee"]).to_crs(s["crs"]["metric"])
    iris = iris[iris["code_insee"].isin(zone["code_insee"])]
    agg = out.assign(w_opt=out.n_options_v2 * out.pop_calee, w_acc=out.acces_1000_v2 * out.pop_calee,
                     w_opt1=out.n_options_v1 * out.pop_calee,
                     couvert=(out.n_points_v2 > 0) * out.pop_calee).groupby("code_iris").agg(
        population=("pop_calee", "sum"), menages=("men", "sum"), w_opt=("w_opt", "sum"), w_acc=("w_acc", "sum"),
        w_opt1=("w_opt1", "sum"), couvert=("couvert", "sum"), carreaux=("idcar_200m", "size"))
    agg["n_options_v2"] = agg.w_opt / agg.population
    agg["n_options_v1"] = agg.w_opt1 / agg.population
    agg["acces_1000_v2"] = agg.w_acc / agg.population
    agg["part_pop_couverte_v2"] = agg.couvert / agg.population
    iris = iris.merge(agg.drop(columns=["w_opt", "w_acc", "w_opt1", "couvert"]).reset_index(), on="code_iris", how="inner")
    iris.to_parquet(processed("access_iris.parquet"))
    comp["iris"] = len(iris)
    processed("access_comparaison.json").write_text(json.dumps(comp, indent=1, ensure_ascii=False), encoding="utf-8")

    # Cartes
    FIG.mkdir(parents=True, exist_ok=True)
    vmax = float(np.nanpercentile(out.n_options_v1, 98))
    plot_map(out, "n_options_v1", "V1 buffer 400 m : options pondérées accessibles", FIG / "acces_v1_buffer.png", zone, vmax)
    plot_map(out, "n_options_v2", "V2 réseau piéton 400 m : options pondérées accessibles", FIG / "acces_v2_reseau.png", zone, vmax)
    plot_map(out, "n_options_v2_sans_poids_ff", "V2 SANS poids réduit free-floating", FIG / "acces_v2_sans_poids_ff.png", zone, vmax)
    out["perte_v1_v2"] = out.n_options_v1 - out.n_options_v2
    plot_map(out, "perte_v1_v2", "Surestimation du buffer (options V1 − V2)", FIG / "acces_v1_moins_v2.png", zone,
             cmap="Reds")
    plot_map(out, "acces_1000_v2", "V2, options pour 1 000 habitants (2SFCA)", FIG / "acces_v2_2sfca.png", zone)
    plot_map(iris, "n_options_v2", "IRIS : options accessibles par habitant (moyenne pondérée)",
             FIG / "acces_iris_v2.png", zone)
    print(json.dumps(comp, indent=1, ensure_ascii=False))
    return comp


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_access()
