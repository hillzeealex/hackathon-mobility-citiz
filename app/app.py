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
from app.data import REAL, ROOT, available, city_folder, has_reco, load_all  # noqa: E402
from app.ui import colorize, deck, fmt  # noqa: E402
from src.optim.costs import co2_avoided_t_per_year, load_costs  # noqa: E402
from src.optim.optimize import Problem, optimize  # noqa: E402

st.set_page_config(page_title="Accès mobilité · Citiz", layout="wide")

TYPE_COLORS = {"bus": [0, 114, 178], "tram": [213, 94, 0], "metro": [204, 121, 167], "train": [86, 86, 86],
               "telepherique": [0, 158, 115], "velo": [0, 158, 115], "trottinette": [240, 228, 66],
               "citiz": [230, 0, 126], "autopartage": [150, 0, 90]}
TYPE_LABELS = {"bus": "Bus", "tram": "Tram", "metro": "Métro", "train": "Train", "telepherique": "Téléphérique",
               "velo": "Vélo", "trottinette": "Trottinette", "citiz": "Citiz", "autopartage": "Autre autopartage (Marguerite…)"}
VIEWS = {"France entière": None, "Nantes Métropole (recommandations)": "nantes", "Grenoble (ville exemple)": "grenoble"}
MIN_MENAGES = 11
TO_WGS84 = Transformer.from_crs(2154, 4326, always_xy=True)
FIG = ROOT / "docs" / "figures"


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


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(v, digits: int = 1) -> str:
    return "n.d." if v is None else f"{100 * v:.{digits}f} %".replace(".", ",")


# ---------------------------------------------------------------------------------------------
view = st.sidebar.radio("Vue", list(VIEWS),
                        help="France : accessibilité V1 (vol d'oiseau) de tous les carreaux habités. "
                             "Nantes : diagnostic et recommandations. Grenoble : ville exemple (marche réelle, validation).")
if VIEWS[view] is None:
    from app.national import render
    render()
    st.stop()

ville = VIEWS[view]
folder = city_folder(ville)
if not available(folder):
    st.error(f"Données de {ville} absentes : lancer `python -m scripts.build_all --ville {ville}`.")
    st.stop()
d = data(str(folder))
meta = d["meta"]
version = meta.get("version_acces", "v1")
st.sidebar.caption(f"{meta.get('zone', '')} · accessibilité {'V2 marche réelle' if version == 'v2' else 'V1 vol d’oiseau'}"
                   f" · GTFS du {meta.get('jour_type_gtfs', '?')}")

st.title(f"{meta.get('zone', ville)} : qui a accès à une option de mobilité à 5 minutes à pied ?")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · Carte d'accès", "2 · Offre et population desservie", "3 · Où investir ?",
                                        "4 · Validation", "5 · Méthode et limites"])

# --- Onglet 1 --------------------------------------------------------------------------------
with tab1:
    c0, c00 = st.columns(2)
    scale = c0.radio("Échelle", ["IRIS (recommandé)", "Carreaux 200 m"], horizontal=True)
    indic = c00.radio("Indicateur", ["Options pondérées par habitant", "Options pour 1 000 habitants (2SFCA)"],
                      horizontal=True, help="Principal : options de mobilité pondérées (mode, fréquence) accessibles à "
                                            "5 min. 2SFCA : offre rapportée à la demande concurrente.")
    col = "n_options" if indic.startswith("Options pondérées") else "score_acces"
    if scale.startswith("IRIS"):
        g = d["iris_wgs"].copy()
        label = "nom"
    else:
        g = d["cells_wgs"].copy()
        hidden = int((g.menages < MIN_MENAGES).sum())
        g = g[g.menages >= MIN_MENAGES]
        label = "id"
        st.caption(f"{hidden} carreaux de moins de {MIN_MENAGES} ménages ne sont pas affichés isolément "
                   "(secret statistique) ; ils restent comptés dans les agrégats IRIS.")
    g["color"] = colorize(g[col])
    g["val_txt"] = g[col].round(1).astype(str).str.replace(".", ",", regex=False)
    g["pop_txt"] = g.population.round(0).astype(int).astype(str)
    cells = d["cells"]
    pop = cells.population.sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Habitants (carreaux habités)", fmt(pop))
    c2.metric("Avec ≥ 1 option à 5 min", f"{100 * cells.loc[cells.n_options > 0, 'population'].sum() / pop:.1f} %".replace(".", ","))
    c3.metric("Options pondérées par habitant", f"{(cells.n_options * cells.population).sum() / pop:.1f}".replace(".", ","))
    c4.metric("Déjà à 5 min d'un autopartage", f"{100 * cells.loc[cells.couvert_citiz_station, 'population'].sum() / pop:.1f} %"
              .replace(".", ","))
    layer = pdk.Layer("GeoJsonLayer", g[[label, "val_txt", "pop_txt", "color", "geometry"]].__geo_interface__,
                      get_fill_color="properties.color", get_line_color=[255, 255, 255, 60], line_width_min_pixels=0.3,
                      opacity=0.75, pickable=True)
    st.pydeck_chart(deck([layer], g, f"<b>{{{label}}}</b><br/>{indic} : {{val_txt}}<br/>Habitants : {{pop_txt}}"))
    st.caption("Couleur : du plus froid (moins d'options) au plus chaud. Les zones froides signalent un "
               "**potentiel d'amélioration**, pas un jugement sur le territoire."
               + (" Accessibilité **V1 (vol d'oiseau)** : borne haute, la marche réelle est plus courte d'accès "
                  "(voir l'onglet Validation)." if version == "v1" else ""))

# --- Onglet 2 --------------------------------------------------------------------------------
with tab2:
    o = d["offer_served_wgs"]
    o = o[o["dans_zone"]].copy() if "dans_zone" in o else o.copy()
    types = st.multiselect("Types", sorted(o["type"].unique()), default=sorted(o["type"].unique()),
                           format_func=lambda t: TYPE_LABELS.get(t, t))
    o = o[o["type"].isin(types)]
    o["color"] = o["type"].map(lambda t: TYPE_COLORS.get(t, [100, 100, 100]))
    o["type_txt"] = o["type"].map(lambda t: TYPE_LABELS.get(t, t))
    o["pop_txt"] = o.pop_desservie.round(0).astype(int).astype(str)
    o["seul_txt"] = o.pop_seule_option.round(0).astype(int).astype(str)
    o["lon"], o["lat"] = o.geometry.x, o.geometry.y
    layer = pdk.Layer("ScatterplotLayer", o.drop(columns="geometry"), get_position=["lon", "lat"], get_fill_color="color",
                      get_radius=45, radius_min_pixels=2, pickable=True, opacity=0.85)
    st.pydeck_chart(deck([layer], d["offer_served_wgs"], "<b>{nom}</b> ({type_txt})<br/>Habitants à 5 min : {pop_txt}"
                                                          "<br/>Dont sans aucune autre option : {seul_txt}"))
    st.caption(" · ".join(f"<span style='color:rgb{tuple(TYPE_COLORS.get(t, [100]*3))}'>●</span> {TYPE_LABELS.get(t, t)}"
                          for t in types), unsafe_allow_html=True)
    cov_by_type = pd.read_csv(folder / "served_by_type.csv") if (folder / "served_by_type.csv").exists() else None
    if cov_by_type is not None:
        st.subheader("Population desservie par type d'offre")
        t = cov_by_type.assign(type=cov_by_type["type"].map(lambda x: TYPE_LABELS.get(x, x)),
                               part_pop_desservie=(100 * cov_by_type["part_pop_desservie"]).round(1))
        st.dataframe(t.rename(columns={"type": "Type", "points_dans_zone": "Points", "pop_desservie": "Habitants à 5 min",
                                       "part_pop_desservie": "% de la population",
                                       "pop_mediane_par_point": "Habitants par point (médiane)"}),
                     width="stretch", hide_index=True)
    st.subheader("Points dont dépendent le plus d'habitants (seule option à 5 min)")
    st.dataframe(o.nlargest(10, "pop_seule_option")[["nom", "type_txt", "pop_desservie", "pop_seule_option"]]
                 .rename(columns={"type_txt": "type", "pop_desservie": "habitants à 5 min",
                                  "pop_seule_option": "habitants sans autre option"}).round(0),
                 width="stretch", hide_index=True)

# --- Onglet 3 --------------------------------------------------------------------------------
with tab3:
    if not has_reco(folder):
        st.info("Les recommandations d'implantation sont calculées pour **Nantes Métropole** (notre ville). "
                "Grenoble sert d'exemple méthodologique et de test à l'aveugle du modèle (onglet Validation).")
    else:
        p = problem(str(folder))
        left, right = st.columns([1, 3])
        with left:
            budget = st.slider("Budget (€)", 50_000, 3_000_000, 500_000, step=50_000, format="%d €")
            equity = st.slider("Poids de l'équité", 0.0, 2.0, float(meta.get("equite_par_defaut", 0.5)), 0.1,
                               help="0 : maximise habitants nouvellement desservis × probabilité du modèle. Plus haut : "
                                    "bonus aux carreaux à ménages pauvres ou sans voiture.")
            method = st.radio("Méthode", ["glouton", "ilp"], format_func={"glouton": "Glouton (instantané)",
                                                                          "ilp": "ILP optimal (≤ 20 s)"}.get)

        @st.cache_data(show_spinner="Optimisation…")
        def run(folder: str, budget: float, equity: float, method: str):
            r = optimize(problem(folder), budget, equity, method=method, **({"time_limit": 20} if method == "ilp" else {}))
            return r.selection, r.summary

        sel, summary = run(str(folder), budget, equity, method)
        sel = sel.merge(d["candidates"][["id", "origine", "commune"]], on="id", how="left")
        co2 = co2_avoided_t_per_year(len(sel))
        covered_pop = d["cells"].loc[d["cells"].couvert_citiz_station, "population"].sum()
        with right:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Stations Citiz recommandées", len(sel))
            m2.metric("Habitants nouvellement à 5 min d'un autopartage", fmt(summary["pop_nouvellement_desservie"]),
                      help=f"Aujourd'hui : {fmt(covered_pop)} habitants ({100 * covered_pop / d['cells'].population.sum():.1f} %).")
            m3.metric("Coût par nouvel habitant desservi", fmt(summary["cout_total"] / max(1, summary["pop_nouvellement_desservie"]), "€"))
            m4.metric("CO₂ évité (estimation prudente)", f"{co2:,.1f} t/an".replace(",", " ").replace(".", ","),
                      help="1 véhicule par station : 10 000 km de voiture évités/an × 0,142 kgCO₂e/km (ADEME, bornes basses).")
            if not sel.empty:
                s = pd.DataFrame(sel)
                s["lon"], s["lat"] = TO_WGS84.transform(s.x.to_numpy(float), s.y.to_numpy(float))
                s["cout_txt"] = s.cout.map(lambda v: fmt(v, "€"))
                s["pop_txt"] = s.pop_nouvellement_desservie.round(0).astype(int).astype(str)
                s["proba_txt"] = (100 * s.usage_predit).round(0).astype(int).astype(str)
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
                st.pydeck_chart(deck(layers, d["candidates_wgs"], "<b>#{rang} {nom}</b><br/>Coût (3 ans) : {cout_txt}"
                                                                  "<br/>Habitants nouvellement desservis : {pop_txt}"
                                                                  "<br/>Probabilité du modèle : {proba_txt} %"))
                st.caption("Points numérotés : stations recommandées (cercle clair = 5 min à pied). Petits points : "
                           "autopartage existant (rose : Citiz, violet : Marguerite).")
        st.subheader("Liste priorisée")
        table = sel[["rang", "nom", "origine", "cout", "pop_nouvellement_desservie", "usage_predit", "cout_par_habitant",
                     "budget_cumule"]].rename(columns={"origine": "emplacement", "pop_nouvellement_desservie": "habitants nouveaux",
                                                       "usage_predit": "probabilité modèle", "cout_par_habitant": "€ / habitant"})
        st.dataframe(table.round(2), width="stretch", hide_index=True)
        st.download_button("Exporter en CSV", sel.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name=f"recommandation_{ville}_{method}_{budget}.csv", mime="text/csv")
        st.caption(f"Méthode : {summary['methode']} · statut {summary['statut']} · {summary['duree_s']} s · "
                   f"budget utilisé {fmt(summary['cout_total'], '€')} / {fmt(budget, '€')} · coût d'une station : "
                   f"scénario « {load_costs()['scenario']} » sur {load_costs()['horizon_ans']} ans + surcoût de risque de vol "
                   "(**hypothèse à valider avec Citiz**, config/costs.yaml). Candidats : carreaux habités et arrêts de TC à plus de 5 min à pied d'un autopartage existant.")

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
