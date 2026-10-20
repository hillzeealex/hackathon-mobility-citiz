"""
Chiffres clés pour les slides -> docs/chiffres_cles.md + slides/img/*.png

    python -m scripts.chiffres_cles

Chaque chiffre est LU dans un fichier produit par le pipeline (aucune saisie à la main) ; le document indique le
fichier et la commande qui le produisent. À relancer après toute reconstruction.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys

import geopandas as gpd
import matplotlib
import pandas as pd

from src.common.config import ROOT, load_settings, processed, set_city

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

IMG = ROOT / "slides" / "img"
FIG = ROOT / "docs" / "figures"
LABELS = {"france_sans_option.png": "France : part des habitants sans option à 5 min, par département (V1)",
          "grenoble_v1_vol_oiseau.png": "Grenoble : options accessibles à vol d'oiseau (V1)",
          "grenoble_v2_marche.png": "Grenoble : options accessibles à pied (V2, même échelle)",
          "grenoble_surestimation_v1.png": "Grenoble : surestimation de la V1 (V1 − V2)",
          "nantes_acces_iris.png": "Nantes : options par habitant, par IRIS (V1)",
          "nantes_acces_carreaux.png": "Nantes : options accessibles par carreau (V1)",
          "nantes_recommandations.png": "Nantes : 12 stations Citiz recommandées (500 000 €, ILP)",
          "modele_shap_importance.png": "Modèle : importance des variables (SHAP)",
          "modele_shap_effets.png": "Modèle : sens des effets (SHAP)"}
CMD = {"national": "python -m src.national.build_all", "model": "python -m src.model.features && python -m src.model.train",
       "grenoble": "python -m scripts.build_all --ville grenoble", "nantes": "python -m scripts.build_all --ville nantes",
       "equite": "python -m scripts.chiffres_cles"}


def j(*parts) -> dict:
    return json.loads(processed(*parts).read_text(encoding="utf-8"))


def fr(x, d: int = 0) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pc(x, d: int = 1) -> str:
    return f"{100 * x:.{d}f} %".replace(".", ",")


def national_map(path) -> None:
    deps = gpd.read_parquet(processed("national", "app", "departements.parquet"))
    met = deps[~deps["dep"].str.startswith("97")].to_crs(2154)
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    met.plot(ax=ax, column="part_pop_sans_option", cmap="RdYlBu_r", legend=True, edgecolor="white", linewidth=0.3,
             legend_kwds={"shrink": 0.6, "label": "Part de la population sans option à 5 min (V1)"})
    ax.set_axis_off()
    ax.set_title("Part des habitants sans aucune option de mobilité à 5 min à pied", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def equity_sensitivity(budget: int = 500_000) -> pd.DataFrame:
    """Effet du poids d'équité sur la sélection à Nantes (glouton) : qui gagne l'accès ?"""
    import numpy as np
    import scipy.sparse as sp

    from src.optim.optimize import Problem, optimize
    set_city("nantes")
    cells = gpd.read_parquet(processed("nantes", "cells.parquet"))
    cand = gpd.read_parquet(processed("nantes", "candidates.parquet"))
    cov = sp.load_npz(processed("nantes", "coverage.npz")).tocsc()
    p = Problem(cov, cells.drop(columns="geometry"), cand[["id", "type", "nom", "cout", "usage_predit", "x", "y"]])
    rows = []
    for eq in (0.0, 0.5, 2.0):
        sel = optimize(p, budget, eq, method="glouton").selection
        idx = np.flatnonzero(cand["id"].isin(sel["id"]).to_numpy())
        new = (cov[:, idx].sum(axis=1).A1 > 0) & ~cells["couvert_citiz_station"].to_numpy()
        w = cells["population"].to_numpy()[new]
        rows.append({"equite": eq, "stations": len(sel), "habitants_nouveaux": round(float(w.sum())),
                     "part_sans_voiture_nouveaux": float(np.average(cells["part_sans_voiture"].to_numpy()[new], weights=w)),
                     "priorite_moyenne_nouveaux": float(np.average(cells["priorite_equite"].to_numpy()[new], weights=w))})
    return pd.DataFrame(rows)


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    s = load_settings()
    nat, off = j("national", "agg_rapport.json")["france"], j("national", "offer_rapport.json")
    rank = pd.read_parquet(processed("national", "classement_epci.parquet"))
    g, n = j("grenoble", "access_comparaison.json"), j("nantes", "access_comparaison.json")
    gp, np_ = j("grenoble", "population_rapport.json"), j("nantes", "population_rapport.json")
    val, reco = j("model", "validation.json"), j("nantes", "reco_resume.json")
    feat = j("model", "features_rapport.json")
    served = pd.read_csv(processed("nantes", "served_by_type.csv"))
    nantes_off = gpd.read_parquet(processed("nantes", "offer_served.parquet"))
    nantes_off = nantes_off[nantes_off["dans_zone"]]
    eq = equity_sensitivity()
    imp = pd.read_csv(processed("model", "shap_importance.csv"))

    def row(name):
        r = rank[rank["nom"] == name].iloc[0]
        return r

    L = [f"# Chiffres clés (générés le {dt.date.today().strftime('%d/%m/%Y')})", "",
         "Généré par `python -m scripts.chiffres_cles` à partir des fichiers du pipeline : **ne pas modifier à la main**.",
         f"Accessibilité « 5 min à pied » = {s['walk']['radius_m']} m ({s['walk']['speed_kmh']} km/h). "
         f"Jour type des horaires de TC : mardi {s['offer']['typical_weekday']}. Population : Filosofi 2021 recalée sur le "
         "recensement 2023. V1 = vol d'oiseau (borne haute), V2 = marche réelle sur le réseau OpenStreetMap.", "",
         "## 1. France entière (V1)", "",
         "| Chiffre | Valeur | Source (fichier · commande) |", "|---|---:|---|",
         f"| Habitants couverts (carreaux de 200 m) | {fr(nat['population'])} | `data/processed/national/agg_rapport.json` · `{CMD['national']}` |",
         f"| Sans aucune option à 5 min | **{pc(nat['part_pop_sans_option'])}** | idem |",
         f"| À 5 min d'un arrêt de transport en commun | {pc(nat['part_pop_avec_tc'])} | idem |",
         f"| À 5 min d'une station Citiz | {pc(nat['part_pop_citiz_5min'])} | idem |",
         f"| Options pondérées par habitant | {fr(nat['n_options_moyen'], 2)} | idem |",
         f"| Points d'offre (après dédoublonnage) | {fr(off['points_apres'])} (sur {fr(off['points_avant'])}) | `national/offer_rapport.json` · idem |",
         f"| Flux GTFS lus | {off['flux_gtfs']} ({off['flux_gtfs_en_erreur']} illisibles, {off['flux_gtfs_hors_periode']} lus sur leur dernier mardi valide) | idem |",
         ""]
    L += ["## 2. Choix des villes (classement de 276 EPCI ≥ 50 000 hab.)", "",
          "| | Rang potentiel Citiz | Habitants | Stations Citiz | Pop. à 5 min de Citiz (V1) | Vols liés aux véhicules / 1 000 hab. |",
          "|---|---:|---:|---:|---:|---:|"]
    for name in ("Métropole Nice Côte d'Azur", "Nantes Métropole", "Grenoble-Alpes-Métropole"):
        r = row(name)
        L.append(f"| {name} | {int(r['rang_potentiel'])} | {fr(r['population'])} | {int(r['stations_citiz'])} | "
                 f"{pc(r['part_pop_citiz_5min'])} | {fr(r['vols_vehicules_1000'], 1)} |")
    L += ["", f"Source : `data/processed/national/classement_epci.parquet` · `{CMD['national']}` ; argumentaire : `docs/choix_ville.md`.", ""]
    L += ["## 3. Grenoble, ville exemple : vol d'oiseau ou marche réelle ?", "",
          "| Part de la population | V1 vol d'oiseau | V2 marche réelle |", "|---|---:|---:|",
          f"| Au moins une option à 5 min | {pc(g['v1']['part_pop_au_moins_1_option'])} | **{pc(g['v2']['part_pop_au_moins_1_option'])}** |",
          f"| Au moins un arrêt de TC | {pc(g['v1']['part_pop_au_moins_1_TC'])} | {pc(g['v2']['part_pop_au_moins_1_TC'])} |",
          f"| Une station Citiz à 5 min | {pc(g['v1']['part_pop_citiz'])} | **{pc(g['v2']['part_pop_citiz'])}** |",
          f"| Options pondérées par habitant | {fr(g['v1']['options_moyennes_par_habitant'], 1)} | {fr(g['v2']['options_moyennes_par_habitant'], 1)} |",
          "", f"- La V1 surestime les options de **{fr(g['surestimation_options_moyennes_pct'], 0)} %** ; "
          f"{fr(g['pop_couverte_v1_pas_v2'])} habitants semblent desservis à vol d'oiseau mais ne le sont pas à pied.",
          f"- {fr(gp['pop_calee'])} habitants, {fr(g['carreaux'])} carreaux habités, {fr(g['points_offre'])} points d'offre.",
          f"- Source : `data/processed/grenoble/access_comparaison.json` · `{CMD['grenoble']}`.", ""]
    t = val["test_aveugle_grenoble"]
    L += ["## 4. Modèle : où Citiz s'installe-t-il ?", "",
          f"Apprentissage : {fr(val['perimetre']['carreaux'])} carreaux des {val['perimetre']['epci']} EPCI où Citiz est présent "
          f"({fr(val['perimetre']['positifs'])} avec une station à 400 m) ; {val['perimetre']['reseaux']} réseaux régionaux Citiz.", "",
          "| Test à l'aveugle Grenoble (réseau Auvergne-Rhône-Alpes jamais vu) | Modèle | Densité seule |", "|---|---:|---:|"]
    for k in (5, 10, 20):
        L.append(f"| Vraies stations ({t['stations']}) dont le carreau est dans le top {k} % | **{pc(t['modele']['stations'][f'top_{k}pct'])}** | "
                 f"{pc(t['baseline_densite']['stations'][f'top_{k}pct'])} |")
    L += [f"| AUC (carreaux de Grenoble) | {fr(t['modele']['carreaux']['auc'], 3)} | {fr(t['baseline_densite']['carreaux']['auc'], 3)} |",
          f"| AUC, validation par réseau (15 plis) | {fr(val['modele_oof']['auc'], 3)} | {fr(val['baseline_densite']['auc'], 3)} |",
          f"| Positifs captés dans le top 10 % de chaque EPCI (moyenne) | {pc(val['capture_moyenne_par_epci']['modele']['top_10pct'])} | "
          f"{pc(val['capture_moyenne_par_epci']['baseline_densite']['top_10pct'])} |",
          "", "Variables les plus importantes (SHAP) : " + ", ".join(f"`{v}`" for v in imp["variable"].head(5)) + ".",
          f"Source : `data/processed/model/validation.json`, `shap_importance.csv` · `{CMD['model']}`. "
          "Limite : le modèle apprend où Citiz s'est installé, pas la demande pure (`docs/modele.md`).", ""]
    cit = served.set_index("type")
    L += ["## 5. Nantes Métropole, notre ville : diagnostic (V1)", "",
          "| Chiffre | Valeur | Source |", "|---|---:|---|",
          f"| Habitants | {fr(np_['pop_calee'])} | `data/processed/nantes/population_rapport.json` · `{CMD['nantes']}` |",
          f"| Au moins une option à 5 min | {pc(n['v1']['part_pop_au_moins_1_option'])} | `nantes/access_comparaison.json` |",
          f"| Options pondérées par habitant | {fr(n['v1']['options_moyennes_par_habitant'], 1)} (Grenoble V1 : {fr(g['v1']['options_moyennes_par_habitant'], 1)}) | idem |",
          f"| Stations Citiz / Marguerite | {reco['stations_autopartage_existantes']['citiz']} / {reco['stations_autopartage_existantes']['autopartage']} | `nantes/reco_resume.json` |",
          f"| À 5 min d'une station Citiz | {pc(n['v1']['part_pop_citiz'])} | `nantes/access_comparaison.json` |",
          f"| À 5 min d'un autopartage (Citiz ou Marguerite) | **{pc(reco['part_deja_couverte'])}** | `nantes/reco_resume.json` |",
          f"| Habitants par station Citiz (médiane) | {fr(cit.loc['citiz', 'pop_mediane_par_point'])} | `nantes/served_by_type.csv` |",
          f"| Habitants dont la seule option est un unique arrêt / station | {fr(nantes_off['pop_seule_option'].sum())} | `nantes/offer_served.parquet` |",
          ""]
    L += ["## 6. Nantes : recommandations Citiz (ILP, équité 0,5)", "",
          f"Candidats : {fr(reco['candidats']['carreau'])} carreaux et {fr(reco['candidats']['arret_tc'])} arrêts de TC à plus de 400 m "
          f"d'un autopartage. Coût d'une station : {fr(reco['cout_station_eur'])} € sur {3} ans (scénario moyen) + surcoût de risque "
          f"de vol (moyenne {fr(reco['surcout_risque_moyen_eur'])} €).", "",
          "| Budget | Stations | Habitants nouvellement à 5 min | Couverture autopartage | € / habitant | CO2 évité |",
          "|---:|---:|---:|---:|---:|---:|"]
    for sc in reco["scenarios"]:
        if sc["methode"] == "ILP":
            L.append(f"| {fr(sc['budget_eur'])} € | {sc['stations']} | **{fr(sc['habitants_nouvellement_couverts'])}** | "
                     f"{pc(reco['part_deja_couverte'])} → {pc(sc['part_population_couverte_apres'])} | {fr(sc['eur_par_habitant'], 1)} | "
                     f"{fr(sc['co2_evite_t_an'], 1)} t/an |")
    gl = {sc["budget_eur"]: sc for sc in reco["scenarios"] if sc["methode"] == "glouton"}
    il = {sc["budget_eur"]: sc for sc in reco["scenarios"] if sc["methode"] == "ILP"}
    L += ["", "Glouton vs ILP (habitants nouvellement couverts) : " + " ; ".join(
        f"{fr(b)} € : {fr(gl[b]['habitants_nouvellement_couverts'])} vs {fr(il[b]['habitants_nouvellement_couverts'])}" for b in il) + ".",
          f"Source : `data/processed/nantes/reco_resume.json`, `recommandations_ilp_<budget>.csv` · `{CMD['nantes']}`. "
          "CO2 : estimation prudente ADEME (10 000 km évités/véhicule/an × 0,142 kgCO2e/km), 1 véhicule par station.", "",
          "Effet du poids d'équité (500 000 €, glouton) :", "",
          "| Poids d'équité | Stations | Habitants nouveaux | Part de ménages sans voiture chez les nouveaux | Priorité d'équité moyenne |",
          "|---:|---:|---:|---:|---:|"]
    for r in eq.itertuples():
        L.append(f"| {fr(r.equite, 1)} | {r.stations} | {fr(r.habitants_nouveaux)} | {pc(r.part_sans_voiture_nouveaux)} | {fr(r.priorite_moyenne_nouveaux, 2)} |")
    if eq["habitants_nouveaux"].nunique() == 1:
        L += ["", "Lecture : la sélection ne change pas avec le poids d'équité. À Nantes, les poches denses non couvertes "
              "autour du centre sont aussi celles où vivent le plus de ménages pauvres ou sans voiture : efficacité et "
              f"équité vont dans le même sens (priorité d'équité moyenne des nouveaux couverts {fr(eq['priorite_moyenne_nouveaux'].iloc[0], 2)}, "
              "contre 0,5 pour l'ensemble des carreaux)."]
    L += ["", f"Source : calcul de `{CMD['equite']}` sur `data/processed/nantes/` (cells, candidates, coverage).", ""]

    imgs = {"france_sans_option.png": None,
            "grenoble_v1_vol_oiseau.png": FIG / "grenoble" / "acces_v1_buffer.png",
            "grenoble_v2_marche.png": FIG / "grenoble" / "acces_v2_reseau.png",
            "grenoble_surestimation_v1.png": FIG / "grenoble" / "acces_v1_moins_v2.png",
            "nantes_acces_iris.png": FIG / "nantes" / "acces_iris_v1.png",
            "nantes_acces_carreaux.png": FIG / "nantes" / "acces_v1_buffer.png",
            "nantes_recommandations.png": FIG / "nantes" / "reco_stations.png",
            "modele_shap_importance.png": FIG / "modele" / "shap_importance.png",
            "modele_shap_effets.png": FIG / "modele" / "shap_beeswarm.png"}
    national_map(IMG / "france_sans_option.png")
    L += ["## 7. Images pour les slides (`slides/img/`)", "", "| Image | Contenu | Produite par |", "|---|---|---|"]
    for name, src in imgs.items():
        if src is not None:
            shutil.copy2(src, IMG / name)
        origin = (f"`{src.relative_to(ROOT).as_posix()}` · " if src else "") + {
            "france": CMD["equite"], "grenoble": CMD["grenoble"], "nantes": CMD["nantes"], "modele": CMD["model"]}[name.split("_")[0]]
        L.append(f"| `{name}` | {LABELS[name]} | {origin} |")
    L.append("")
    (ROOT / "docs" / "chiffres_cles.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
