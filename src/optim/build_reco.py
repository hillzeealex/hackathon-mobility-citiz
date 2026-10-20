"""
Recommandations d'implantation de stations Citiz pour une ville -> data/processed/<ville>/

    python -m src.optim.build_reco --ville nantes [--equite 0.5] [--budgets 250000 500000 1000000]

Candidats : centroïdes des carreaux peuplés de la métropole et arrêts de TC de la zone, SAUF ceux déjà à moins de
400 m d'une station d'autopartage (Citiz, Marguerite…).
Pour chaque candidat j :
  usage_predit_j = probabilité du modèle (proba_oof : prédite sans avoir vu le réseau Citiz de la ville) au carreau
  cout_j = coût total d'une station Citiz (config/costs.yaml, horizon) + surcoût de risque de vol (commune)
Objectif (src/optim/optimize.py) : Σ population nouvellement couverte × (1 + équité × priorité) × usage relatif.
Priorité d'équité d'un carreau = moyenne des rangs-percentiles (dans la ville) de la part de ménages pauvres et de
la part de ménages sans voiture.
Sorties : candidates.parquet, coverage.npz (carreaux × candidats), cells.parquet, iris.parquet, meta.json (contrat
de l'appli, app/data.py), recommandations_<méthode>_<budget>.csv, reco_resume.json, docs/figures/<ville>/reco_*.png.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.spatial import cKDTree

from src.common.config import ROOT, city_from_args, city_processed, current_city, load_settings, study_area
from src.features.accessibility import coverage_buffer
from src.model.features import model_path
from src.optim.costs import co2_avoided_t_per_year, equipment_cost, risk_surcharge
from src.optim.optimize import Problem, optimize

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TC_TYPES = ("bus", "tram", "metro", "train", "telepherique")
CARSHARING = ("citiz", "autopartage")
KIND = "citiz_station"


def equity_priority(cells: pd.DataFrame) -> np.ndarray:
    poor = cells["part_menages_pauvres"].rank(pct=True).fillna(0.5)
    nocar = cells["part_sans_voiture"].rank(pct=True).fillna(0.5)
    return ((poor + nocar) / 2).to_numpy()


def nearest(source_xy: np.ndarray, target_xy: np.ndarray) -> np.ndarray:
    return cKDTree(source_xy).query(target_xy)[1]


def build_candidates(cells: gpd.GeoDataFrame, offer: gpd.GeoDataFrame, covered: np.ndarray, radius: float) -> gpd.GeoDataFrame:
    cxy = np.column_stack([cells.centroid.x, cells.centroid.y])
    cs = offer[offer["type"].isin(CARSHARING) & (offer["sous_type"] == "station")]
    cs_xy = np.column_stack([cs.geometry.x, cs.geometry.y])
    c = cells.loc[~covered, ["idcar_200m", "code_insee"]].assign(x=cxy[~covered, 0], y=cxy[~covered, 1],
                                                                  origine="carreau")
    c["id"] = "carreau:" + c["idcar_200m"]
    c["nom"] = "Carreau " + c["idcar_200m"].str[-14:]
    stops = offer[offer["type"].isin(TC_TYPES) & offer["dans_zone"]].copy()
    sxy = np.column_stack([stops.geometry.x, stops.geometry.y])
    far = coverage_buffer(sxy, cs_xy, radius).sum(axis=1).A1 == 0 if len(cs_xy) else np.ones(len(stops), bool)
    stops = stops[far]
    a = pd.DataFrame({"id": "arret:" + stops["id"].astype(str), "nom": stops["nom"].fillna("Arrêt") + " (" + stops["type"] + ")",
                      "x": stops.geometry.x.to_numpy(), "y": stops.geometry.y.to_numpy(), "origine": "arret_tc"})
    cand = pd.concat([c[["id", "nom", "x", "y", "origine"]], a], ignore_index=True).assign(type=KIND)
    # lieu lisible : quartier IRIS et commune du carreau le plus proche
    k = nearest(cxy, cand[["x", "y"]].to_numpy())
    iris_name = gpd.read_parquet(city_processed("access_iris.parquet")).set_index("code_iris")["nom_iris"]
    from src.ingest.zone import load_zone
    com_name = load_zone().set_index("code_insee")["nom"]
    cand["code_iris"] = cells["code_iris"].to_numpy()[k]
    cand["commune"] = cells["code_insee"].to_numpy()[k]
    cand["commune"] = cand["commune"].map(com_name)
    lieu = cand["code_iris"].map(iris_name).fillna(cand["commune"])
    is_cell = cand["origine"] == "carreau"
    cand.loc[is_cell, "nom"] = "Quartier " + lieu[is_cell] + " (" + cand.loc[is_cell, "commune"].fillna("") + ")"
    cand.loc[~is_cell, "nom"] = cand.loc[~is_cell, "nom"] + ", " + cand.loc[~is_cell, "commune"].fillna("")
    return gpd.GeoDataFrame(cand, geometry=gpd.points_from_xy(cand["x"], cand["y"]), crs=cells.crs)


def build_reco(budgets=(250_000, 500_000, 1_000_000), equity: float = 0.5, ilp_time: float = 120) -> dict:
    s = load_settings()
    r = s["walk"]["radius_m"]
    sa = study_area()
    cells = gpd.read_parquet(city_processed("access_cells.parquet")).reset_index(drop=True)
    offer = gpd.read_parquet(city_processed("offer.parquet")).reset_index(drop=True)
    cxy = np.column_stack([cells.centroid.x, cells.centroid.y])
    covered, cs = existing_coverage(cells, offer, r)

    cand = build_candidates(cells, offer, covered, r)
    cand_xy = cand[["x", "y"]].to_numpy()

    # probabilité du modèle (hors réseau de la ville) et risque de vol au carreau le plus proche
    pred = pd.read_parquet(model_path("predictions.parquet"),
                           columns=["idcar_200m", "code_epci", "x", "y", "proba", "proba_oof", "cible_citiz_400m"])
    pred = pred[pred["code_epci"] == sa["epci_siren"]].reset_index(drop=True)
    feat = pd.read_parquet(model_path("features.parquet"), columns=["idcar_200m", "reseau_citiz", "cible_citiz_400m",
                                                                     "vols_vehicules_1000"])
    ref_risk = float(feat.loc[feat["reseau_citiz"].notna() & (feat["cible_citiz_400m"] == 1), "vols_vehicules_1000"].median())
    pred = pred.merge(feat[["idcar_200m", "vols_vehicules_1000"]], on="idcar_200m", how="left")
    k = nearest(pred[["x", "y"]].to_numpy(), cand_xy)
    proba = pred["proba_oof"].fillna(pred["proba"]).to_numpy()
    cand["usage_predit"] = proba[k]
    cand["vols_vehicules_1000"] = pred["vols_vehicules_1000"].to_numpy()[k]
    base_cost = equipment_cost(KIND)["total"]
    cand["surcout_risque"] = risk_surcharge(cand["vols_vehicules_1000"] / ref_risk)
    cand["cout"] = base_cost + cand["surcout_risque"]

    cov = coverage_buffer(cxy, cand_xy, r)
    cells_p = pd.DataFrame({"population": cells["pop_calee"].to_numpy(float), "priorite_equite": equity_priority(cells),
                            f"couvert_{KIND}": covered})
    problem = Problem(cov, cells_p, cand[["id", "type", "nom", "cout", "usage_predit", "x", "y"]])

    pop_total = cells_p["population"].sum()
    resume = {"ville": current_city(), "date": dt.date.today().isoformat(), "rayon_m": r, "equite": equity,
              "carreaux": len(cells), "population": round(pop_total),
              "population_deja_couverte_autopartage": round(float(cells_p.loc[covered, "population"].sum())),
              "part_deja_couverte": round(float(cells_p.loc[covered, "population"].sum() / pop_total), 4),
              "stations_autopartage_existantes": {t: int((cs["type"] == t).sum()) for t in CARSHARING},
              "candidats": {o: int((cand["origine"] == o).sum()) for o in ("carreau", "arret_tc")},
              "cout_station_eur": round(base_cost), "taux_vols_reference": round(ref_risk, 2),
              "surcout_risque_moyen_eur": round(float(cand["surcout_risque"].mean())), "scenarios": []}
    selections = {}
    for budget in budgets:
        for method in ("glouton", "ilp"):
            kw = {"time_limit": ilp_time, "gap": 0.005} if method == "ilp" else {}
            res = optimize(problem, budget, equity=equity, method=method, **kw)
            sel = res.selection
            new_pop = float(sel["pop_nouvellement_desservie"].sum())
            chosen = sel["id"]
            prio = cells_p["priorite_equite"].to_numpy()
            newly = (cov[:, np.flatnonzero(cand["id"].isin(chosen).to_numpy())].sum(axis=1).A1 > 0) & ~covered
            sc = {"budget_eur": budget, "methode": res.summary.get("methode", method), "statut": res.summary.get("statut"),
                  "duree_s": res.summary.get("duree_s"), "stations": len(sel),
                  "dont_arrets_tc": int(sel["id"].str.startswith("arret:").sum()),
                  "cout_total_eur": round(float(sel["cout"].sum())),
                  "habitants_nouvellement_couverts": round(new_pop),
                  "part_population_couverte_apres": round(float((cells_p.loc[covered, "population"].sum() + new_pop) / pop_total), 4),
                  "eur_par_habitant": round(float(sel["cout"].sum() / new_pop), 1) if new_pop else None,
                  "co2_evite_t_an": round(co2_avoided_t_per_year(len(sel)), 1),
                  "priorite_equite_moyenne_nouveaux": round(float(np.average(prio[newly], weights=cells_p["population"].to_numpy()[newly])), 3)
                  if newly.any() else None,
                  "objectif": round(float(res.summary.get("objectif", sel["gain_objectif"].sum())), 1)}
            resume["scenarios"].append(sc)
            out = sel.merge(cand[["id", "origine", "commune", "code_iris", "surcout_risque", "vols_vehicules_1000"]],
                            on="id", how="left")
            out.to_csv(city_processed(f"recommandations_{method}_{budget}.csv"), sep=";", decimal=",", index=False,
                       encoding="utf-8-sig")
            selections[(method, budget)] = out
    resume["priorite_equite_moyenne_population"] = round(float(np.average(cells_p["priorite_equite"],
                                                                           weights=cells_p["population"])), 3)

    # contrat de l'application (app/data.py)
    cand.to_parquet(city_processed("candidates.parquet"))
    sp.save_npz(city_processed("coverage.npz"), cov)
    write_app_contract(cells, cells_p, covered, resume)
    city_processed("reco_resume.json").write_text(json.dumps(resume, indent=1, ensure_ascii=False), encoding="utf-8")
    plot_reco(cells, cs, covered, selections, budgets[len(budgets) // 2])
    print(json.dumps(resume, indent=1, ensure_ascii=False))
    return resume


def existing_coverage(cells: gpd.GeoDataFrame, offer: gpd.GeoDataFrame, radius: float) -> tuple[np.ndarray, gpd.GeoDataFrame]:
    cs = offer[offer["type"].isin(CARSHARING) & (offer["sous_type"] == "station")]
    cxy = np.column_stack([cells.centroid.x, cells.centroid.y])
    return coverage_buffer(cxy, np.column_stack([cs.geometry.x, cs.geometry.y]), radius).sum(axis=1).A1 > 0, cs


def build_app_files(equity: float = 0.5) -> None:
    """Fichiers de l'appli (cells, iris, meta) pour une ville sans recommandations (ex. Grenoble)."""
    cells = gpd.read_parquet(city_processed("access_cells.parquet")).reset_index(drop=True)
    offer = gpd.read_parquet(city_processed("offer.parquet"))
    covered, _ = existing_coverage(cells, offer, load_settings()["walk"]["radius_m"])
    cells_p = pd.DataFrame({"population": cells["pop_calee"].to_numpy(float), "priorite_equite": equity_priority(cells)})
    write_app_contract(cells, cells_p, covered, {"date": dt.date.today().isoformat(), "equite": equity})


def write_app_contract(cells: gpd.GeoDataFrame, cells_p: pd.DataFrame, covered: np.ndarray, resume: dict) -> None:
    v = "v2" if "n_options_v2" in cells else "v1"
    out = gpd.GeoDataFrame({"id": cells["idcar_200m"], "population": cells_p["population"], "menages": cells["men"],
                            "priorite_equite": cells_p["priorite_equite"], "n_options": cells[f"n_options_{v}"],
                            "score_acces": cells[f"acces_1000_{v}"], "code_iris": cells["code_iris"],
                            f"couvert_{KIND}": covered, "part_sans_voiture": cells["part_sans_voiture"],
                            "geometry": cells.geometry}, crs=cells.crs)
    out.to_parquet(city_processed("cells.parquet"))
    iris = gpd.read_parquet(city_processed("access_iris.parquet"))
    iris = iris.rename(columns={"nom_iris": "nom", f"n_options_{v}": "n_options", f"acces_1000_{v}": "score_acces"})
    iris[["code_iris", "nom", "population", "menages", "n_options", "score_acces", "geometry"]].to_parquet(
        city_processed("iris.parquet"))
    meta = {"zone": study_area()["name"], "ville": current_city(), "date": resume["date"], "demo": False,
            "version_acces": v, "jour_type_gtfs": load_settings()["offer"]["typical_weekday"],
            "equite_par_defaut": resume["equite"]}
    city_processed("meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")


def plot_reco(cells, cs, covered, selections, budget) -> None:
    fig_dir = ROOT / "docs" / "figures" / current_city()
    fig_dir.mkdir(parents=True, exist_ok=True)
    sel = selections[("ilp", budget)]
    from src.ingest.zone import load_zone
    fig, ax = plt.subplots(figsize=(8, 8))
    load_zone().boundary.plot(ax=ax, color="#999", lw=0.5)
    cells[~covered].plot(ax=ax, color="#dddddd", label="Carreau habité sans autopartage à 5 min")
    cells[covered].plot(ax=ax, color="#9a9a9a", label="Carreau déjà à 5 min d'un autopartage")
    minx, miny, maxx, maxy = cells.total_bounds
    ax.set_xlim(minx - 300, maxx + 300)
    ax.set_ylim(miny - 300, maxy + 300)
    ax.scatter(cs.geometry.x, cs.geometry.y, s=10, c="#333", marker="s", label="Autopartage existant (Citiz, Marguerite)")
    ax.scatter(sel["x"], sel["y"], s=110, c="#e6007e", edgecolor="white", label=f"Stations recommandées (ILP, {budget:,.0f} €)".replace(",", " "))
    for rk, x, y in zip(sel["rang"], sel["x"], sel["y"]):
        ax.annotate(str(int(rk)), (x, y), fontsize=7, ha="center", va="center", color="white")
    ax.set_axis_off()
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title(f"{study_area()['name']} : stations Citiz recommandées (gris foncé = déjà à 5 min d'un autopartage)", fontsize=10)
    fig.tight_layout()
    fig.savefig(fig_dir / "reco_stations.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    city_from_args()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ville")
    ap.add_argument("--equite", type=float, default=0.5)
    ap.add_argument("--budgets", type=float, nargs="+", default=[250_000, 500_000, 1_000_000])
    ap.add_argument("--ilp-temps", type=float, default=120)
    a = ap.parse_args()
    build_reco(tuple(int(b) for b in a.budgets), a.equite, a.ilp_temps)
