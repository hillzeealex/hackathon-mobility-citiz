"""
Application Streamlit : Diagnostic d'accès à la mobilité à 5 min à pied,
cartographie décisionnelle et recommandation d'implantations de stations Citiz sous budget.
Focus prioritaire : Nantes Métropole (Naolib × Citiz).
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.data import DEMO, REAL, ROOT, NANTES, NICE, GRENOBLE, available, load_all  # noqa: E402
from app.ui import colorize, deck, fmt  # noqa: E402
from src.optim.costs import co2_avoided_t_per_year, load_costs  # noqa: E402
from src.optim.optimize import Problem, optimize  # noqa: E402

st.set_page_config(
    page_title="Citiz × Naolib · Nantes Métropole",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Charte graphique & palettes couleurs
TYPE_COLORS = {
    "citiz": [230, 0, 126],          # Magenta Citiz officiel
    "autopartage": [160, 32, 100],   # Marguerite / Autopartage
    "tram": [213, 94, 0],            # Orange Tramway Naolib
    "bus": [0, 114, 178],            # Bleu Busway & Bus
    "velo": [0, 158, 115],           # Vert Bicloo
    "parc_relais": [230, 150, 0],    # Jaune P+R
    "telepherique": [86, 86, 86],
    "metro": [204, 121, 167],
    "train": [86, 86, 86],
    "trottinette": [240, 228, 66]
}

TYPE_LABELS = {
    "citiz": "Station Citiz (officielle)",
    "autopartage": "Autopartage Marguerite / Naolib",
    "tram": "Tramway Naolib (L1, L2, L3)",
    "bus": "Busway & Chronobus Naolib",
    "velo": "Vélos libre-service Bicloo",
    "parc_relais": "Parking-Relais P+R",
    "telepherique": "Navibus / Ferry",
    "metro": "Métro",
    "train": "Train",
    "trottinette": "Trottinette"
}

CAND_LABELS = {
    "citiz_station": "Station Citiz",
    "bus_stop": "Arrêt de bus",
    "bike_station": "Station vélo",
    "free_floating_zone": "Zone free-floating"
}

CAND_CATEGORY_COLORS = {
    "Parking-Relais P+R": [230, 140, 20],
    "Pôle Multimodal / Quartier Dense": [0, 114, 178],
    "Zone Résidentielle Dense": [180, 20, 140]
}

MIN_MENAGES = 11
TO_WGS84 = Transformer.from_crs(2154, 4326, always_xy=True)


# ---------------------------------------------------------------------------------------------
# Données en cache
# ---------------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement des données géographiques…")
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


@st.cache_data(ttl=90, show_spinner=False)
def fetch_citiz_live_status():
    """Récupère l'état en direct de la flotte Citiz Nantes Métropole depuis le backend GBFS officiel."""
    url_info = "https://backend.citiz.fr/public/provider/15/gbfs/v3.0/station_information.json"
    url_status = "https://backend.citiz.fr/public/provider/15/gbfs/v3.0/station_status.json"
    stations = []
    try:
        r_info = requests.get(url_info, timeout=5)
        r_status = requests.get(url_status, timeout=5)
        if r_info.status_code == 200 and r_status.status_code == 200:
            status_map = {s["station_id"]: s for s in r_status.json().get("data", {}).get("stations", [])}
            for s in r_info.json().get("data", {}).get("stations", []):
                sid = s["station_id"]
                st_info = status_map.get(sid, {})
                nom = s.get("name", [{"text": f"Station {sid}"}])[0].get("text") if isinstance(s.get("name"), list) else s.get("name")
                stations.append({
                    "station_id": sid,
                    "nom": nom,
                    "lat": float(s["lat"]),
                    "lon": float(s["lon"]),
                    "capacite": int(s.get("capacity", 2)),
                    "dispos": st_info.get("num_vehicles_available", 0),
                    "is_renting": st_info.get("is_renting", True),
                    "adresse": s.get("address", "")
                })
    except Exception:
        pass
    return stations


# ---------------------------------------------------------------------------------------------
# Barre latérale : navigation & configuration
# ---------------------------------------------------------------------------------------------
st.sidebar.markdown("### 🚗 **Citiz × Naolib · Mobilité**")

level = st.sidebar.radio(
    "Niveau d'analyse",
    ["Zoom agglomération", "France entière"],
    index=0,
    help="France : accessibilité V1 (vol d'oiseau) de tous les carreaux habités. Zoom : marche réelle, modèle et optimisation."
)

if level == "France entière":
    from app.national import render
    render()
    st.stop()

# Sélection des 3 villes clés du projet
city_map = {
    "Nantes Métropole (Priorité)": NANTES if available(NANTES) else REAL,
    "Nice Côte d'Azur (Réseau neuf)": NICE if available(NICE) else REAL,
    "Grenoble-Alpes Métropole (Référence)": GRENOBLE if available(GRENOBLE) else REAL
}

city_name_choice = st.sidebar.selectbox(
    "🏙️ Ville d'analyse",
    list(city_map.keys()),
    index=0,
    help="Sélectionnez l'une des 3 villes étudiées : Nantes (densification), Nice (création ex-nihilo), Grenoble (référence)."
)
selected_city_dir = city_map[city_name_choice]

folders = {}
if available(selected_city_dir):
    folders["Données réelles"] = selected_city_dir
elif available(REAL):
    folders["Données réelles"] = REAL
if available(DEMO):
    folders["Données de démonstration (factices)"] = DEMO

if not folders:
    st.error("Aucune donnée précalculée. Lancer `python scripts/build_nantes_data.py` ou `python scripts/make_demo_data.py`.")
    st.stop()

choices = list(folders.keys())
src = st.sidebar.radio("Jeu de données", choices, index=0)
folder = str(folders[src])
d = data(folder)

st.sidebar.divider()
zone_name = d["meta"].get("zone", city_name_choice.split(" (")[0])
st.sidebar.caption(f"📍 **Zone d'étude** : {zone_name}")
if d["meta"].get("demo"):
    st.sidebar.warning("Données FACTICES : sert uniquement à valider l'ergonomie.")
else:
    st.sidebar.success(f"Données RÉELLES : {zone_name} (GTFS, GBFS Citiz, voirie).")


# ---------------------------------------------------------------------------------------------
# En-tête principal & KPIs clés
# ---------------------------------------------------------------------------------------------
st.title("Qui a réellement accès à une option de mobilité à 5 minutes à pied ?")
st.caption(f"Territoire analysé : **{zone_name}** · Vitesse piétonne : 4,8 km/h (400 m en 5 minutes)")

tab1, tab2, tab3, tab4 = st.tabs([
    "1 · Carte d'accès",
    "2 · Offre et population desservie",
    "3 · Où investir ?",
    "4 · Méthode et limites"
])


# =============================================================================================
# ONGLET 1 : CARTE D'ACCÈS
# =============================================================================================
with tab1:
    level_scale = st.radio("Échelle", ["IRIS (recommandé)", "Carreaux 200 m"], horizontal=True)
    if level_scale.startswith("IRIS"):
        g = d["iris_wgs"].copy()
        label = "nom"
    else:
        g = d["cells_wgs"].copy()
        hidden = int((g.menages < MIN_MENAGES).sum())
        g = g[g.menages >= MIN_MENAGES]
        label = "id"
        if hidden > 0:
            st.caption(f"{hidden} carreaux de moins de {MIN_MENAGES} ménages ne sont pas affichés isolément "
                       "(secret statistique) ; ils restent comptés dans les agrégats IRIS.")

    g["color"] = colorize(g.score_acces)
    g["score_txt"] = g.score_acces.round(1).astype(str)
    g["pop_txt"] = g.population.round(0).astype(int).astype(str)

    c1, c2, c3 = st.columns(3)
    pop = d["cells"].population.sum()
    c1.metric("Habitants (carreaux habités)", fmt(pop))
    c2.metric("Habitants avec ≥ 1 option à 5 min", f"{100 * d['cells'].loc[d['cells'].n_options > 0, 'population'].sum() / max(1, pop):.0f} %")
    c3.metric("Options pondérées / 1 000 hab. (médiane)", f"{d['iris'].score_acces.median():.1f}")

    layer = pdk.Layer(
        "GeoJsonLayer",
        g[[label, "score_txt", "pop_txt", "color", "geometry"]].__geo_interface__,
        get_fill_color="properties.color",
        get_line_color=[255, 255, 255, 60],
        line_width_min_pixels=0.3,
        opacity=0.75,
        pickable=True
    )
    st.pydeck_chart(deck([layer], g, f"<b>{{{label}}}</b><br/>Options / 1 000 hab. : {{score_txt}}<br/>Habitants : {{pop_txt}}", zoom=11.3))
    st.caption("Couleur : du plus froid (faible accessibilité) au plus chaud. Les **zones froides** signalent un "
               "**potentiel d'amélioration prioritaire** pour l'implantation de mobilités partagées.")


# =============================================================================================
# ONGLET 2 : OFFRE ET POPULATION DESSERVIE
# =============================================================================================
with tab2:
    o = d["offer_served_wgs"].copy()
    available_types = sorted(o.type.unique())
    types = st.multiselect(
        "Types",
        available_types,
        default=available_types,
        format_func=lambda t: TYPE_LABELS.get(t, t)
    )
    if not types:
        st.info("Sélectionnez au moins un type de mobilité.")
        st.stop()

    o = o[o.type.isin(types)]
    o["color"] = o.type.map(lambda t: TYPE_COLORS.get(t, [100, 100, 100]))
    o["type_txt"] = o.type.map(lambda t: TYPE_LABELS.get(t, t))
    o["pop_txt"] = o.pop_desservie.round(0).astype(int).astype(str)
    o["seul_txt"] = (100 * o.part_seule_option).round(0).astype(int).astype(str)
    o["lon"], o["lat"] = o.geometry.x, o.geometry.y

    layer = pdk.Layer(
        "ScatterplotLayer",
        o.drop(columns="geometry"),
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=45,
        radius_min_pixels=2,
        pickable=True,
        opacity=0.85
    )
    st.pydeck_chart(deck([layer], d["offer_served_wgs"], "<b>{nom}</b> ({type_txt})<br/>Habitants à 5 min : {pop_txt}"
                                                          "<br/>Dont sans autre option : {seul_txt} %", zoom=11.3))
    st.caption(" · ".join(f"<span style='color:rgb{tuple(TYPE_COLORS.get(t, [100]*3))}'>●</span> {TYPE_LABELS.get(t, t)}"
                          for t in types), unsafe_allow_html=True)

    stats = o.groupby("type").agg(
        points=("id", "size"),
        pop_moy=("pop_desservie", "mean"),
        orphelins=("part_seule_option", lambda s: int((s >= 0.5).sum()))
    )
    stats.index = stats.index.map(lambda t: TYPE_LABELS.get(t, t))
    st.dataframe(
        stats.rename(columns={
            "points": "Points",
            "pop_moy": "Habitants desservis (moyenne)",
            "orphelins": "Points « seule option » pour ≥ 50 % de leurs habitants"
        }).round(0),
        width="stretch"
    )

    st.subheader("Top 10 : habitants desservis à 5 minutes")
    st.dataframe(
        o.nlargest(10, "pop_desservie")[["nom", "type_txt", "pop_desservie", "part_seule_option"]]
        .rename(columns={"type_txt": "type", "pop_desservie": "habitants à 5 min", "part_seule_option": "part sans autre option"}),
        width="stretch",
        hide_index=True
    )

    # Moniteur temps réel Citiz si disponible
    if "citiz" in types:
        with st.expander("⚡ Voir la disponibilité en temps réel de la flotte Citiz (GBFS live)"):
            citiz_live = fetch_citiz_live_status()
            if citiz_live:
                live_df = pd.DataFrame(citiz_live)
                st.caption(f"{len(live_df)} stations Citiz connectées · {live_df['dispos'].sum()} véhicules actuellement disponibles.")
                st.dataframe(
                    live_df[["nom", "dispos", "capacite", "adresse"]].rename(columns={
                        "nom": "Station",
                        "dispos": "Véhicules libres",
                        "capacite": "Capacité",
                        "adresse": "Adresse"
                    }),
                    width="stretch",
                    hide_index=True
                )
            else:
                st.caption("Flux temps réel accessible en direct depuis https://backend.citiz.fr/public/provider/15/gbfs/v3.0/")


# =============================================================================================
# ONGLET 3 : OÙ INVESTIR ? (OPTIMISATION & CHARTE DES POTENTIELS)
# =============================================================================================
with tab3:
    p = problem(folder)
    left, right = st.columns([1, 3])
    with left:
        budget = st.slider("Budget (€)", 20_000, 3_000_000, 100_000, step=10_000, format="%d €")
        target_scenario = st.radio(
            "Scénario d'usage",
            ["Particuliers", "Mixte", "Pros"],
            index=0,
            help=(
                "• Particuliers (officiel, α = 0) : priorité aux résidents (soirée & week-end, chiffres officiels inchangés).\n"
                "• Mixte (recommandé, α = 0,3) : équilibre résidents et trajets professionnels de journée.\n"
                "• Pros : flottes professionnelles B2B (maximise les emplois desservis)."
            )
        )
        sc_map = {"Particuliers": ("particuliers", 0.0), "Mixte": ("mixte", 0.3), "Pros": ("pros", 1.0)}
        sc_name, sc_alpha = sc_map[target_scenario]
        equity = st.slider(
            "Poids de l'équité",
            0.0, 2.0, 0.5, 0.1,
            help="0 : maximise les habitants desservis × usage. Plus haut : bonus aux zones peu desservies ou à faible revenu."
        )
        cand_types = sorted(p.candidates.type.unique())
        chosen_types = st.multiselect(
            "Équipements",
            cand_types,
            default=cand_types,
            format_func=lambda t: CAND_LABELS.get(t, t)
        )
        method = st.radio(
            "Méthode",
            ["glouton", "ilp"],
            format_func={"glouton": "Glouton (instantané)", "ilp": "ILP optimal (≤ 20 s)"}.get
        )
    if not chosen_types:
        st.info("Choisir au moins un type d'équipement.")
        st.stop()

    @st.cache_data(show_spinner="Optimisation…")
    def run(folder: str, budget: float, equity: float, types: tuple, method: str, scenario: str, alpha: float):
        r = optimize(problem(folder), budget, equity, method=method, types=list(types),
                     scenario=scenario, alpha=alpha,
                     **({"time_limit": 20} if method == "ilp" else {}))
        return r.selection, r.summary

    sel, summary = run(folder, budget, equity, tuple(chosen_types), method, sc_name, sc_alpha)
    n_citiz = int((sel.type == "citiz_station").sum())
    co2 = co2_avoided_t_per_year(n_citiz)

    with right:
        has_pro = "emplois_nouvellement_desservis" in summary and summary["emplois_nouvellement_desservis"] > 0
        if has_pro:
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Emplacements retenus", len(sel))
            m2.metric("Habitants desservis", fmt(summary["pop_nouvellement_desservie"]))
            m3.metric("Emplois desservis", fmt(summary["emplois_nouvellement_desservis"]))
            tot_pers = summary["pop_nouvellement_desservie"] + summary["emplois_nouvellement_desservis"]
            m4.metric("Coût / personne", fmt(summary["cout_total"] / max(1, tot_pers), "€"))
            m5.metric("CO₂ évité", f"{co2:,.1f} t/an".replace(",", " "))
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Emplacements retenus", len(sel))
            m2.metric("Habitants nouvellement desservis", fmt(summary["pop_nouvellement_desservie"]))
            m3.metric("Coût par habitant", fmt(summary["cout_total"] / max(1, summary["pop_nouvellement_desservie"]), "€"))
            m4.metric(
                "CO₂ évité (estimation prudente)",
                f"{co2:,.1f} t/an".replace(",", " "),
                help="Stations Citiz uniquement : 10 000 km de voiture évités/véhicule/an × 0,142 kgCO₂e/km (ADEME, bornes basses)."
            )

        if sc_name == "pros":
            st.warning("⚠️ **Limite méthodologique** : le modèle prédictif d'usage a été entraîné sur les stations résidentielles historiques de Citiz ; il n'est pas calibré pour l'usage professionnel exclusif.")

        if not sel.empty:
            s = pd.DataFrame(sel)
            s["lon"], s["lat"] = TO_WGS84.transform(s.x.to_numpy(float), s.y.to_numpy(float))
            s["type_txt"] = s.type.map(lambda t: CAND_LABELS.get(t, t))
            s["cout_txt"] = s.cout.map(lambda v: fmt(v, "€"))
            s["pop_txt"] = s.pop_nouvellement_desservie.round(0).astype(int).astype(str)
            s["color"] = s.type.map({"citiz_station": [230, 0, 126], "bus_stop": [0, 114, 178],
                                     "bike_station": [0, 158, 115]}).map(lambda c: c if isinstance(c, list) else [90, 90, 90])

            # Enrichir avec les détails géographiques précis (adresses, carrefours, aménagement)
            if "adresse_precise" in d["candidates"].columns:
                extra_cols = [c for c in ["nom", "commune", "categorie", "adresse_precise", "type_amenagement", "flotte_conseillee", "intermodalite", "justification"] if c in d["candidates"].columns]
                cand_info = d["candidates"][extra_cols].drop_duplicates(subset=["nom"])
                s = s.merge(cand_info, on="nom", how="left")

            # Contrôles d'affichage pour la carte détaillée
            map_c1, map_c2 = st.columns([2, 1])
            with map_c1:
                station_options = ["📍 Vue d'ensemble de l'agglomération"] + [f"#{row.rang} {row.nom}" for _, row in s.iterrows()]
                selected_zoom_target = st.selectbox(
                    "🔍 Zoomer directement sur l'emplacement exact d'une station :",
                    station_options,
                    index=0
                )
            with map_c2:
                show_radius = st.checkbox("Afficher le cercle de marche 5 min (400 m)", value=False, help="Active ou désactive le rayon de marche piéton pour garder une vue nette.")
                show_jobs = st.checkbox("Afficher la densité d'emplois (Sirene)", value=(sc_name != "particuliers"), help="Affiche les zones d'emploi et pôles d'activités économiques.")

            # Coordonnées du centrage
            center_coords = None
            map_zoom = 11.5
            selected_station_row = None
            if selected_zoom_target != "📍 Vue d'ensemble de l'agglomération":
                sel_rang = int(selected_zoom_target.split()[0].replace("#", ""))
                selected_station_row = s[s.rang == sel_rang].iloc[0]
                center_coords = (float(selected_station_row["lon"]), float(selected_station_row["lat"]))
                map_zoom = 15.8  # Zoom direct au niveau de la rue !

            exist = d["offer_served_wgs"]
            exist = exist[exist.type.isin(["citiz", "autopartage"])].assign(
                lon=lambda x: x.geometry.x, lat=lambda x: x.geometry.y
            ).drop(columns="geometry")

            # Tramway pour contexte de correspondance
            tram_pts = d["offer_served_wgs"]
            tram_pts = tram_pts[tram_pts.type == "tram"].assign(
                lon=lambda x: x.geometry.x, lat=lambda x: x.geometry.y
            ).drop(columns="geometry")

            if exist.empty:
                st.info(f"💡 **Piste « création ex-nihilo » ({zone_name})** : Aucune station Citiz n'existe actuellement. La carte ci-dessous affiche le plan de déploiement d'un réseau pionnier complet !")

            layers = []
            # Couche optionnelle : densité d'emplois (Sirene agrégé au carreau 200m)
            if show_jobs and "cells_wgs" in d and "emplois" in d["cells_wgs"].columns:
                emp_data = d["cells_wgs"][d["cells_wgs"].emplois >= 25].copy()
                if not emp_data.empty:
                    emp_data["lon"] = emp_data.geometry.centroid.x
                    emp_data["lat"] = emp_data.geometry.centroid.y
                    emp_data["r_emp"] = np.clip(np.sqrt(emp_data.emplois) * 12.0, 35, 280)
                    layers.append(
                        pdk.Layer(
                            "ScatterplotLayer",
                            emp_data,
                            get_position=["lon", "lat"],
                            get_fill_color=[128, 0, 180, 80],
                            get_radius="r_emp",
                            stroked=False,
                            pickable=True
                        )
                    )

            if not tram_pts.empty:
                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        tram_pts,
                        get_position=["lon", "lat"],
                        get_fill_color=[213, 94, 0, 140],
                        get_radius=30,
                        radius_min_pixels=3,
                        pickable=True
                    )
                )
            if not exist.empty:
                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        exist,
                        get_position=["lon", "lat"],
                        get_fill_color=[230, 0, 126, 160],
                        get_line_color=[255, 255, 255],
                        line_width_min_pixels=1,
                        stroked=True,
                        get_radius=40,
                        radius_min_pixels=4,
                        pickable=True
                    )
                )

            # Rayon de marche 400m (uniquement si coché)
            if show_radius:
                layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        s,
                        get_position=["lon", "lat"],
                        get_fill_color="color",
                        get_radius=400,
                        opacity=0.12,
                        stroked=True,
                        get_line_color="color",
                        line_width_min_pixels=1
                    )
                )

            # Points exacts des nouvelles stations (pastilles nettes à taille fixe)
            layers.extend([
                # Anneau extérieur blanc contrasté
                pdk.Layer(
                    "ScatterplotLayer",
                    s,
                    get_position=["lon", "lat"],
                    get_fill_color=[0, 114, 178],
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=3,
                    stroked=True,
                    get_radius=50,
                    radius_min_pixels=7,
                    pickable=True
                ),
                # Étiquette numérique de rang au-dessus du point
                pdk.Layer(
                    "TextLayer",
                    s,
                    get_position=["lon", "lat"],
                    get_text="rang",
                    get_size=13,
                    get_color=[255, 255, 255],
                    get_background_color=[0, 70, 130, 200],
                    get_pixel_offset=[0, -16]
                )
            ])

            tooltip_html = (
                "<b>#{rang} {nom}</b><br/>"
                "Emplacement : {type_txt}<br/>"
                "Coût : {cout_txt}<br/>"
                "Nouveaux habitants desservis à 5 min : {pop_txt}"
            )
            st.pydeck_chart(deck(layers, d["candidates_wgs"], tooltip_html, zoom=map_zoom, center=center_coords))

            leg_text = (
                "🔵 **Points bleus numérotés (#1, #2...)** : emplacements exacts des nouvelles stations recommandées · "
                "🔴 **Points roses** : stations Citiz déjà en service · "
                "🟠 **Petits repères orange** : arrêts du réseau Tramway Naolib."
            )
            if show_jobs:
                leg_text += " · 🟣 **Disques violets** : carreaux concentrant les emplois (Sirene géolocalisée)."
            st.caption(leg_text)

            # Si une station est sélectionnée, afficher sa fiche de micro-implantation
            if selected_station_row is not None:
                st.markdown("---")
                f_c1, f_c2 = st.columns([2, 1])
                with f_c1:
                    st.markdown(f"#### 📍 Détail de l'emplacement exact : #{selected_station_row.rang} {selected_station_row.nom}")
                    st.markdown(f"**Adresse / Carrefour précis :** `{selected_station_row.get('adresse_precise', selected_station_row.nom)}`")
                    st.markdown(f"**Coordonnées GPS exactes :** `{selected_station_row.lat:.5f}, {selected_station_row.lon:.5f}`")
                    st.markdown(f"**Aménagement préconisé :** {selected_station_row.get('type_amenagement', '2 places en voirie délimitées avec marquage bleu Citiz et panneau officiel')}")
                    st.markdown(f"**Intermodalité immédiate :** {selected_station_row.get('intermodalite', 'Connexion réseau Naolib')}")
                    if selected_station_row.get("justification"):
                        st.info(f"💡 **Pourquoi ici :** {selected_station_row['justification']}")
                with f_c2:
                    st.metric("Nouveaux habitants à 5 min", fmt(selected_station_row.pop_nouvellement_desservie))
                    if "emplois_nouvellement_desservis" in selected_station_row:
                        st.metric("Nouveaux emplois à 5 min", fmt(selected_station_row.emplois_nouvellement_desservis))
                    st.metric("Coût d'installation", fmt(selected_station_row.cout, "€"))
                    gmaps_link = f"https://www.google.com/maps/search/?api=1&query={selected_station_row.lat:.6f},{selected_station_row.lon:.6f}"
                    st.link_button("🌐 Voir la rue sur Google Street View / Maps", gmaps_link, use_container_width=True)

    st.subheader("Liste priorisée des implantations")
    display_cols = ["rang", "type", "nom"]
    if "adresse_precise" in s.columns:
        display_cols.append("adresse_precise")
    display_cols += ["cout", "pop_nouvellement_desservie"]
    if "emplois_nouvellement_desservis" in s.columns:
        display_cols.append("emplois_nouvellement_desservis")
    display_cols += ["usage_predit", "cout_par_habitant"]
    if "cout_par_personne" in s.columns:
        display_cols.append("cout_par_personne")
    display_cols.append("budget_cumule")

    table = s.assign(type=s.type.map(lambda t: CAND_LABELS.get(t, t)))[display_cols]
    col_rename = {
        "rang": "Rang",
        "type": "Type",
        "nom": "Emplacement recommandé",
        "adresse_precise": "Adresse / Carrefour exact",
        "cout": "Coût (€)",
        "pop_nouvellement_desservie": "Nouveaux habitants",
        "emplois_nouvellement_desservis": "Nouveaux emplois",
        "usage_predit": "Usage annuel (trajets)",
        "cout_par_habitant": "Coût / hab. (€)",
        "cout_par_personne": "Coût / pers. (€)",
        "budget_cumule": "Budget cumulé (€)"
    }
    st.dataframe(table.rename(columns=col_rename).round(1), width="stretch", hide_index=True)
    st.download_button(
        "Exporter en CSV",
        sel.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"recommandation_{method}_{budget}.csv",
        mime="text/csv"
    )
    st.caption(
        f"Méthode : {summary['methode']} · statut {summary['statut']} · {summary['duree_s']} s · "
        f"budget utilisé {fmt(summary['cout_total'], '€')} / {fmt(budget, '€')} · "
        f"coûts : scénario « {load_costs()['scenario']} » sur {load_costs()['horizon_ans']} ans (config/costs.yaml)"
    )

    # Module étendu : Charte des emplacements potentiels
    if "categorie" in d["candidates"].columns:
        st.divider()
        st.subheader("📍 Charte géographique & Catalogue complet des emplacements potentiels")
        st.markdown(
            "Explorez ci-dessous l'ensemble des **candidats identifiés sur Nantes Métropole** selon leur archetype "
            "(Parking-Relais P+R, Pôle d'échange Tramway / Busway, Zone résidentielle dense)."
        )

        cands = d["candidates_wgs"].copy()
        cands["lon"], cands["lat"] = cands.geometry.x, cands.geometry.y

        fc1, fc2 = st.columns([1, 1])
        with fc1:
            cats = sorted(cands["categorie"].dropna().unique().tolist())
            chosen_cats = st.multiselect("Filtrer par catégorie d'opportunité", cats, default=cats)
        with fc2:
            communes = ["Toutes"] + sorted(cands["commune"].dropna().unique().tolist()) if "commune" in cands.columns else ["Toutes"]
            chosen_comm = st.selectbox("Filtrer par commune", communes)

        cands_sub = cands[cands["categorie"].isin(chosen_cats)].copy()
        if chosen_comm != "Toutes":
            cands_sub = cands_sub[cands_sub["commune"] == chosen_comm]

        if not cands_sub.empty:
            cands_sub["color"] = cands_sub["categorie"].map(lambda c: CAND_CATEGORY_COLORS.get(c, [100, 100, 100]))
            cands_sub["pop_txt"] = cands_sub["pop_potentielle"].astype(str) if "pop_potentielle" in cands_sub.columns else "n.d."
            cands_sub["usage_txt"] = cands_sub["usage_predit"].round(0).astype(int).astype(str)
            cands_sub["cout_txt"] = cands_sub["cout"].map(lambda v: fmt(v, "€"))

            l_buff = pdk.Layer(
                "ScatterplotLayer",
                cands_sub.drop(columns="geometry"),
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_radius=400,
                opacity=0.15,
                stroked=True,
                get_line_color="color",
                line_width_min_pixels=1
            )
            l_pts = pdk.Layer(
                "ScatterplotLayer",
                cands_sub.drop(columns="geometry"),
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_line_color=[255, 255, 255],
                line_width_min_pixels=1.5,
                stroked=True,
                get_radius=60,
                radius_min_pixels=5,
                pickable=True
            )
            cand_tip = "<b>#{rang} {nom}</b><br/>Catégorie : {categorie}<br/>Habitants à 5 min : {pop_txt}<br/>Usage estimé : {usage_txt} trajets/an"
            st.pydeck_chart(deck([l_buff, l_pts], cands_sub, cand_tip, zoom=11.3))
            st.caption("🟠 **Orange** : Parkings-Relais (P+R) · 🔵 **Bleu** : Pôles Tramway / Busway · 🟣 **Violet** : Zones résidentielles denses.")

        # -------------------------------------------------------------------------------------
        # ZOOM MICRO-IMPLANTATION : OÙ METTRE EXACTEMENT LA STATION ?
        # -------------------------------------------------------------------------------------
        st.divider()
        st.subheader("🔎 Zoom Micro-Implantation : Localisation exacte de la station au sol")
        st.markdown(
            "Sélectionnez une station candidate ci-dessous pour voir **au niveau de la rue et du bitume** "
            "l'emplacement précis où implanter les places de stationnement Citiz."
        )

        cand_choice_list = cands_sub["nom"].tolist() if not cands_sub.empty else cands["nom"].tolist()
        selected_cand_name = st.selectbox(
            "🎯 Choisir la station candidate à inspecter en zoom",
            cand_choice_list,
            index=0
        )
        cand_row = cands[cands["nom"] == selected_cand_name].iloc[0]

        zoom_c1, zoom_c2 = st.columns([1.8, 1.2])

        with zoom_c1:
            tile_choice = st.radio(
                "Fond de plan cartographique",
                ["Plan de Rues (OpenStreetMap)", "Vue Aérienne / Satellite (HD)", "Plan Carto Épuré"],
                horizontal=True
            )
            
            tile_attr = None
            if tile_choice == "Plan de Rues (OpenStreetMap)":
                tiles = "OpenStreetMap"
            elif tile_choice == "Vue Aérienne / Satellite (HD)":
                tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                tile_attr = "Esri World Imagery"
            else:
                tiles = "CartoDB positron"

            import folium
            from streamlit_folium import st_folium

            lat_target, lon_target = float(cand_row["lat"]), float(cand_row["lon"])
            
            m_zoom = folium.Map(
                location=[lat_target, lon_target],
                zoom_start=17,
                tiles=tiles,
                attr=tile_attr
            )
            
            # Cercle 400m (5 min piéton)
            folium.Circle(
                location=[lat_target, lon_target],
                radius=400,
                color="#0072b2",
                fill=True,
                fill_color="#0072b2",
                fill_opacity=0.12,
                weight=1.5,
                tooltip="Zone de chalandise piétonne à 5 min (400 m)"
            ).add_to(m_zoom)

            # Emprise immédiate de stationnement (35m)
            folium.Circle(
                location=[lat_target, lon_target],
                radius=35,
                color="#e6007e",
                fill=True,
                fill_color="#e6007e",
                fill_opacity=0.35,
                weight=2,
                dash_array="5, 5",
                tooltip="Emprise directe de la station (2 places réservées Citiz)"
            ).add_to(m_zoom)

            # Marqueur central précis
            folium.Marker(
                location=[lat_target, lon_target],
                popup=folium.Popup(f"<b>Station Citiz #{cand_row.get('rang', '')}</b><br>{cand_row['nom']}<br><i>{cand_row.get('adresse_precise', '')}</i>", max_width=280),
                tooltip=f"📍 Emplacement préconisé : {cand_row['nom']}",
                icon=folium.Icon(color="red", icon="car", prefix="fa")
            ).add_to(m_zoom)

            # Afficher les arrêts de transport ou stations vélo à proximité
            nearby_offer = d["offer_served_wgs"]
            nearby = nearby_offer[
                (abs(nearby_offer.geometry.y - lat_target) < 0.004) &
                (abs(nearby_offer.geometry.x - lon_target) < 0.005)
            ]
            for _, noff in nearby.iterrows():
                noff_type = noff["type"]
                noff_color = "orange" if noff_type == "tram" else ("blue" if noff_type == "bus" else ("green" if noff_type == "velo" else "gray"))
                folium.CircleMarker(
                    location=[noff.geometry.y, noff.geometry.x],
                    radius=5,
                    color=noff_color,
                    fill=True,
                    fill_opacity=0.8,
                    tooltip=f"{TYPE_LABELS.get(noff_type, noff_type)} : {noff['nom']}"
                ).add_to(m_zoom)

            st_folium(m_zoom, width=None, height=480, returned_objects=[])

        with zoom_c2:
            st.markdown(f"#### 📋 Fiche de micro-implantation #{cand_row.get('rang', 1)}")
            st.markdown(f"**Site retenu :** {cand_row['nom']}")
            
            st.metric("👥 Bassin de population à 5 min", fmt(cand_row.get("pop_potentielle", 0)))
            st.metric("📈 Usage estimé", f"{cand_row.get('usage_predit', 0):.0f} trajets/an")
            st.metric("💶 Coût d'installation estimé", fmt(cand_row.get("cout", 7500), "€"))
            
            st.markdown("---")
            st.markdown(f"📍 **Coordonnées GPS exactes :** `{lat_target:.5f}, {lon_target:.5f}`")
            st.markdown(f"🛣️ **Adresse / Carrefour :** {cand_row.get('adresse_precise', cand_row['nom'])}")
            st.markdown(f"🅿️ **Aménagement préconisé :** {cand_row.get('type_amenagement', '2 places en voirie réservées par arrêté municipal, signalétique verticale Citiz et arceau rabattable')}")
            st.markdown(f"🚗 **Flotte initiale recommandée :** {cand_row.get('flotte_conseillee', '1 Citadine polyvalente (Cat. S) + 1 Compacte (Cat. M)')}")
            st.markdown(f"🚊 **Connexions immédiates :** {cand_row.get('intermodalite', 'Réseau Naolib')}")
            st.info(f"💡 **Pourquoi ici ?** {cand_row.get('justification', '')}")

            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={lat_target:.6f},{lon_target:.6f}"
            osm_url = f"https://www.openstreetmap.org/?mlat={lat_target:.6f}&mlon={lon_target:.6f}#map=18/{lat_target:.6f}/{lon_target:.6f}"
            
            c_btn1, c_btn2 = st.columns(2)
            c_btn1.link_button("🌐 Voir sur Google Maps / Street View", gmaps_url, use_container_width=True)
            c_btn2.link_button("🗺️ Voir sur OpenStreetMap", osm_url, use_container_width=True)


# =============================================================================================
# ONGLET 4 : MÉTHODE ET LIMITES
# =============================================================================================
with tab4:
    doc = ROOT / "docs" / "methodologie.md"
    if doc.exists():
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.markdown("""
### Méthodologie & Cadre d'Analyse (Nantes Métropole)
- **Accessibilité piétonne** : 400 m à vol d'oiseau ≈ 5 minutes de marche à 4,8 km/h.
- **Indicateur d'accès** : nombre d'options de mobilité pondérées par mode (TC, vélo, autopartage) rapportées à 1 000 habitants.
- **Identification des candidats** :
  1. Parkings-Relais (P+R) Naolib sans station Citiz à moins de 350 m.
  2. Pôles d'échanges Tramway / Busway / TER majeurs non couverts.
  3. Zones froides à forte densité résidentielle (Filosofi 200 m).
- **Optimisation sous budget** :
  - **Glouton** : ratio gain marginal / coût d'installation.
  - **ILP (PuLP + HiGHS)** : programmation linéaire en nombres entiers garantissant l'optimalité globale.
- **Impact environnemental** : estimation basée sur les ratios ADEME (10 000 km évités/véhicule/an × 0,142 kgCO₂e/km).
""")
