"""
Démo Streamlit : accès à la mobilité à 5 min à pied et recommandation d'implantations sous budget.

    streamlit run app/app.py

Ne lit que des fichiers précalculés (contrat : app/data.py). Rien de lourd n'est calculé au démarrage.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data import DEMO, REAL, ROOT, available, load_all  # noqa: E402
from app.ui import colorize, deck, fmt  # noqa: E402
from src.optim.costs import co2_avoided_t_per_year, load_costs  # noqa: E402
from src.optim.optimize import Problem, optimize  # noqa: E402

st.set_page_config(page_title="Accès mobilité · Citiz", layout="wide")

TYPE_COLORS = {"bus": [0, 114, 178], "tram": [213, 94, 0], "metro": [204, 121, 167], "train": [86, 86, 86],
               "telepherique": [0, 158, 115], "velo": [0, 158, 115], "trottinette": [240, 228, 66],
               "citiz": [230, 0, 126], "autopartage": [150, 0, 90]}
TYPE_LABELS = {"bus": "Bus", "tram": "Tram", "metro": "Métro", "train": "Train", "telepherique": "Téléphérique",
               "velo": "Vélo", "trottinette": "Trottinette", "citiz": "Citiz", "autopartage": "Autre autopartage"}
CAND_LABELS = {"citiz_station": "Station Citiz", "bus_stop": "Arrêt de bus", "bike_station": "Station vélo",
               "free_floating_zone": "Zone free-floating"}
MIN_MENAGES = 11
TO_WGS84 = Transformer.from_crs(2154, 4326, always_xy=True)


# ---------------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des données précalculées…")
def data(folder: str) -> dict:
    d = load_all(Path(folder))
    for k in ("cells", "iris", "offer_served", "candidates"):
        d[k + "_wgs"] = d[k].to_crs(4326)
    return d


@st.cache_resource
def problem(folder: str) -> Problem:
    d = data(folder)
    return Problem(d["coverage"], d["cells"].drop(columns="geometry"), d["candidates"].drop(columns="geometry"))


# ---------------------------------------------------------------------------------------------
level = st.sidebar.radio("Niveau d'analyse", ["France entière", "Zoom agglomération"],
                         help="France : accessibilité V1 (vol d'oiseau) de tous les carreaux habités. "
                              "Zoom : marche réelle, modèle et optimisation.")
if level == "France entière":
    from app.national import render
    render()
    st.stop()

folders = {"Données réelles": REAL, "Données de démonstration (factices)": DEMO}
choices = [k for k, f in folders.items() if available(f)]
if not choices:
    st.error("Aucune donnée précalculée. Lancer `python scripts/build_all.py` ou `python scripts/make_demo_data.py`.")
    st.stop()
src = st.sidebar.radio("Jeu de données", choices)
folder = str(folders[src])
d = data(folder)
st.sidebar.caption(d["meta"].get("zone", ""))
if d["meta"].get("demo"):
    st.warning("Données FACTICES : sert uniquement à valider l'ergonomie.")

st.title("Qui a accès à une option de mobilité à 5 minutes à pied ?")
tab1, tab2, tab3, tab4 = st.tabs(["1 · Carte d'accès", "2 · Offre et population desservie",
                                  "3 · Où investir ?", "4 · Méthode et limites"])

# --- Onglet 1 --------------------------------------------------------------------------------
with tab1:
    level = st.radio("Échelle", ["IRIS (recommandé)", "Carreaux 200 m"], horizontal=True)
    if level.startswith("IRIS"):
        g = d["iris_wgs"].copy()
        label = "nom"
    else:
        g = d["cells_wgs"].copy()
        hidden = int((g.menages < MIN_MENAGES).sum())
        g = g[g.menages >= MIN_MENAGES]
        label = "id"
        st.caption(f"{hidden} carreaux de moins de {MIN_MENAGES} ménages ne sont pas affichés isolément "
                   "(secret statistique) ; ils restent comptés dans les agrégats IRIS.")
    g["color"] = colorize(g.score_acces)
    g["score_txt"] = g.score_acces.round(1).astype(str)
    g["pop_txt"] = g.population.round(0).astype(int).astype(str)
    c1, c2, c3 = st.columns(3)
    pop = d["cells"].population.sum()
    c1.metric("Habitants (carreaux habités)", fmt(pop))
    c2.metric("Habitants avec ≥ 1 option à 5 min", f"{100 * d['cells'].loc[d['cells'].n_options > 0, 'population'].sum() / pop:.0f} %")
    c3.metric("Options pondérées / 1 000 hab. (médiane IRIS)", f"{d['iris'].score_acces.median():.1f}")
    layer = pdk.Layer("GeoJsonLayer", g[[label, "score_txt", "pop_txt", "color", "geometry"]].__geo_interface__,
                      get_fill_color="properties.color", get_line_color=[255, 255, 255, 60], line_width_min_pixels=0.3,
                      opacity=0.75, pickable=True)
    st.pydeck_chart(deck([layer], g, f"<b>{{{label}}}</b><br/>Options / 1 000 hab. : {{score_txt}}<br/>Habitants : {{pop_txt}}"))
    st.caption("Couleur : du plus froid (moins d'options par habitant) au plus chaud. Les zones froides signalent un "
               "**potentiel d'amélioration**, pas un jugement sur le territoire.")

# --- Onglet 2 --------------------------------------------------------------------------------
with tab2:
    o = d["offer_served_wgs"].copy()
    types = st.multiselect("Types", sorted(o.type.unique()), default=sorted(o.type.unique()),
                           format_func=lambda t: TYPE_LABELS.get(t, t))
    o = o[o.type.isin(types)]
    o["color"] = o.type.map(lambda t: TYPE_COLORS.get(t, [100, 100, 100]))
    o["type_txt"] = o.type.map(lambda t: TYPE_LABELS.get(t, t))
    o["pop_txt"] = o.pop_desservie.round(0).astype(int).astype(str)
    o["seul_txt"] = (100 * o.part_seule_option).round(0).astype(int).astype(str)
    o["lon"], o["lat"] = o.geometry.x, o.geometry.y
    layer = pdk.Layer("ScatterplotLayer", o.drop(columns="geometry"), get_position=["lon", "lat"], get_fill_color="color",
                      get_radius=45, radius_min_pixels=2, pickable=True, opacity=0.85)
    st.pydeck_chart(deck([layer], d["offer_served_wgs"], "<b>{nom}</b> ({type_txt})<br/>Habitants à 5 min : {pop_txt}"
                                                          "<br/>Dont sans autre option : {seul_txt} %"))
    st.caption(" · ".join(f"<span style='color:rgb{tuple(TYPE_COLORS.get(t, [100]*3))}'>●</span> {TYPE_LABELS.get(t, t)}"
                          for t in types), unsafe_allow_html=True)
    stats = o.groupby("type").agg(points=("id", "size"), pop_moy=("pop_desservie", "mean"),
                                  orphelins=("part_seule_option", lambda s: int((s >= 0.5).sum())))
    stats.index = stats.index.map(lambda t: TYPE_LABELS.get(t, t))
    st.dataframe(stats.rename(columns={"points": "Points", "pop_moy": "Habitants desservis (moyenne)",
                                       "orphelins": "Points « seule option » pour ≥ 50 % de leurs habitants"}).round(0),
                 width="stretch")
    st.subheader("Top 10 : habitants desservis")
    st.dataframe(o.nlargest(10, "pop_desservie")[["nom", "type_txt", "pop_desservie", "part_seule_option"]]
                 .rename(columns={"type_txt": "type", "pop_desservie": "habitants à 5 min", "part_seule_option": "part sans autre option"}),
                 width="stretch", hide_index=True)

# --- Onglet 3 --------------------------------------------------------------------------------
with tab3:
    p = problem(folder)
    left, right = st.columns([1, 3])
    with left:
        budget = st.slider("Budget (€)", 50_000, 3_000_000, 500_000, step=50_000, format="%d €")
        equity = st.slider("Poids de l'équité", 0.0, 2.0, 0.5, 0.1,
                           help="0 : maximise les habitants desservis × usage. Plus haut : bonus aux zones peu desservies "
                                "ou à faible revenu.")
        cand_types = sorted(p.candidates.type.unique())
        chosen_types = st.multiselect("Équipements", cand_types, default=cand_types, format_func=lambda t: CAND_LABELS.get(t, t))
        method = st.radio("Méthode", ["glouton", "ilp"], format_func={"glouton": "Glouton (instantané)",
                                                                      "ilp": "ILP optimal (≤ 20 s)"}.get)
    if not chosen_types:
        st.info("Choisir au moins un type d'équipement.")
        st.stop()

    @st.cache_data(show_spinner="Optimisation…")
    def run(folder: str, budget: float, equity: float, types: tuple, method: str):
        r = optimize(problem(folder), budget, equity, method=method, types=list(types),
                     **({"time_limit": 20} if method == "ilp" else {}))
        return r.selection, r.summary

    sel, summary = run(folder, budget, equity, tuple(chosen_types), method)
    n_citiz = int((sel.type == "citiz_station").sum())
    co2 = co2_avoided_t_per_year(n_citiz)
    with right:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Emplacements retenus", len(sel))
        m2.metric("Habitants nouvellement desservis", fmt(summary["pop_nouvellement_desservie"]))
        m3.metric("Coût par habitant", fmt(summary["cout_total"] / max(1, summary["pop_nouvellement_desservie"]), "€"))
        m4.metric("CO₂ évité (estimation prudente)", f"{co2:,.1f} t/an".replace(",", " "),
                  help="Stations Citiz uniquement : 10 000 km de voiture évités/véhicule/an × 0,142 kgCO₂e/km (ADEME, bornes basses).")
        if not sel.empty:
            s = pd.DataFrame(sel)
            s["lon"], s["lat"] = TO_WGS84.transform(s.x.to_numpy(float), s.y.to_numpy(float))
            s["type_txt"] = s.type.map(lambda t: CAND_LABELS.get(t, t))
            s["cout_txt"] = s.cout.map(lambda v: fmt(v, "€"))
            s["pop_txt"] = s.pop_nouvellement_desservie.round(0).astype(int).astype(str)
            s["color"] = s.type.map({"citiz_station": [230, 0, 126], "bus_stop": [0, 114, 178],
                                     "bike_station": [0, 158, 115]}).map(lambda c: c if isinstance(c, list) else [90, 90, 90])
            exist = d["offer_served_wgs"]
            exist = exist[exist.type == "citiz"].assign(lon=lambda x: x.geometry.x, lat=lambda x: x.geometry.y).drop(columns="geometry")
            layers = [pdk.Layer("ScatterplotLayer", exist, get_position=["lon", "lat"], get_fill_color=[230, 0, 126, 70],
                                get_radius=40, radius_min_pixels=2),
                      pdk.Layer("ScatterplotLayer", s, get_position=["lon", "lat"], get_fill_color="color", get_radius=400,
                                opacity=0.15, stroked=False),
                      pdk.Layer("ScatterplotLayer", s, get_position=["lon", "lat"], get_fill_color="color",
                                get_line_color=[0, 0, 0], line_width_min_pixels=1, stroked=True, get_radius=70,
                                radius_min_pixels=5, pickable=True),
                      pdk.Layer("TextLayer", s, get_position=["lon", "lat"], get_text="rang", get_size=12,
                                get_color=[0, 0, 0], get_pixel_offset=[0, -14])]
            st.pydeck_chart(deck(layers, d["candidates_wgs"], "<b>#{rang} {type_txt}</b><br/>{nom}<br/>Coût : {cout_txt}"
                                                              "<br/>Habitants nouvellement desservis : {pop_txt}"))
            st.caption("Points numérotés : emplacements recommandés (cercle clair = 5 min à pied). Points pâles : stations Citiz existantes.")
    st.subheader("Liste priorisée")
    table = sel.assign(type=sel.type.map(lambda t: CAND_LABELS.get(t, t)))[
        ["rang", "type", "nom", "cout", "pop_nouvellement_desservie", "usage_predit", "cout_par_habitant", "budget_cumule"]]
    st.dataframe(table.round(1), width="stretch", hide_index=True)
    st.download_button("Exporter en CSV", sel.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"recommandation_{method}_{budget}.csv", mime="text/csv")
    st.caption(f"Méthode : {summary['methode']} · statut {summary['statut']} · {summary['duree_s']} s · "
               f"budget utilisé {fmt(summary['cout_total'], '€')} / {fmt(budget, '€')} · "
               f"coûts : scénario « {load_costs()['scenario']} » sur {load_costs()['horizon_ans']} ans (config/costs.yaml)")

# --- Onglet 4 --------------------------------------------------------------------------------
with tab4:
    doc = ROOT / "docs" / "methodologie.md"
    if doc.exists():
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.info("docs/methodologie.md sera rédigé en phase 8. Points clés prévus :")
        st.markdown("""
- **Accessibilité** : distance de marche réelle (réseau piéton OSM), 400 m ≈ 5 min ; comparaison avec un simple buffer.
- **Indicateur** : options de mobilité pondérées par mode (et fréquence) à 5 min, pour 1 000 habitants (Filosofi 200 m).
- **Modèle** : LightGBM vs baseline, validation croisée **spatiale**, MAE / R², SHAP.
- **Optimisation** : glouton vs ILP (PuLP/HiGHS) sous contrainte de budget, couverture marginale.
- **Limites** : population fiscale 2021, coûts à valider, usage observé sur quelques jours, CO₂ estimé prudemment.
""")
