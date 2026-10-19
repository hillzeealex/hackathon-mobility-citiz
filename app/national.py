"""Vue « France entière » (niveau 1) : carte légère par département / EPCI, zoom IRIS / carreaux à la demande."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pydeck as pdk
import streamlit as st

from app.ui import colorize, deck, fmt
from src.common.config import processed

APP = processed("national", "app")
# indicateur -> (libellé, format, valeurs fortes = chaud ?)
METRICS = {
    "n_options_moyen": ("Options pondérées accessibles à 5 min (par habitant)", "{:.1f}", True),
    "part_pop_sans_option": ("Part de la population sans aucune option à 5 min", "{:.0%}", False),
    "part_pop_avec_tc": ("Part de la population à 5 min d'un arrêt de TC", "{:.0%}", True),
    "part_pop_citiz_5min": ("Part de la population à 5 min d'une station Citiz", "{:.1%}", True),
    "part_menages_sans_voiture": ("Part des ménages sans voiture", "{:.0%}", True),
    "densite_vecue_hab_km2": ("Densité vécue (hab./km²)", "{:,.0f}", True),
}
EPCI_ONLY = {"score_potentiel_citiz": ("Potentiel Citiz (score 0-1)", "{:.2f}", True),
             "vols_vehicules_1000": ("Vols liés aux véhicules pour 1 000 hab. (2023-2025)", "{:.1f}", True)}


@st.cache_resource(show_spinner="Chargement de la carte nationale…")
def national_layers() -> dict:
    return {"Départements": gpd.read_parquet(APP / "departements.parquet"),
            "EPCI": gpd.read_parquet(APP / "epci.parquet")}


@st.cache_resource(show_spinner="Chargement du département…", max_entries=6)
def dep_layer(dep: str, kind: str) -> gpd.GeoDataFrame:
    return gpd.read_parquet(APP / "dep" / f"{dep}_{kind}.parquet")


def choropleth(g: gpd.GeoDataFrame, metric: str, label_col: str, metrics: dict, zoom: float):
    label, fmt_, hot = metrics[metric]
    g = g[[label_col, metric, "population", "geometry"]].copy()
    g["color"] = colorize(g[metric], reverse=not hot)
    g["val"] = g[metric].map(lambda v: fmt_.format(v).replace(",", " ") if pd.notna(v) else "n.d.")
    g["pop"] = g["population"].map(lambda v: fmt(v) if pd.notna(v) else "n.d.")
    layer = pdk.Layer("GeoJsonLayer", g.drop(columns=[metric, "population"]).__geo_interface__,
                      get_fill_color="properties.color", get_line_color=[255, 255, 255, 80], line_width_min_pixels=0.3,
                      opacity=0.75, pickable=True)
    st.pydeck_chart(deck([layer], g, f"<b>{{{label_col}}}</b><br/>{label} : {{val}}<br/>Habitants : {{pop}}", zoom))


def render() -> None:
    if not (APP / "epci.parquet").exists():
        st.error("Fichiers nationaux absents : lancer `python -m src.national.build_all`.")
        return
    st.title("France entière : accès à une option de mobilité à 5 minutes à pied")
    st.caption("Accessibilité **V1 : 400 m à vol d'oiseau**. Elle surestime l'accès réel (détours) ; l'ampleur du biais "
               "est mesurée sur les agglomérations zoomées (marche réelle sur le réseau OSM).")
    layers = national_layers()
    c1, c2 = st.columns([1, 2])
    with c1:
        level = st.radio("Échelle", ["Départements", "EPCI"], horizontal=True)
        metrics = {**METRICS, **(EPCI_ONLY if level == "EPCI" else {})}
        metric = st.selectbox("Indicateur", list(metrics), format_func=lambda m: metrics[m][0])
    g = layers[level].rename(columns={"nom": "nom_aff"})
    with c2:
        dep_tot = layers["Départements"]
        pop = dep_tot.population.sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Habitants couverts (carreaux Filosofi)", fmt(pop))
        m2.metric("Sans aucune option à 5 min", f"{(dep_tot.part_pop_sans_option * dep_tot.population).sum() / pop:.0%}")
        m3.metric("À 5 min d'une station Citiz", f"{(dep_tot.part_pop_citiz_5min * dep_tot.population).sum() / pop:.1%}")
    choropleth(g, metric, "nom_aff", metrics, zoom=4.8)
    st.caption("Couleur : du plus froid au plus chaud. Les zones froides signalent un **potentiel d'amélioration**.")

    st.subheader("Classement des EPCI de plus de 50 000 habitants : potentiel Citiz")
    st.caption("Score = moyenne des rangs : densité vécue, part de ménages sans voiture, autopartage existant (faible = mieux). "
               "⚠️ L'autopartage existant n'est connu en open data que pour Citiz, Clem, Rémi, Optymo et Leo&Go : "
               "il est sous-estimé dans les grandes villes (Getaround, Zity, Free2Move… ne publient pas de GBFS).")
    rank = layers["EPCI"].drop(columns="geometry").dropna(subset=["score_potentiel_citiz"]).sort_values("rang_potentiel")
    cols = {"rang_potentiel": "Rang", "nom": "EPCI", "population": "Habitants", "densite_vecue_hab_km2": "Densité vécue",
            "part_menages_sans_voiture": "Ménages sans voiture", "stations_citiz": "Stations Citiz",
            "autopartage_10k_hab": "Autopartage / 10 000 hab.", "n_options_moyen": "Options à 5 min",
            "part_pop_sans_option": "Pop. sans option", "vols_vehicules_1000": "Vols véhicules / 1 000 hab.",
            "score_potentiel_citiz": "Score"}
    tbl = rank[[c for c in cols if c in rank]].rename(columns=cols)
    st.dataframe(tbl.head(30).round(3), width="stretch", hide_index=True)
    st.download_button("Exporter le classement complet (CSV)", tbl.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name="classement_epci_potentiel_citiz.csv", mime="text/csv")

    st.subheader("Zoom sur un département")
    deps = layers["Départements"].sort_values("dep")
    dep = st.selectbox("Département", deps["dep"], format_func=lambda d: f"{d} · {deps.set_index('dep').at[d, 'nom']}")
    kind = st.radio("Détail", ["IRIS", "Carreaux 200 m (≥ 11 ménages)"], horizontal=True)
    if not (APP / "dep" / f"{dep}_{'iris' if kind == 'IRIS' else 'carreaux'}.parquet").exists():
        st.info("Pas de population au carreau (Filosofi ne couvre ni la Guadeloupe, ni la Guyane, ni Mayotte) : "
                "aucun indicateur d'accessibilité par habitant pour ce territoire. Son offre de transport est connue.")
        return
    if kind == "IRIS":
        g = dep_layer(dep, "iris").rename(columns={"nom_iris": "nom_aff"})
        choropleth(g, "n_options_moyen", "nom_aff", METRICS, zoom=9)
    else:
        g = dep_layer(dep, "carreaux").rename(columns={"pop_calee": "population", "n_options": "n_options_moyen"})
        g["nom_aff"] = g["idcar_200m"].str[-16:]
        choropleth(g, "n_options_moyen", "nom_aff", METRICS, zoom=9)
        st.caption("Les carreaux de moins de 11 ménages ne sont pas affichés (secret statistique) ; ils restent comptés à l'IRIS.")
