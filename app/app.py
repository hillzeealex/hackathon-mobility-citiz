"""
Démo Streamlit : accès à la mobilité à 5 min à pied et recommandation d'implantations Citiz sous budget.

    streamlit run app/app.py

Données RÉELLES uniquement, précalculées (contrat : app/data.py) :
  France entière (data/processed/national/app/), Nantes = ville des recommandations, Grenoble = ville exemple.
Rien de lourd n'est calculé au démarrage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data import FILES, REAL, ROOT, available, city_folder, has_reco, load_all  # noqa: E402
from app.ui import colorize, deck, fmt, fr, pct, table, walk_minutes  # noqa: E402
from src.common.config import load_settings  # noqa: E402
from src.optim.costs import co2_avoided_t_per_year, load_costs  # noqa: E402
from src.optim.optimize import Problem, optimize  # noqa: E402

st.set_page_config(page_title="Accès mobilité · Citiz", layout="wide")

TYPE_COLORS = {"bus": [0, 114, 178], "tram": [213, 94, 0], "metro": [204, 121, 167], "train": [86, 86, 86],
               "telepherique": [0, 158, 115], "velo": [0, 158, 115], "trottinette": [240, 228, 66],
               "citiz": [230, 0, 126], "autopartage": [150, 0, 90]}
TYPE_LABELS = {"bus": "Bus", "tram": "Tram", "metro": "Métro", "train": "Train", "telepherique": "Téléphérique",
               "velo": "Vélo", "trottinette": "Trottinette", "citiz": "Citiz", "autopartage": "Autre autopartage (Marguerite…)"}
# opérateur lisible à partir de la source (gtfs:<jeu>, gbfs:<flux>, local:<nom>)
OPERATORS = (("naolib", "Naolib"), ("aleop", "Aléop (Région)"), ("sncf", "SNCF"), ("bacs-de-loire", "Bacs de Loire"),
             ("marguerite", "Marguerite"), ("citiz", "Citiz"), ("telepherique", "Téléphérique de la Bastille"),
             ("reseau-tag", "M réso (TAG)"), ("tougo", "Tougo"), ("voironnais", "Pays Voironnais"),
             ("cars-region-isere", "Cars Région Isère"), ("voi-", "Voi"))
VIEWS = {"France entière": None, "Nantes Métropole (recommandations)": "nantes", "Grenoble (ville exemple)": "grenoble"}
MIN_MENAGES = 11
TO_WGS84 = Transformer.from_crs(2154, 4326, always_xy=True)
FIG = ROOT / "docs" / "figures"
DEMO = {"budget": 500_000, "equity": 0.5, "method": "glouton"}       # bouton « Scénario démo »
PRECALC = (250_000, 500_000, 1_000_000)                               # budgets lus directement (build_reco)


def operator(source: str) -> str:
    return next((name for key, name in OPERATORS if key in str(source)), str(source).split(":")[-1])


# ---------------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des données précalculées…")
def data(folder: str) -> dict:
    d = load_all(Path(folder))
    for k in ("cells", "iris", "offer_served", "candidates"):
        if k in d:
            d[k + "_wgs"] = d[k].to_crs(4326)
    return d


@st.cache_resource
def problem(folder: str) -> Problem:
    d = data(folder)
    return Problem(d["coverage"], d["cells"].drop(columns="geometry"), d["candidates"].drop(columns="geometry"))


@st.cache_data
def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data
def precomputed(folder: str, version: str, budget: int, equity: float, method: str):
    """Scénario déjà calculé par build_reco (lecture instantanée) ; None s'il n'existe pas pour ces réglages."""
    resume = read_json(Path(folder) / f"reco_resume_{version}.json")
    csv = Path(folder) / f"recommandations_{method}_{budget}_{version}.csv"
    if not resume or abs(resume.get("equite", -1) - equity) > 1e-9 or not csv.exists():
        return None
    sc = next((s for s in resume["scenarios"] if s["budget_eur"] == budget and s["methode"].lower() == method), None)
    if sc is None:
        return None
    sel = pd.read_csv(csv, sep=";", decimal=",", encoding="utf-8-sig")
    summary = {"pop_nouvellement_desservie": sc["habitants_nouvellement_couverts"], "cout_total": sc["cout_total_eur"],
               "methode": sc["methode"], "statut": sc["statut"], "duree_s": sc["duree_s"]}
    return sel, summary


@st.cache_data(show_spinner="Calcul en cours… (quelques secondes)")
def live(folder: str, budget: float, equity: float, method: str):
    r = optimize(problem(folder), budget, equity, method=method, **({"time_limit": 20} if method == "ilp" else {}))
    return r.selection, r.summary


def demo_scenario() -> None:
    st.session_state.update(DEMO)


# ---------------------------------------------------------------------------------------------
view = st.sidebar.radio("Vue", list(VIEWS),
                        help="France : accessibilité à vol d'oiseau de tous les carreaux habités. "
                             "Nantes : diagnostic et recommandations. Grenoble : ville exemple (marche réelle, validation).")
if VIEWS[view] is None:
    from app.national import render
    render()
    st.stop()

ville = VIEWS[view]
folder = city_folder(ville)
if not available(folder):
    missing = [f for f in FILES if not (folder / f).exists()]
    st.error(f"Données de {ville} absentes ({', '.join(missing)} dans `data/processed/{ville}/`). "
             f"Les reconstruire : `python -m scripts.build_all --ville {ville}` (≈ 5 min), ou télécharger la Release "
             "« donnees-v2 » du dépôt (voir docs/RECUPERER_LES_DONNEES.md).")
    st.stop()
d = data(str(folder))
meta = d["meta"]
version = meta.get("version_acces", "v1")
reco = has_reco(folder)
if reco:
    st.sidebar.button("▶ Scénario démo (500 000 €)", on_click=demo_scenario, width="stretch",
                      help="Remet l'onglet « Où investir ? » sur le scénario de référence : 500 000 €, équité 0,5, glouton.")
st.sidebar.caption(f"{meta.get('zone', '')} · accessibilité {'V2 marche réelle' if version == 'v2' else 'V1 vol d’oiseau'}"
                   f" · GTFS du {meta.get('jour_type_gtfs', '?')}")

st.title(f"{meta.get('zone', ville)} : qui a accès à une option de mobilité à 5 minutes à pied ?")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · Carte d'accès", "2 · Offre et population desservie", "3 · Où investir ?",
                                        "4 · Validation", "5 · Méthode et limites"])
cells = d["cells"]
pop = cells.population.sum()
covered_pop = cells.loc[cells.couvert_citiz_station, "population"].sum()

# --- Onglet 1 --------------------------------------------------------------------------------
with tab1:
    st.markdown("**Cette carte montre** combien d'options de mobilité (bus, tram, vélo, trottinette, voiture partagée) "
                "chaque habitant trouve à moins de 5 minutes à pied de chez lui, en marche réelle sur les rues et chemins.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Habitants", fmt(pop))
    c2.metric("Avec au moins une option à 5 min", pct(cells.loc[cells.n_options > 0, "population"].sum() / pop))
    c3.metric("Options par habitant (pondérées)", fr((cells.n_options * cells.population).sum() / pop, 1),
              help="Chaque option compte selon son mode et sa fréquence : un tram toutes les 5 min pèse plus qu'un car rare.")
    c4.metric("Déjà à 5 min d'un autopartage", pct(covered_pop / pop))
    c0, c00 = st.columns(2)
    scale = c0.radio("Échelle", ["IRIS (recommandé)", "Carreaux 200 m"], horizontal=True)
    indic = c00.radio("Indicateur", ["Options pondérées par habitant", "Options pour 1 000 habitants (2SFCA)"],
                      horizontal=True, help="Principal : options de mobilité pondérées (mode, fréquence) accessibles à "
                                            "5 min. 2SFCA : offre rapportée au nombre d'habitants qui se la partagent.")
    col = "n_options" if indic.startswith("Options pondérées") else "score_acces"
    if scale.startswith("IRIS"):
        g = d["iris_wgs"].copy()
        g["lieu"] = g["nom"]
    else:
        g = d["cells_wgs"].copy()
        hidden = int((g.menages < MIN_MENAGES).sum())
        g = g[g.menages >= MIN_MENAGES]
        g["lieu"] = "Carreau de 200 m"
        st.caption(f"{fmt(hidden)} carreaux de moins de {MIN_MENAGES} ménages ne sont pas affichés isolément "
                   "(secret statistique) ; ils restent comptés dans les quartiers IRIS.")
    g["color"] = colorize(g[col])
    g["val_txt"] = g[col].map(lambda v: fr(v, 1))
    g["pop_txt"] = g.population.map(fmt)
    layer = pdk.Layer("GeoJsonLayer", g[["lieu", "val_txt", "pop_txt", "color", "geometry"]].__geo_interface__,
                      get_fill_color="properties.color", get_line_color=[255, 255, 255, 60], line_width_min_pixels=0.3,
                      opacity=0.75, pickable=True)
    st.pydeck_chart(deck([layer], g, f"<b>{{lieu}}</b><br/>{indic} : {{val_txt}}<br/>Habitants : {{pop_txt}}"))
    st.caption("Couleur : du bleu (moins d'options) au rouge (plus d'options). Les zones bleues signalent un "
               "**potentiel d'amélioration**, pas un jugement sur le quartier."
               + (" Accessibilité **à vol d'oiseau** : borne haute, la marche réelle donne moins d'accès "
                  "(voir l'onglet Validation)." if version == "v1" else "")
               + " Limite : seul l'autopartage publié en open data est visible (Citiz, Marguerite) ; Getaround et "
                 "les voitures entre particuliers n'apparaissent pas.")

# --- Onglet 2 --------------------------------------------------------------------------------
with tab2:
    st.markdown("**Cette carte montre** chaque arrêt de transport en commun et chaque station de vélos ou de voitures "
                "partagées, avec le nombre d'habitants qui vivent à moins de 5 minutes à pied.")
    o_all = d["offer_served_wgs"]
    o_all = o_all[o_all["dans_zone"]].copy() if "dans_zone" in o_all else o_all.copy()
    tc = o_all["type"].isin(["bus", "tram", "metro", "train", "telepherique"])
    cs = o_all["type"].isin(["citiz", "autopartage"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Arrêts de transport en commun", fmt(tc.sum()))
    m2.metric("Stations d'autopartage", fmt(cs.sum()), help=" · ".join(
        f"{TYPE_LABELS[t]} : {n}" for t, n in o_all.loc[cs, "type"].value_counts().items()))
    m3.metric("Vélos et trottinettes (stations ou zones)", fmt((~tc & ~cs).sum()))
    m4.metric("Habitants avec une seule option à 5 min", fmt(o_all["pop_seule_option"].sum()),
              help="Habitants pour qui ce point est la seule option de mobilité à 5 minutes à pied.")
    types = st.multiselect("Types", sorted(o_all["type"].unique()), default=sorted(o_all["type"].unique()),
                           format_func=lambda t: TYPE_LABELS.get(t, t))
    o = o_all[o_all["type"].isin(types)].copy()
    o["color"] = o["type"].map(lambda t: TYPE_COLORS.get(t, [100, 100, 100]))
    o["type_txt"] = o["type"].map(lambda t: TYPE_LABELS.get(t, t))
    o["operateur"] = o["source"].map(operator)
    o["nom"] = o["nom"].fillna("Point sans nom")
    o["pop_txt"] = o.pop_desservie.map(fmt)
    o["seul_txt"] = o.pop_seule_option.map(fmt)
    o["lon"], o["lat"] = o.geometry.x, o.geometry.y
    layer = pdk.Layer("ScatterplotLayer", o.drop(columns="geometry"), get_position=["lon", "lat"], get_fill_color="color",
                      get_radius=45, radius_min_pixels=2, pickable=True, opacity=0.85)
    st.pydeck_chart(deck([layer], d["offer_served_wgs"], "<b>{nom}</b><br/>{type_txt} · opérateur : {operateur}"
                                                          "<br/>Habitants à 5 min : {pop_txt}"
                                                          "<br/>Dont sans aucune autre option : {seul_txt}"))
    st.caption(" · ".join(f"<span style='color:rgb{tuple(TYPE_COLORS.get(t, [100]*3))}'>●</span> {TYPE_LABELS.get(t, t)}"
                          for t in types), unsafe_allow_html=True)
    cov_by_type = pd.read_csv(folder / "served_by_type.csv") if (folder / "served_by_type.csv").exists() else None
    if cov_by_type is not None:
        st.subheader("Population desservie par type d'offre")
        t = cov_by_type.assign(type=cov_by_type["type"].map(lambda x: TYPE_LABELS.get(x, x)))
        t = t.rename(columns={"type": "Type", "points_dans_zone": "Points", "pop_desservie": "Habitants à 5 min",
                              "part_pop_desservie": "Part de la population", "pop_mediane_par_point": "Habitants par point (médiane)"})
        st.dataframe(table(t, digits={"Points": 0, "Habitants à 5 min": 0, "Habitants par point (médiane)": 0},
                           percent={"Part de la population": 1}), width="stretch", hide_index=True)
    st.subheader("Points dont dépendent le plus d'habitants (seule option à 5 min)")
    top = (o.nlargest(10, "pop_seule_option")[["nom", "type_txt", "operateur", "pop_desservie", "pop_seule_option"]]
           .rename(columns={"nom": "Nom", "type_txt": "Type", "operateur": "Opérateur", "pop_desservie": "Habitants à 5 min",
                            "pop_seule_option": "Habitants sans autre option"}))
    st.dataframe(table(top, digits={"Habitants à 5 min": 0, "Habitants sans autre option": 0}), width="stretch", hide_index=True)

# --- Onglet 3 --------------------------------------------------------------------------------
with tab3:
    if not reco:
        st.info("Les recommandations d'implantation sont calculées pour **Nantes Métropole** (notre ville). "
                "Grenoble sert d'exemple méthodologique et de test à l'aveugle du modèle (onglet Validation).")
    else:
        st.markdown("**Cette carte montre** où ajouter des stations Citiz pour qu'un maximum d'habitants, en priorité "
                    "ceux qui ont peu d'alternatives, se retrouvent à 5 minutes à pied d'une voiture partagée, "
                    "dans la limite du budget choisi.")
        for k, v in DEMO.items():
            st.session_state.setdefault(k, v)
        left, right = st.columns([1, 3])
        with left:
            budget = st.select_slider("Budget (€)", list(range(50_000, 3_000_001, 50_000)), key="budget",
                                      format_func=lambda v: fmt(v, "€"),
                               help="Scénarios 250 000 €, 500 000 € et 1 000 000 € (équité 0,5) précalculés : affichage "
                                    "instantané. Autres réglages : calcul en direct.")
            equity = st.slider("Poids de l'équité", 0.0, 2.0, step=0.1, key="equity",
                               help="0 : maximise habitants nouvellement desservis × probabilité du modèle. Plus haut : "
                                    "bonus aux quartiers où les ménages sont plus modestes ou sans voiture.")
            method = st.radio("Méthode", ["glouton", "ilp"], key="method",
                              format_func={"glouton": "Glouton (instantané)", "ilp": "ILP optimal (≤ 20 s)"}.get)
            st.button("▶ Scénario démo (500 000 €)", on_click=demo_scenario, key="demo_tab")

        pre = precomputed(str(folder), version, budget, round(equity, 2), method) if budget in PRECALC else None
        sel, summary = pre if pre is not None else live(str(folder), budget, equity, method)
        sel = pd.DataFrame(sel)[["rang", "id", "nom", "x", "y", "cout", "pop_nouvellement_desservie", "usage_predit",
                                 "cout_par_habitant", "budget_cumule"]]
        cand_cols = [c for c in ("id", "origine", "commune", "dist_autopartage_m") if c in d["candidates"]]
        sel = sel.merge(d["candidates"][cand_cols], on="id", how="left")
        new_pop = summary["pop_nouvellement_desservie"]
        co2 = co2_avoided_t_per_year(len(sel))
        with right:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Stations Citiz recommandées", len(sel))
            m2.metric("Habitants nouvellement à 5 min d'un autopartage", fmt(new_pop),
                      delta=f"couverture {pct(covered_pop / pop)} → {pct((covered_pop + new_pop) / pop)}", delta_color="off",
                      help=f"Aujourd'hui : {fmt(covered_pop)} habitants à 5 min d'un autopartage ; après : "
                           f"{fmt(covered_pop + new_pop)}.")
            m3.metric("Coût par nouvel habitant desservi", fr(summary["cout_total"] / max(1, new_pop), 1, "€"),
                      help=f"Sur {load_costs()['horizon_ans']} ans (installation, véhicule, assurance, entretien).")
            m4.metric("CO₂ évité (estimation prudente)", fr(co2, 1, "t/an"),
                      help="1 véhicule par station : 10 000 km de voiture évités/an × 0,142 kgCO₂e/km (ADEME, bornes basses).")
            if not sel.empty:
                s = sel.copy()
                s["lon"], s["lat"] = TO_WGS84.transform(s.x.to_numpy(float), s.y.to_numpy(float))
                s["cout_txt"] = s.cout.map(lambda v: fmt(v, "€"))
                s["pop_txt"] = s.pop_nouvellement_desservie.map(fmt)
                s["proba_txt"] = s.usage_predit.map(lambda v: pct(v, 0))
                walk = s["dist_autopartage_m"] if "dist_autopartage_m" in s else pd.Series(float("nan"), index=s.index)
                speed = load_settings()["walk"]["speed_kmh"]
                s["marche_txt"] = walk.map(lambda m: walk_minutes(m, speed))
                ex = d["offer_served_wgs"]
                ex = ex[ex["type"].isin(["citiz", "autopartage"])].assign(lon=lambda x: x.geometry.x, lat=lambda x: x.geometry.y,
                                                                          color=lambda x: x["type"].map(TYPE_COLORS))
                layers = [pdk.Layer("ScatterplotLayer", ex.drop(columns="geometry"), get_position=["lon", "lat"],
                                    get_fill_color="color", get_radius=40, radius_min_pixels=2, opacity=0.5),
                          pdk.Layer("ScatterplotLayer", s, get_position=["lon", "lat"], get_fill_color=[230, 0, 126],
                                    get_radius=400, opacity=0.12, stroked=False),
                          pdk.Layer("ScatterplotLayer", s, get_position=["lon", "lat"], get_fill_color=[230, 0, 126],
                                    get_line_color=[0, 0, 0], line_width_min_pixels=1, stroked=True, get_radius=70,
                                    radius_min_pixels=5, pickable=True),
                          pdk.Layer("TextLayer", s, get_position=["lon", "lat"], get_text="rang", get_size=12,
                                    get_color=[0, 0, 0], get_pixel_offset=[0, -14])]
                st.pydeck_chart(deck(layers, d["candidates_wgs"], "<b>n° {rang} · {nom}</b>"
                                                                  "<br/>À {marche_txt} à pied de l'autopartage le plus proche"
                                                                  "<br/>Habitants nouvellement à 5 min : {pop_txt}"
                                                                  "<br/>Coût sur 3 ans : {cout_txt}"
                                                                  "<br/>Probabilité selon le modèle : {proba_txt}"))
                st.caption("Points numérotés : stations recommandées (halo clair ≈ 400 m). Petits points : autopartage "
                           "existant (rose : Citiz, violet : Marguerite). Un point peut sembler proche d'une station "
                           "existante à vol d'oiseau tout en étant à plus de 5 min à pied (voir l'infobulle).")
        st.subheader("Liste priorisée")
        tbl = sel.assign(origine=sel["origine"].map({"carreau": "quartier", "arret_tc": "arrêt de TC"}).fillna(sel["origine"]),
                         marche=sel.get("dist_autopartage_m", pd.Series(float("nan"), index=sel.index))
                         .map(lambda m: walk_minutes(m, load_settings()["walk"]["speed_kmh"])))
        tbl = tbl[["rang", "nom", "origine", "marche", "cout", "pop_nouvellement_desservie", "usage_predit",
                   "cout_par_habitant", "budget_cumule"]].rename(columns={
                       "rang": "Rang", "nom": "Lieu", "origine": "Emplacement", "marche": "Autopartage le plus proche (à pied)",
                       "cout": "Coût sur 3 ans (€)", "pop_nouvellement_desservie": "Habitants nouveaux",
                       "usage_predit": "Probabilité modèle", "cout_par_habitant": "€ par habitant",
                       "budget_cumule": "Budget cumulé (€)"})
        st.dataframe(table(tbl, digits={"Coût sur 3 ans (€)": 0, "Habitants nouveaux": 0, "€ par habitant": 1,
                                        "Budget cumulé (€)": 0}, percent={"Probabilité modèle": 0}),
                     width="stretch", hide_index=True)
        st.download_button("Exporter en CSV", sel.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name=f"recommandation_{ville}_{method}_{budget}.csv", mime="text/csv")
        source = ("scénario précalculé, lecture instantanée" if pre is not None
                  else f"calculé en direct en {fr(summary['duree_s'], 1)} s")
        st.caption(f"Méthode : {summary['methode']} · statut {summary['statut']} · {source} · budget utilisé "
                   f"{fmt(summary['cout_total'], '€')} sur {fmt(budget, '€')}. Coût d'une station : scénario "
                   f"« {load_costs()['scenario']} » sur {load_costs()['horizon_ans']} ans, plus un surcoût d'assurance "
                   "et d'entretien selon la commune (**hypothèse à valider avec Citiz**). Limite : la probabilité du "
                   "modèle reflète les choix d'implantation passés de Citiz, pas la demande pure.")

# --- Onglet 4 --------------------------------------------------------------------------------
with tab4:
    val = read_json(REAL / "model" / "validation.json")
    st.subheader("Le modèle retrouve-t-il les stations Citiz de Grenoble sans les avoir vues ?")
    if val and "test_aveugle_grenoble" in val:
        t = val["test_aveugle_grenoble"]
        rows = [{"Indicateur": f"Stations dont le carreau est dans le top {k} % des carreaux prédits",
                 "Modèle": pct(t["modele"]["stations"][f"top_{k}pct"]), "Densité seule": pct(t["baseline_densite"]["stations"][f"top_{k}pct"])}
                for k in (5, 10, 20)]
        rows.append({"Indicateur": "AUC (carreaux)", "Modèle": str(t["modele"]["carreaux"]["auc"]).replace(".", ","),
                     "Densité seule": str(t["baseline_densite"]["carreaux"]["auc"]).replace(".", ",")})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(f"Le modèle est entraîné sans le réseau « {t['reseau_exclu']} » ({t['stations']} stations à Grenoble, "
                   f"{t['carreaux']} carreaux). Validation sur les {val['perimetre']['reseaux']} réseaux Citiz : AUC "
                   f"{str(val['modele_oof']['auc']).replace('.', ',')} (densité seule {str(val['baseline_densite']['auc']).replace('.', ',')}). "
                   "Limite : le modèle apprend où Citiz s'est installé, pas la demande pure.")
        c1, c2 = st.columns(2)
        for c, img, cap in ((c1, FIG / "modele" / "shap_importance.png", "Importance des variables (SHAP)"),
                            (c2, FIG / "modele" / "shap_beeswarm.png", "Sens des effets (SHAP)")):
            if img.exists():
                c.image(str(img), caption=cap)
    else:
        st.info("Modèle non entraîné : `python -m src.model.features && python -m src.model.train`.")
    st.subheader("Vol d'oiseau (V1) ou marche réelle (V2) ? Grenoble")
    comp = read_json(REAL / "grenoble" / "access_comparaison.json")
    if comp and "v2" in comp:
        rows = [{"Indicateur": lab, "V1 vol d'oiseau": f(comp["v1"][k]), "V2 marche réelle": f(comp["v2"][k])}
                for lab, k, f in (("Au moins une option à 5 min", "part_pop_au_moins_1_option", pct),
                                  ("Au moins un arrêt de TC", "part_pop_au_moins_1_TC", pct),
                                  ("Une station Citiz à 5 min", "part_pop_citiz", pct),
                                  ("Options pondérées par habitant", "options_moyennes_par_habitant", lambda v: f"{v:.1f}".replace(".", ",")))]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(f"La V1 surestime les options de {str(comp['surestimation_options_moyennes_pct']).replace('.', ',')} % ; "
                   f"{fmt(comp['pop_couverte_v1_pas_v2'])} habitants semblent desservis à vol d'oiseau mais ne le sont pas "
                   "à pied (rivières, voies ferrées, îlots). Les chiffres France et Nantes (V1) sont donc des bornes hautes.")
        cols = st.columns(3)
        for c, name, cap in zip(cols, ("acces_v1_buffer", "acces_v2_reseau", "acces_v1_moins_v2"),
                                ("V1 : vol d'oiseau", "V2 : marche réelle", "Surestimation V1 − V2")):
            img = FIG / "grenoble" / f"{name}.png"
            if img.exists():
                c.image(str(img), caption=cap)
    else:
        st.info("Comparaison V1 / V2 absente : `python -m scripts.build_all --ville grenoble --v2`.")

# --- Onglet 5 --------------------------------------------------------------------------------
with tab5:
    for title, doc in (("Méthodologie", "methodologie.md"), ("Modèle", "modele.md"), ("Éthique", "ethique.md"),
                       ("Choix des villes", "choix_ville.md")):
        path = ROOT / "docs" / doc
        if path.exists():
            with st.expander(title, expanded=title == "Méthodologie"):
                st.markdown(path.read_text(encoding="utf-8"))
