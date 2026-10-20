"""Vue « France entière » (niveau 1) : carte légère par département / EPCI, zoom IRIS / carreaux à la demande."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pydeck as pdk
import streamlit as st

from app.ui import colorize, deck, fmt, fr, pct, table
from src.common.config import processed

APP = processed("national", "app")
# indicateur -> (libellé, format, valeurs fortes = chaud ?)
METRICS = {
    "n_options_moyen": ("Options pondérées accessibles à 5 min (par habitant)", lambda v: fr(v, 1), True),
    "part_pop_sans_option": ("Part de la population sans aucune option à 5 min", lambda v: pct(v, 0), False),
    "part_pop_avec_tc": ("Part de la population à 5 min d'un arrêt de TC", lambda v: pct(v, 0), True),
    "part_pop_citiz_5min": ("Part de la population à 5 min d'une station Citiz", lambda v: pct(v, 1), True),
    "part_menages_sans_voiture": ("Part des ménages sans voiture", lambda v: pct(v, 0), True),
    "densite_vecue_hab_km2": ("Densité vécue (hab./km²)", lambda v: fr(v, 0), True),
}
# Le risque de vol n'est pas cartographié : il n'entre dans le projet que comme un coût (surcoût d'assurance
# et d'entretien d'une station), à l'échelle communale (docs/ethique.md).
EPCI_ONLY = {"score_potentiel_citiz": ("Potentiel Citiz (score 0-1)", lambda v: fr(v, 2), True)}


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
    g["val"] = g[metric].map(fmt_)
    g["pop"] = g["population"].map(fmt)
    layer = pdk.Layer("GeoJsonLayer", g.drop(columns=[metric, "population"]).__geo_interface__,
                      get_fill_color="properties.color", get_line_color=[255, 255, 255, 80], line_width_min_pixels=0.3,
                      opacity=0.75, pickable=True)
    st.pydeck_chart(deck([layer], g, f"<b>{{{label_col}}}</b><br/>{label} : {{val}}<br/>Habitants : {{pop}}", zoom))


def render() -> None:
    files = [APP / "departements.parquet", APP / "epci.parquet"]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        st.error(f"Fichiers nationaux absents ({', '.join(missing)} dans `data/processed/national/app/`). "
                 "Les reconstruire : `python -m src.national.build_all` (≈ 5 min), ou télécharger la Release "
                 "« donnees-v2 » du dépôt (voir docs/RECUPERER_LES_DONNEES.md).")
        return
    st.title("France entière : accès à une option de mobilité à 5 minutes à pied")
    st.markdown("**Cette carte montre**, pour chaque département ou intercommunalité, la part des habitants qui ont "
                "un bus, un tram, un vélo en libre-service ou une voiture partagée à moins de 5 minutes à pied de chez eux.")
    layers = national_layers()
    dep_tot = layers["Départements"]
    pop = dep_tot.population.sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Habitants couverts (carreaux Filosofi)", fmt(pop))
    m2.metric("Sans aucune option à 5 min", pct((dep_tot.part_pop_sans_option * dep_tot.population).sum() / pop))
    m3.metric("À 5 min d'un arrêt de transport en commun", pct((dep_tot.part_pop_avec_tc * dep_tot.population).sum() / pop))
    m4.metric("À 5 min d'une station Citiz", pct((dep_tot.part_pop_citiz_5min * dep_tot.population).sum() / pop))
    c1, c2 = st.columns([1, 2])
    level = c1.radio("Échelle", ["Départements", "EPCI"], horizontal=True)
    metrics = {**METRICS, **(EPCI_ONLY if level == "EPCI" else {})}
    metric = c2.selectbox("Indicateur", list(metrics), format_func=lambda m: metrics[m][0])
    g = layers[level].rename(columns={"nom": "nom_aff"})
    choropleth(g, metric, "nom_aff", metrics, zoom=4.8)
    st.caption("Couleur : du plus froid au plus chaud. Les zones froides signalent un **potentiel d'amélioration**. "
               "Accessibilité calculée à 400 m à vol d'oiseau : c'est une borne haute (la marche réelle, mesurée à "
               "Grenoble et Nantes, donne moins d'accès).")

    st.subheader("Classement des EPCI de plus de 50 000 habitants : potentiel Citiz")
    st.caption("Score = moyenne des rangs : densité vécue, part de ménages sans voiture, autopartage existant (faible = mieux). "
               "Limite : l'autopartage existant n'est connu en open data que pour Citiz, Clem, Rémi, Optymo et Leo&Go ; "
               "Getaround, Zity, Free2Move… ne publient pas de données ouvertes et restent invisibles ici.")
    rank = layers["EPCI"].drop(columns="geometry").dropna(subset=["score_potentiel_citiz"]).sort_values("rang_potentiel")
    cols = {"rang_potentiel": "Rang", "nom": "EPCI", "population": "Habitants", "densite_vecue_hab_km2": "Densité vécue",
            "part_menages_sans_voiture": "Ménages sans voiture", "stations_citiz": "Stations Citiz",
            "autopartage_10k_hab": "Autopartage / 10 000 hab.", "n_options_moyen": "Options à 5 min",
            "part_pop_sans_option": "Pop. sans option", "score_potentiel_citiz": "Score"}
    tbl = rank[[c for c in cols if c in rank]].rename(columns=cols)
    st.dataframe(table(tbl.head(30), digits={"Rang": 0, "Habitants": 0, "Densité vécue": 0, "Stations Citiz": 0,
                                             "Autopartage / 10 000 hab.": 1, "Options à 5 min": 1, "Score": 2},
                       percent={"Ménages sans voiture": 0, "Pop. sans option": 0}),
                 width="stretch", hide_index=True)
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
        g["nom_aff"] = "Carreau " + g["idcar_200m"].str[-14:]
        choropleth(g, "n_options_moyen", "nom_aff", METRICS, zoom=9)
        st.caption("Les carreaux de moins de 11 ménages ne sont pas affichés (secret statistique) ; ils restent comptés à l'IRIS.")
