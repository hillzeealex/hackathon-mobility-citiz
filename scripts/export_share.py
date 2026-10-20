"""
Export des données nettoyées pour l'équipe -> data/share/

    python scripts/export_share.py                 # Grenoble + Nantes + France entière
    python scripts/export_share.py --only nantes   # ou --only grenoble / --only france
    python scripts/export_share.py --estimate-raw-zone   # taille estimée d'un zip des données BRUTES de la zone

Grenoble (data/share/), pour chaque table de data/processed/ (zone, population, offre, accessibilité) :
  - <table>.gpkg     pour QGIS (Lambert-93, EPSG:2154)
  - <table>.csv      pour Excel (séparateur ;, UTF-8 avec BOM, virgule décimale, latitude/longitude WGS84)
  - <table>.geojson  pour le web (WGS84), seulement s'il fait moins de 50 Mo
  + carte_apercu.html (folium) + hackathon_grenoble_donnees_propres_AAAAMMJJ.zip
Nantes (data/share/nantes/) : mêmes tables préfixées nantes_ (GPKG + CSV), offre avec population desservie,
  recommandations Citiz (V2 marche réelle et V1), carte_nantes.html + hackathon_nantes_donnees_propres_AAAAMMJJ.zip
France entière (data/share/france/), AGRÉGATS seulement (pas de carreaux : trop lourd) :
  - france_departements / france_epci / france_communes  .gpkg (WGS84, toutes les géométries) + .csv
  - france_classement_epci.csv (EPCI classés, pour Excel) + carte_france_departements.html
  + hackathon_france_donnees_propres_AAAAMMJJ.zip
Secret statistique : seuls les carreaux (et IRIS, communes) d'au moins 11 ménages sont exportés ; effectifs
des agrégats arrondis à 5. DICTIONNAIRE_DONNEES.md décrit les deux jeux.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.config import ROOT, city_processed, load_settings, processed, raw, set_city  # noqa: E402

SHARE = ROOT / "data" / "share"
FRANCE = "france"            # sous-dossier de SHARE
NANTES = "nantes"
EXPORTS_META = ".exports.json"   # tables exportées par partie (le dictionnaire couvre les deux même si une seule est relancée)
GEOJSON_MAX = 50 * 1024 ** 2
RISK_MIN_POP = 10_000        # taux de vols par commune publiés seulement au-delà (petits effectifs : bruit, stigmatisation)
MIN_MEN = load_settings()["privacy"]["min_households"]
ROUND_IRIS = 5   # arrondi des effectifs IRIS partagés (anti-recoupement), pas des calculs
IRIS_COUNT_COLS = ("pop_calee", "ind", "men", "men_pauv", "population", "menages")


def round_counts(df: pd.DataFrame, step: int = ROUND_IRIS) -> pd.DataFrame:
    """Arrondit les effectifs (personnes, ménages) au multiple de `step` le plus proche."""
    df = df.copy()
    for c in IRIS_COUNT_COLS:
        if c in df:
            df[c] = (df[c] / step).round() * step
    return df

IGN_ADE = "IGN, ADMIN EXPRESS COG 2026"
IGN_IRIS = "IGN, CONTOURS IRIS 2026"
FILO = "INSEE, Filosofi 2021 carreaux 200 m"
RP_LOG = "INSEE, recensement 2023, logement par IRIS"
CALC = "calcul du projet"
GTFS = "GTFS (transport.data.gouv.fr)"
GBFS = "GBFS (transport.data.gouv.fr)"

# colonne -> (signification, unité, source)
COLUMNS: dict[str, tuple[str, str, str]] = {
    "latitude": ("Latitude du point (centroïde pour une surface)", "degrés WGS84", CALC),
    "longitude": ("Longitude du point (centroïde pour une surface)", "degrés WGS84", CALC),
    "code_insee": ("Code officiel géographique de la commune", "-", IGN_ADE),
    "nom": ("Nom", "-", "selon la table"),
    "nom_commune": ("Nom de la commune", "-", IGN_ADE),
    "population": ("Population municipale de la commune", "habitants", "INSEE, recensement 2023 (via ADMIN EXPRESS)"),
    "date_du_recensement": ("Date de référence du recensement", "date", IGN_ADE),
    "superficie_km2": ("Superficie", "km²", CALC),
    # population
    "idcar_200m": ("Identifiant INSEE du carreau de 200 m", "-", FILO),
    "i_est_200": ("1 = valeurs estimées par l'INSEE (carreau de moins de 11 ménages dans la source)", "0/1", FILO),
    "ind": ("Individus (ménages fiscaux ordinaires), non calé", "personnes", FILO),
    "men": ("Ménages fiscaux", "ménages", FILO),
    "men_pauv": ("Ménages sous le seuil de pauvreté", "ménages", FILO),
    "men_prop": ("Ménages propriétaires", "ménages", FILO),
    "ind_snv": ("Somme des niveaux de vie winsorisés des individus", "€ / an", FILO),
    "log_soc": ("Logements sociaux", "logements", FILO),
    **{f"ind_{k}": ("Individus de 80 ans et plus" if k == "80p" else f"Individus de {k.replace('_', ' à ')} ans",
                    "personnes", FILO)
       for k in ("0_3", "4_5", "6_10", "11_17", "18_24", "25_39", "40_54", "55_64", "65_79", "80p")},
    "ratio_calage": ("Ratio population recensement 2023 / Σ Filosofi de la commune", "-", CALC),
    "pop_calee": ("Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut", "personnes", CALC),
    "code_iris": ("Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS)", "-", IGN_IRIS),
    "nom_iris": ("Nom de l'IRIS", "-", IGN_IRIS),
    "part_sans_voiture": ("Part des ménages sans voiture (valeur de l'IRIS, ou de la commune)", "0-1", RP_LOG),
    "motorisation_source": ("Origine de part_sans_voiture : iris, commune_non_irisee, repli_commune", "-", CALC),
    "niveau_vie_moyen": ("Niveau de vie moyen (ind_snv / ind)", "€ / an / personne", CALC),
    "part_menages_pauvres": ("Part des ménages pauvres (men_pauv / men)", "0-1", CALC),
    "densite_hab_km2": ("Densité de population calée", "habitants / km²", CALC),
    "carreaux": ("Nombre de carreaux habités agrégés", "carreaux", CALC),
    # offre
    "id": ("Identifiant : source:identifiant_d_origine:mode", "-", "GTFS / GBFS"),
    "type": ("Mode : bus, tram, train, telepherique, velo, trottinette, citiz", "-", CALC),
    "sous_type": ("arret (TC), station (Citiz), zone_free_floating (zone de stationnement Voi)", "-", CALC),
    "source": ("Jeu de données d'origine (gtfs:<jeu> ou gbfs:<jeu>)", "-", "transport.data.gouv.fr"),
    "capacite": ("Capacité déclarée (places) pour les stations GBFS", "places", GBFS),
    "passages_jour": ("Passages un mardi type (TC uniquement), après fusion des quais", "passages / jour", GTFS),
    "n_fusionnes": ("Nombre de points d'origine fusionnés (dédoublonnage)", "points", CALC),
    "ids_fusionnes": ("Identifiants des points d'origine fusionnés, séparés par |", "-", CALC),
    "dans_zone": ("Vrai si le point est dans la métropole (faux : dans la bande tampon de 800 m)", "booléen", CALC),
    # accessibilité (phase 3)
    "n_options_v1": ("Options pondérées accessibles à 400 m à vol d'oiseau", "options", CALC),
    "n_options_v2": ("Options pondérées accessibles à 400 m de marche (réseau OSM)", "options", CALC),
    "n_points_v1": ("Points d'offre à 400 m à vol d'oiseau", "points", CALC),
    "n_points_v2": ("Points d'offre à 400 m de marche", "points", CALC),
    "acces_1000_v1": ("Options pour 1 000 habitants (2SFCA), vol d'oiseau", "options / 1 000 hab.", CALC),
    "acces_1000_v2": ("Options pour 1 000 habitants (2SFCA), marche", "options / 1 000 hab.", CALC),
    "n_options_v2_sans_poids_ff": ("Comme n_options_v2, free-floating au poids normal du mode", "options", CALC),
    "part_pop_couverte_v2": ("Part de la population avec au moins une option à 5 min de marche", "0-1", CALC),
    "population_calee": ("Population calée", "personnes", CALC),
    "menages": ("Ménages fiscaux", "ménages", FILO),
}
for _t in ("bus", "tram", "train", "telepherique", "velo", "trottinette", "citiz", "metro"):
    COLUMNS[f"n_{_t}_v2"] = (f"Points « {_t} » à 5 min de marche", "points", CALC)

for _t in ("autopartage",):
    COLUMNS[f"n_{_t}_v2"] = ("Stations d'autopartage hors Citiz (Marguerite) à 5 min de marche", "points", CALC)
    COLUMNS[f"n_{_t}_v1"] = ("Stations d'autopartage hors Citiz (Marguerite) à 400 m à vol d'oiseau", "points", CALC)
for _t in ("bus", "tram", "train", "telepherique", "velo", "trottinette", "citiz", "metro"):
    COLUMNS[f"n_{_t}_v1"] = (f"Points « {_t} » à 400 m à vol d'oiseau", "points", CALC)
COLUMNS.update({
    "n_options_v1_sans_poids_ff": ("Comme n_options_v1, free-floating au poids normal du mode", "options", CALC),
    "part_pop_couverte_v1": ("Part de la population avec au moins une option à 400 m à vol d'oiseau", "0-1", CALC),
    "acces_1000_v1": ("Options pour 1 000 habitants (2SFCA), vol d'oiseau", "options / 1 000 hab.", CALC),
    "pop_desservie": ("Habitants (population calée) à 5 min de ce point (V2 marche réelle si disponible, sinon V1)", "habitants", CALC),
    "pop_seule_option": ("Habitants pour qui ce point est la SEULE option à 5 min", "habitants", CALC),
    "part_seule_option": ("pop_seule_option / pop_desservie", "0-1", CALC),
    "version": ("Accessibilité utilisée : v1 vol d'oiseau, v2 marche réelle", "-", CALC),
    "rang": ("Rang dans la liste priorisée (1 = première station à installer)", "rang", CALC),
    "cout": ("Coût total de la station sur l'horizon (3 ans, scénario moyen) + surcoût de risque", "€", "config/costs.yaml"),
    "pop_nouvellement_desservie": ("Habitants qui passent à moins de 5 min d'un autopartage grâce à cette station", "habitants", CALC),
    "usage_predit": ("Probabilité du modèle qu'une station Citiz soit à 400 m (prédite sans le réseau de la ville)", "0-1", CALC),
    "cout_par_habitant": ("cout / pop_nouvellement_desservie", "€ / habitant", CALC),
    "budget_cumule": ("Coût cumulé des stations de rang ≤ celui-ci", "€", CALC),
    "gain_objectif": ("Gain de la fonction objectif (habitants × équité × usage relatif)", "-", CALC),
    "origine": ("Type d'emplacement candidat : carreau (centre d'un carreau habité) ou arret_tc", "-", CALC),
    "commune": ("Commune de l'emplacement", "-", IGN_ADE),
    "surcout_risque": ("Surcoût de risque de vol inclus dans cout (HYPOTHÈSE À VALIDER AVEC CITIZ)", "€", "config/costs.yaml"),
    "dist_autopartage_m": ("Distance à la station d'autopartage existante la plus proche, à pied (V2) ou à vol d'oiseau (V1) ; "
                           "vide au-delà de 3 km", "m", CALC),
    "dist_vol_oiseau_m": ("Distance à vol d'oiseau à la station d'autopartage existante la plus proche", "m", CALC),
    "x": ("Coordonnée X Lambert-93", "m", CALC),
    "y": ("Coordonnée Y Lambert-93", "m", CALC),
    "budget_eur": ("Budget du scénario", "€", CALC),
    "acces": ("Accessibilité utilisée pour la recommandation (v1 / v2)", "-", CALC),
})
SSMSI = "SSMSI, délinquance enregistrée par commune 2023-2025"
V1 = "calcul du projet (V1 : 400 m à vol d'oiseau)"
COLUMNS.update({
    # France entière (niveau 1) : agrégats de carreaux pondérés par la population calée
    "dep": ("Code du département", "-", IGN_ADE),
    "code_epci": ("Numéro SIREN de l'EPCI (intercommunalité)", "-", IGN_ADE),
    "nom_epci": ("Nom de l'EPCI de la commune", "-", IGN_ADE),
    "nature": ("Nature de l'EPCI : ME métropole, CU, CA, CC", "-", IGN_ADE),
    "n_options_moyen": ("Options de mobilité pondérées accessibles à 5 min, moyenne par habitant", "options", V1),
    "part_pop_sans_option": ("Part de la population sans aucun point d'offre à 5 min", "0-1", V1),
    "part_pop_avec_tc": ("Part de la population à 5 min d'un arrêt de transport en commun", "0-1", V1),
    "part_pop_citiz_5min": ("Part de la population à 5 min d'une station Citiz", "0-1", V1),
    "acces_1000_moyen": ("Options pour 1 000 habitants (2SFCA, tient compte de la demande concurrente), moyenne par habitant",
                         "options / 1 000 hab.", V1),
    "citiz_1000_moyen": ("Véhicules Citiz pour 1 000 habitants (2SFCA), moyenne par habitant", "véhicules / 1 000 hab.", V1),
    "part_menages_sans_voiture": ("Part des ménages sans voiture", "0-1", RP_LOG),
    "densite_vecue_hab_km2": ("Densité vécue : densité moyenne des carreaux où vivent les habitants (pondérée par la "
                              "population ; insensible aux espaces vides)", "habitants / km²", CALC),
    "stations_citiz": ("Stations Citiz (GBFS)", "stations", GBFS),
    "vehicules_citiz": ("Véhicules Citiz déclarés (capacité des stations)", "véhicules", GBFS),
    "stations_autres_autopartage": ("Stations d'autres opérateurs d'autopartage publiant un GBFS (Clem, Rémi, Optymo, Leo&Go)",
                                    "stations", GBFS),
    "voitures_free_floating": ("Voitures d'autopartage sans station visibles en GBFS (photo du téléchargement)", "voitures", GBFS),
    "autopartage_10k_hab": ("Autopartage existant connu (stations + voitures free-floating) pour 10 000 hab. — "
                            "sous-estimé : la plupart des opérateurs ne publient rien", "pour 10 000 hab.", CALC),
    "citiz_stations_100k_hab": ("Stations Citiz pour 100 000 habitants", "pour 100 000 hab.", CALC),
    "vols_vehicules_1000": ("Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab.",
                            "faits / an / 1 000 hab.", SSMSI),
    "degradations_1000": ("Destructions et dégradations volontaires, moyenne annuelle 2023-2025 pour 1 000 hab.",
                          "faits / an / 1 000 hab.", SSMSI),
    "score_potentiel_citiz": ("Potentiel Citiz : moyenne des rangs-percentiles (densité vécue ↑, ménages sans voiture ↑, "
                              "autopartage existant ↓) parmi les EPCI ≥ 50 000 hab.", "0-1", CALC),
    "score_avec_risque": ("Score de potentiel − 0,25 × rang-percentile des vols liés aux véhicules (variante prudente)", "≈ 0-1", CALC),
    "rang_potentiel": ("Rang national du potentiel Citiz (1 = plus fort), EPCI ≥ 50 000 hab.", "rang", CALC),
    "score_potentiel_epci": ("Score de potentiel Citiz de l'EPCI de la commune (vide si EPCI < 50 000 hab.)", "0-1", CALC),
    "rang_potentiel_epci": ("Rang national de l'EPCI de la commune", "rang", CALC),
    "score_potentiel_moyen": ("Moyenne, pondérée par la population, du score de potentiel des EPCI classés du département",
                              "0-1", CALC),
    "part_pop_epci_classes": ("Part de la population du département vivant dans un EPCI classé (≥ 50 000 hab.)", "0-1", CALC),
    "meilleur_epci": ("EPCI du département le mieux classé (potentiel Citiz)", "-", CALC),
    "meilleur_rang": ("Rang national de cet EPCI", "rang", CALC),
})
# même nom, sens différent selon la table
_FR_POP = ("Population calée (Σ des carreaux Filosofi recalés sur le recensement 2023), arrondie à 5", "habitants", CALC)
_FR_MEN = ("Ménages fiscaux (Σ des carreaux), arrondis à 5", "ménages", FILO)
_FR_CARR = ("Carreaux habités de 200 m", "carreaux", FILO)
COLUMNS_BY_TABLE: dict[str, dict[str, tuple[str, str, str]]] = {
    t: {"population": _FR_POP, "menages": _FR_MEN, "carreaux": _FR_CARR, "nom": (f"Nom officiel ({t.split('_')[-1]})", "-", IGN_ADE),
        "superficie_km2": ("Superficie (projection équivalente)", "km²", CALC)}
    for t in ("france_departements", "france_epci", "france_communes", "france_classement_epci")
}
COLUMNS_BY_TABLE["france_communes"]["vols_vehicules_1000"] = (
    COLUMNS["vols_vehicules_1000"][0] + f" — publié seulement pour les communes d'au moins {RISK_MIN_POP:,} hab.".replace(",", " "),
    *COLUMNS["vols_vehicules_1000"][1:])
COLUMNS_BY_TABLE["france_communes"]["degradations_1000"] = (
    COLUMNS["degradations_1000"][0] + f" — idem, communes d'au moins {RISK_MIN_POP:,} hab.".replace(",", " "),
    *COLUMNS["degradations_1000"][1:])


def describe(table: str, col: str) -> tuple[str, str, str] | None:
    return COLUMNS_BY_TABLE.get(table, {}).get(col) or COLUMNS.get(col)


TABLES = {  # nom exporté -> (description, ce qui a été fait)
    "zone_communes": ("Les communes de la métropole (périmètre d'étude).", []),
    "population_carreaux": ("Population et caractéristiques socio-économiques par carreau de 200 m.", []),
    "population_iris": ("Agrégat par IRIS de TOUS les carreaux (y compris < 11 ménages) : affichage public recommandé. "
                        "**Effectifs (pop_calee, ind, men, men_pauv) arrondis à 5 près** (secret statistique) ; "
                        "ratios calculés sur les valeurs exactes.", []),
    "offre": ("Tous les points d'offre de mobilité (arrêts TC, stations d'autopartage, vélos, trottinettes) sur la zone "
              "+ 800 m, avec la population desservie (objectif 2).", []),
    "recommandations": ("Stations Citiz recommandées (500 000 €, ILP, équité 0,5), dans l'ordre de priorité ; accessibilité "
                        "en marche réelle (V2). Les fichiers recommandations_*.csv donnent tous les budgets et méthodes.", []),
    "acces_carreaux": ("Indicateurs d'accessibilité à 5 min par carreau (V1 vol d'oiseau et V2 marche réelle).", []),
    "acces_iris": ("Indicateurs d'accessibilité agrégés par IRIS.", []),
    "france_departements": ("France entière (DROM inclus) : un indicateur par département. Guadeloupe, Guyane et Mayotte : "
                            "pas de population au carreau (Filosofi), indicateurs vides. Dossier `france/`.", []),
    "france_epci": ("France entière : toutes les intercommunalités, indicateurs + classement du potentiel Citiz "
                    "(rang et score seulement pour les EPCI ≥ 50 000 hab.). Dossier `france/`.", []),
    "france_communes": ("France entière : une ligne par commune habitée d'au moins 11 ménages fiscaux ; contours simplifiés "
                        "(≈ 100 m). Taux de vols seulement pour les communes ≥ 10 000 hab. Dossier `france/`.", []),
    "france_classement_epci": ("Classement des EPCI ≥ 50 000 hab. par potentiel Citiz, trié par rang (CSV pour Excel). "
                               "Dossier `france/`.", []),
}


# ---------------------------------------------------------------------------------------------
def with_latlon(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pts = g.geometry.representative_point() if not (g.geom_type == "Point").all() else g.geometry
    ll = gpd.GeoSeries(pts, crs=g.crs).to_crs(4326)
    return g.assign(latitude=ll.y.round(6), longitude=ll.x.round(6))


def iris_aggregate(cells: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Agrégat IRIS de la population (calculé sur TOUS les carreaux, y compris < 11 ménages)."""
    from src.ingest.archives import ign_gpkg
    from src.ingest.zone import load_zone

    zone = load_zone()
    iris = gpd.read_file(ign_gpkg("iris"), bbox=tuple(zone.to_crs(4326).total_bounds),
                         columns=["code_iris", "nom_iris", "code_insee", "nom_commune"]).to_crs(cells.crs)
    c = cells.assign(_sv=cells.part_sans_voiture * cells.men)
    agg = c.groupby("code_iris").agg(carreaux=("idcar_200m", "size"), pop_calee=("pop_calee", "sum"), ind=("ind", "sum"),
                                     men=("men", "sum"), men_pauv=("men_pauv", "sum"), ind_snv=("ind_snv", "sum"),
                                     _sv=("_sv", "sum"))
    agg["niveau_vie_moyen"] = agg.ind_snv / agg.ind
    agg["part_menages_pauvres"] = (agg.men_pauv / agg.men).clip(0, 1)
    agg["part_sans_voiture"] = agg._sv / agg.men
    out = iris.merge(agg.drop(columns=["_sv", "ind_snv"]).reset_index(), on="code_iris", how="inner")
    out["superficie_km2"] = out.area / 1e6
    out["densite_hab_km2"] = out.pop_calee / out.superficie_km2
    return out


def round_floats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.select_dtypes("float").columns:
        if c not in ("latitude", "longitude"):
            df[c] = df[c].round(4)
    return df


def export_table(name: str, g: gpd.GeoDataFrame, log: list, sub: str = "", geojson: bool = True) -> dict:
    folder = SHARE / sub
    folder.mkdir(parents=True, exist_ok=True)
    g = with_latlon(round_floats(g))
    info = {"table": name, "dossier": sub, "lignes": len(g), "colonnes": [c for c in g.columns if c != "geometry"],
            "fichiers": {}}
    gp = folder / f"{name}.gpkg"
    gp.unlink(missing_ok=True)
    g.to_file(gp, layer=name, driver="GPKG")
    info["fichiers"]["gpkg"] = gp.stat().st_size
    csv = folder / f"{name}.csv"
    pd.DataFrame(g.drop(columns="geometry")).to_csv(csv, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    info["fichiers"]["csv"] = csv.stat().st_size
    if not geojson:
        return info
    gj = g.drop(columns=["latitude", "longitude"]).to_crs(4326).to_json(drop_id=True, to_wgs84=True)
    gj_path = folder / f"{name}.geojson"
    if len(gj.encode("utf-8")) < GEOJSON_MAX:
        gj_path.write_text(gj, encoding="utf-8")
        info["fichiers"]["geojson"] = gj_path.stat().st_size
    else:
        gj_path.unlink(missing_ok=True)
        log.append(f"{name} : GeoJSON non produit (≥ 50 Mo)")
    return info


# ---------------------------------------------------------------------------------------------
def fr(n: float, decimals: int = 0) -> str:
    """Nombre au format français : 406 039 ; 99,7."""
    return f"{n:,.{decimals}f}".replace(",", " ").replace(".", ",")


def cleaning_notes(ville: str = "grenoble") -> list[str]:
    set_city(ville)
    s = load_settings()
    notes = []
    rep = city_processed("population_rapport.json")
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        notes += [
            f"**Population calée** : Filosofi 2021 ne compte que les ménages fiscaux ordinaires ({fr(r['ind_filosofi'])} "
            f"individus) ; chaque carreau est recalé sur la population communale du recensement 2023 "
            f"({fr(r['population_recensement'])}) : `pop_calee = ind × ratio_calage`. Ratios par commune : "
            "`data/processed/population_calage_communes.csv` (ex. Saint-Martin-d'Hères 1,25 : campus).",
            "**Rattachement des carreaux** : par centroïde (un carreau en bordure n'est compté que dans une commune).",
            f"**Secret statistique** : {fr(r['carreaux_men_lt_11'])} carreaux de moins de {MIN_MEN} ménages sont "
            "utilisés dans les calculs et dans les agrégats IRIS, mais **ne figurent pas** dans population_carreaux "
            f"(ni les IRIS de moins de {MIN_MEN} ménages dans population_iris). Pour empêcher de retrouver un carreau "
            f"masqué par différence (total IRIS − carreaux affichés), les **effectifs des tables IRIS sont arrondis à "
            f"{ROUND_IRIS} près** dans les exports partagés ({', '.join(f'`{c}`' for c in IRIS_COUNT_COLS)}) ; les ratios "
            "et tous les calculs du projet utilisent les valeurs exactes. Voir `docs/ethique.md`.",
            f"**Motorisation** : jointure IRIS réussie pour {fr(100 * r['taux_jointure_iris'], 1)} % des carreaux des communes "
            f"découpées en IRIS ; {r['repli_commune']} replis sur la valeur communale ; {fr(r['commune_non_irisee'])} "
            "carreaux de communes non découpées en IRIS (valeur communale).",
        ]
    dd = city_processed("offer_dedup_stats.csv")
    if dd.exists():
        d = pd.read_csv(dd)
        detail = ", ".join(f"{x.type} {x.avant}→{x.apres}" for x in d.itertuples())
        notes.append(f"**Dédoublonnage de l'offre** : points d'un même mode à moins de {s['offer']['dedup_m']} m fusionnés "
                     f"(train : {s['offer'].get('dedup_m_by_type', {}).get('train', '-')} m) ; {detail}.")
    gr = city_processed("offer_gtfs_report.csv")
    if gr.exists():
        g = pd.read_csv(gr)
        days = sorted(set(g["jour_type"].dropna()))
        notes.append(f"**Jour type GTFS** : mardi le plus chargé des 8 prochaines semaines couvertes par chaque réseau "
                     f"({', '.join(days)}) : évite les vacances scolaires. `frequencies.txt` converti en départs réels.")
    notes += [
        f"**Zone tampon** : l'offre est chargée sur la métropole + {s['offer']['buffer_m']} m (colonne `dans_zone`).",
        f"**GTFS retenus** (`config/settings.yaml`, cities.{ville}.gtfs_feeds) : " + ", ".join(
            f"`{f}`" for f in s["cities"][ville]["gtfs_feeds"]) + " ; exclus partout : covoiturage, Flixbus, BlaBlaCar ; "
        f"jour type figé au mardi {s['offer']['typical_weekday']}.",
        "**Exclusions** : flux GBFS « Dott France » (doublon) ; emplacement interne « DEMOBOX (Réservé Citiz) ».",
        "**Corrections de typage GTFS** : `route_type = 5` du téléphérique -> téléphérique ; arrêts SNCF « OCECar » "
        "(autocars de substitution) -> bus.",
        "**Zones free-floating** : chaque zone de stationnement donne un point `velo` et un point `trottinette`.",
    ] + ([
        "**Marguerite** : 61 stations d'autopartage publiées par Nantes Métropole (open data, Licence Ouverte), type "
        "`autopartage` ; les stations Citiz viennent du GBFS Citiz. Getaround : aucune donnée ouverte.",
        "**Recommandations** : `src/optim/build_reco.py` ; candidats hors des 5 min de marche d'un autopartage ; coût "
        "avec surcoût de risque de vol (**hypothèse à valider avec Citiz**) ; voir `docs/chiffres_cles.md`.",
    ] if ville == "nantes" else []) + [
        "**Coordonnées** : filtrage des points (0,0) ou hors de France métropolitaine.",
    ]
    return notes


def france_notes() -> list[str]:
    notes = []
    rep = processed("national", "agg_rapport.json")
    if rep.exists():
        r = json.loads(rep.read_text(encoding="utf-8"))
        tot = r.get("france", r)
        if "population" in tot:
            notes.append(f"**Couverture** : {fr(tot['population'])} habitants calés (carreaux Filosofi 2021 de métropole, "
                         "Martinique et Réunion). Guadeloupe, Guyane, Mayotte : pas de carreaux Filosofi, donc pas d'indicateur "
                         "par habitant (lignes vides dans france_departements, absentes de france_communes).")
    notes += [
        "**Accessibilité V1** : 400 m **à vol d'oiseau** autour du centroïde de chaque carreau de 200 m, puis moyenne "
        "pondérée par la population. C'est une **borne haute** : la marche réelle (réseau OSM, V2) est mesurée sur les "
        "agglomérations zoomées. Mêmes poids de modes et même dédoublonnage que pour Grenoble (`docs/methodologie.md` §4-5).",
    ]
    off = processed("national", "offer_rapport.json")
    if off.exists():
        o = json.loads(off.read_text(encoding="utf-8"))
        notes.append(f"**Offre nationale** : {o['flux_gtfs']} GTFS ({o['flux_gtfs_en_erreur']} illisibles ; "
                     f"{o['flux_gtfs_hors_periode']} expirés, lus sur leur dernier mardi valide) + tous les GBFS de "
                     "transport.data.gouv.fr, fusionnés puis dédoublonnés par mode (40 m ; trains 150 m) : "
                     f"{fr(o['points_avant'])} → {fr(o['points_apres'])} points.")
    notes += [
        "**Autopartage existant** : seuls Citiz, Clem, Rémi, Optymo et Leo&Go publient un GBFS ; Getaround, Zity, "
        "Free2Move… sont absents. `autopartage_10k_hab` et donc le potentiel sont **biaisés** dans les grandes villes.",
        "**Risque de vol** (SSMSI) : faits enregistrés par la police et la gendarmerie, rapportés à la population ; "
        f"commune : publié seulement à partir de {fr(RISK_MIN_POP)} habitants (au-dessous, quelques faits font varier "
        "fortement le taux et désigneraient injustement de petites communes). C'est un **critère d'exploitation** "
        "(coût, assurance) et non un jugement sur les habitants : voir `docs/ethique.md`.",
        f"**Secret statistique** : communes de moins de {MIN_MEN} ménages fiscaux exclues ; effectifs (`population`, "
        f"`menages`) de toutes les tables France arrondis à {ROUND_IRIS} près. Aucun carreau n'est exporté au niveau national.",
        "**Géométries** : WGS84 (EPSG:4326) pour tout le territoire (DROM compris), simplifiées : départements ≈ 200 m, "
        "EPCI ≈ 300 m, communes ≈ 100 m. À utiliser pour des cartes, pas pour des calculs de surface fins.",
    ]
    return notes


def load_exports_meta() -> dict:
    p = SHARE / EXPORTS_META
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_dictionary(meta: dict[str, list[dict]], log: list) -> Path:
    lines = ["# Dictionnaire des données — Hackathon Mobility (Epitech × Citiz) : Grenoble, Nantes et France entière", "",
             f"Généré par `scripts/export_share.py` le {dt.date.today().isoformat()}. "
             "Méthode détaillée : `docs/methodologie.md` ; sources : `docs/sources.md` ; éthique : `docs/ethique.md`.", "",
             "## Contenu", "",
             "| Dossier / fichier | Contenu |", "|---|---|",
             "| `data/share/` | Grenoble-Alpes-Métropole : carreaux, IRIS, communes, offre (+ accessibilité quand elle est calculée) |",
             "| `data/share/nantes/` | Nantes Métropole : mêmes tables préfixées `nantes_`, offre avec population desservie, recommandations Citiz |",
             "| `data/share/france/` | France entière : **agrégats** par département, EPCI et commune, classement des EPCI |",
             "| `hackathon_grenoble_donnees_propres_AAAAMMJJ.zip` | tout `data/share/` (hors `france/`) + ce dictionnaire + méthodologie |",
             "| `hackathon_nantes_donnees_propres_AAAAMMJJ.zip` | tout `data/share/nantes/` + ce dictionnaire + méthodologie, modèle, décisions, chiffres clés |",
             "| `hackathon_france_donnees_propres_AAAAMMJJ.zip` | tout `data/share/france/` + ce dictionnaire + méthodologie, éthique |",
             "", "## Formats", "",
             "| Format | Pour qui | Détails |", "|---|---|---|",
             "| `.csv` | Excel | séparateur `;`, UTF-8 avec BOM, virgule décimale ; colonnes `latitude`/`longitude` en WGS84 (centroïde pour les surfaces), pas de géométrie |",
             "| `.gpkg` | QGIS | géométries complètes : Lambert-93 (EPSG:2154) pour Grenoble, WGS84 (EPSG:4326) pour la France |",
             "| `.geojson` | web, outils en ligne | WGS84 (EPSG:4326), produit si < 50 Mo (Grenoble seulement) |",
             "| `carte_apercu.html` | tout le monde | double-clic : carte interactive de Grenoble (connexion internet requise pour le fond de carte) |",
             "| `france/carte_france_departements.html` | tout le monde | double-clic : carte nationale par département, un indicateur à la fois |",
             ""]
    sections = [("grenoble", "Grenoble-Alpes-Métropole (ville exemple)", lambda: cleaning_notes("grenoble")),
                ("nantes", "Nantes Métropole (ville des recommandations)", lambda: cleaning_notes("nantes")),
                ("france", "France entière (niveau 1)", france_notes)]
    for part, title, notes in sections:
        if part not in meta:
            continue
        lines += [f"# {title}", "", "## Choix de nettoyage", ""] + [f"- {n}" for n in notes()] + [""]
        for info in meta[part]:
            desc = TABLES.get(info["table"], TABLES.get(info["table"].removeprefix("nantes_"), ("", [])))[0]
            prefix = f"{info['dossier']}/" if info.get("dossier") else ""
            size = ", ".join(f"`{prefix}{info['table']}.{k}` {fr(v / 1024 ** 2, 1)} Mo" for k, v in info["fichiers"].items())
            lines += [f"## {info['table']}", "", desc, "", f"**{fr(info['lignes'])} lignes** — fichiers : {size}", "",
                      "| Colonne | Signification | Unité | Source |", "|---|---|---|---|"]
            for c in info["colonnes"]:
                d = describe(info["table"], c)
                if d is None:
                    log.append(f"colonne non documentée : {info['table']}.{c}")
                sig, unit, src = d or ("**à documenter**", "", "")
                lines.append(f"| `{c}` | {sig} | {unit} | {src} |")
            lines.append("")
    path = SHARE / "DICTIONNAIRE_DONNEES.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------------
TYPE_COLORS = {"bus": "#0072b2", "tram": "#d55e00", "train": "#555555", "telepherique": "#009e73",
               "velo": "#2ca02c", "trottinette": "#bcbd22", "citiz": "#e6007e", "metro": "#cc79a7"}


def write_map(layers: dict[str, gpd.GeoDataFrame], path: Path | None = None) -> Path:
    import folium
    import branca.colormap as cm

    zone = layers["zone_communes"].to_crs(4326)
    minx, miny, maxx, maxy = zone.total_bounds
    m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=11, tiles="CartoDB positron")

    def gj(g, cols):
        g = g.to_crs(4326)[cols + ["geometry"]].copy()
        g["geometry"] = g.geometry.set_precision(1e-5)   # ~1 m : allège le HTML
        return g

    folium.GeoJson(gj(zone, ["nom", "population"]), name="Communes",
                   style_function=lambda f: {"color": "#444", "weight": 1, "fill": False},
                   tooltip=folium.GeoJsonTooltip(["nom", "population"], aliases=["Commune", "Habitants (2023)"])).add_to(m)
    if "population_iris" in layers:
        it = layers["population_iris"]
        cmap = cm.linear.YlOrRd_09.scale(0, float(it.densite_hab_km2.quantile(0.98)))
        cmap.caption = "Densité (hab./km², IRIS)"
        folium.GeoJson(gj(it.round({"densite_hab_km2": 0, "pop_calee": 0, "part_sans_voiture": 2}),
                          ["nom_iris", "nom_commune", "pop_calee", "densite_hab_km2", "part_sans_voiture"]),
                       name="Population par IRIS",
                       style_function=lambda f: {"fillColor": cmap(min(f["properties"]["densite_hab_km2"] or 0, cmap.vmax)),
                                                 "color": "#999", "weight": 0.3, "fillOpacity": 0.55},
                       tooltip=folium.GeoJsonTooltip(["nom_iris", "nom_commune", "pop_calee", "densite_hab_km2", "part_sans_voiture"],
                                                     aliases=["IRIS", "Commune", "Habitants", "Hab./km²", "Ménages sans voiture"])).add_to(m)
        cmap.add_to(m)
    if "population_carreaux" in layers:
        pc = layers["population_carreaux"].round({"pop_calee": 0, "part_sans_voiture": 2})
        cm2 = cm.linear.PuBu_09.scale(0, float(pc.pop_calee.quantile(0.98)))
        folium.GeoJson(gj(pc, ["idcar_200m", "pop_calee", "part_sans_voiture"]), name="Carreaux 200 m (≥ 11 ménages)",
                       show=False,
                       style_function=lambda f: {"fillColor": cm2(min(f["properties"]["pop_calee"] or 0, cm2.vmax)),
                                                 "color": "none", "fillOpacity": 0.6},
                       tooltip=folium.GeoJsonTooltip(["pop_calee", "part_sans_voiture"], aliases=["Habitants", "Ménages sans voiture"])).add_to(m)
    if "offre" in layers:
        o = layers["offre"]
        for t, sub in o.groupby("type"):
            color = TYPE_COLORS.get(t, "#666")
            folium.GeoJson(gj(sub.fillna({"passages_jour": -1}), ["nom", "type", "passages_jour"]), name=f"Offre : {t} ({len(sub)})",
                           show=t in ("tram", "train", "citiz", "telepherique"),
                           marker=folium.CircleMarker(radius=4 if t != "citiz" else 6, fill=True, fill_opacity=0.85, weight=1),
                           style_function=lambda f, c=color: {"color": c, "fillColor": c},
                           tooltip=folium.GeoJsonTooltip(["nom", "type", "passages_jour"],
                                                         aliases=["Nom", "Mode", "Passages/jour (-1 = sans objet)"])).add_to(m)
    if "acces_iris" in layers:
        a = layers["acces_iris"]
        cm3 = cm.linear.RdYlBu_11.scale(0, float(a.n_options_v2.quantile(0.98)))
        folium.GeoJson(gj(a.round({"n_options_v2": 1}), ["nom_iris", "n_options_v2"]), name="Accessibilité (IRIS)", show=False,
                       style_function=lambda f: {"fillColor": cm3(min(f["properties"]["n_options_v2"] or 0, cm3.vmax)),
                                                 "color": "#999", "weight": 0.3, "fillOpacity": 0.6}).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    path = path or SHARE / "carte_apercu.html"
    m.save(str(path))
    return path


# ---------------------------------------------------------------------------------------------
def dep_of(codes: pd.Series) -> pd.Series:
    codes = pd.Series(codes, dtype="string")
    return codes.str[:3].where(codes.str.startswith("97"), codes.str[:2])


def weighted_mean(values: pd.Series, weights: pd.Series, key: pd.Series) -> pd.Series:
    ok = values.notna()
    return (values[ok] * weights[ok]).groupby(key[ok]).sum() / weights[ok].groupby(key[ok]).sum()


def france_tables(log: list) -> dict[str, gpd.GeoDataFrame | pd.DataFrame]:
    """Agrégats France entière (département, EPCI, commune) + classement : rien au carreau."""
    import pyogrio

    from src.ingest.archives import ign_gpkg
    from src.national.common import national
    from src.national.ranking import security_by_commune, security_rates

    ade = ign_gpkg("admin_express")
    rank = pd.read_parquet(national("classement_epci.parquet"))
    sec = security_by_commune()

    com = pyogrio.read_dataframe(ade, layer="commune", columns=["code_insee", "nom_officiel", "codes_siren_des_epci"])
    com = com.rename(columns={"nom_officiel": "nom"})
    com["code_epci"] = com.pop("codes_siren_des_epci").fillna("").str.split(r"[/,; ]+").str[0].replace("", None)
    com["dep"] = dep_of(com["code_insee"]).to_numpy()

    # stations Citiz par commune (et département)
    off = pd.read_parquet(national("offer.parquet"), columns=["type", "sous_type", "capacite", "lon", "lat"])
    cz = off[(off["type"] == "citiz") & (off["sous_type"] == "station")]
    pts = gpd.GeoDataFrame(cz, geometry=gpd.points_from_xy(cz["lon"], cz["lat"]), crs=4326)
    j = gpd.sjoin(pts, com[["code_insee", "dep", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    log.append(f"stations Citiz hors commune (en mer, frontière) : {int(j['code_insee'].isna().sum())} / {len(j)}")

    # communes
    agg_c = pd.read_parquet(national("agg_commune.parquet"))
    c = com.merge(agg_c, on="code_insee", how="inner")
    c["stations_citiz"] = c["code_insee"].map(j.groupby("code_insee").size()).fillna(0).astype(int)
    c["vehicules_citiz"] = c["code_insee"].map(j.groupby("code_insee")["capacite"].sum()).fillna(0)
    c = c.merge(security_rates(sec, sec.index), left_on="code_insee", right_index=True, how="left")
    small = c["population"] < RISK_MIN_POP
    c.loc[small, ["vols_vehicules_1000", "degradations_1000"]] = np.nan
    ep = rank[["code_epci", "nom", "score_potentiel_citiz", "rang_potentiel"]].rename(
        columns={"nom": "nom_epci", "score_potentiel_citiz": "score_potentiel_epci", "rang_potentiel": "rang_potentiel_epci"})
    c = c.merge(ep, on="code_epci", how="left")
    c["geometry"] = c.geometry.simplify(0.001).set_precision(1e-5)     # ≈ 100 m
    hidden = c["menages"] < MIN_MEN
    log.append(f"communes exclues (< {MIN_MEN} ménages) : {int(hidden.sum())} ; taux de vols masqués "
               f"(< {fr(RISK_MIN_POP)} hab.) : {int(small[~hidden].sum())} communes")
    cols_c = ["code_insee", "nom", "dep", "code_epci", "nom_epci"] + [k for k in agg_c if k != "code_insee"] + \
             ["stations_citiz", "vehicules_citiz", "vols_vehicules_1000", "degradations_1000",
              "score_potentiel_epci", "rang_potentiel_epci", "geometry"]
    communes_all = c
    c = gpd.GeoDataFrame(c.loc[~hidden, cols_c], geometry="geometry", crs=4326)

    # départements
    deps = pyogrio.read_dataframe(ade, layer="departement", columns=["code_insee", "nom_officiel"]).rename(
        columns={"code_insee": "dep", "nom_officiel": "nom"})
    agg_d = pd.read_parquet(national("agg_departement.parquet"))
    d = deps.merge(agg_d, on="dep", how="left")
    d["stations_citiz"] = d["dep"].map(j.groupby("dep").size()).fillna(0).astype(int)
    d["vehicules_citiz"] = d["dep"].map(j.groupby("dep")["capacite"].sum()).fillna(0)
    d = d.merge(security_rates(sec, dep_of(sec.index.to_series()).to_numpy()), left_on="dep", right_index=True, how="left")
    ca = communes_all
    d["score_potentiel_moyen"] = d["dep"].map(weighted_mean(ca["score_potentiel_epci"], ca["population"], ca["dep"]))
    d["part_pop_epci_classes"] = d["dep"].map(ca[ca["score_potentiel_epci"].notna()].groupby("dep")["population"].sum()
                                              / ca.groupby("dep")["population"].sum())
    best = ca.dropna(subset=["rang_potentiel_epci"]).sort_values("rang_potentiel_epci").drop_duplicates("dep").set_index("dep")
    d["meilleur_epci"] = d["dep"].map(best["nom_epci"])
    d["meilleur_rang"] = d["dep"].map(best["rang_potentiel_epci"])
    d["geometry"] = d.geometry.simplify(0.002)                         # ≈ 200 m
    d = gpd.GeoDataFrame(d.sort_values("dep"), geometry="geometry", crs=4326)

    # EPCI (toutes) + classement
    geo = gpd.read_parquet(national("geo_epci.parquet"))[["code_epci", "geometry"]]
    e = gpd.GeoDataFrame(rank.merge(geo, on="code_epci", how="left"), geometry="geometry", crs=4326)
    first = ["rang_potentiel", "code_epci", "nom", "nature"]
    e = e[first + [k for k in e.columns if k not in first]]
    cl = pd.DataFrame(e.drop(columns="geometry")).dropna(subset=["score_potentiel_citiz"]).sort_values("rang_potentiel")

    return {"france_departements": round_counts(d), "france_epci": round_counts(e),
            "france_communes": round_counts(c), "france_classement_epci": round_counts(cl)}


FRANCE_MAP = {  # indicateur -> (libellé, format, valeurs fortes en rouge ?)
    "part_pop_sans_option": ("Population sans aucune option à 5 min", "{:.0%}", True),
    "n_options_moyen": ("Options pondérées à 5 min par habitant", "{:.1f}", True),
    "part_pop_citiz_5min": ("Population à 5 min d'une station Citiz", "{:.1%}", True),
    "part_menages_sans_voiture": ("Ménages sans voiture", "{:.0%}", True),
    "score_potentiel_moyen": ("Potentiel Citiz moyen (EPCI classés)", "{:.2f}", True),
    "vols_vehicules_1000": ("Vols liés aux véhicules / 1 000 hab. / an", "{:.1f}", True),
}


def write_france_map(deps: gpd.GeoDataFrame, epci: gpd.GeoDataFrame, citiz: pd.DataFrame, path: Path) -> Path:
    import branca.colormap as cm
    import folium

    from app.ui import RAMP

    colors = ["#%02x%02x%02x" % tuple(c) for c in RAMP]
    m = folium.Map(location=[46.6, 2.4], zoom_start=6, tiles=None)
    folium.TileLayer("CartoDB positron", control=False).add_to(m)
    g = deps.copy()
    g["geometry"] = g.geometry.simplify(0.01).set_precision(1e-3)   # ≈ 1 km : HTML léger
    tip_cols, aliases = ["nom", "dep", "pop_txt"], ["Département", "Code", "Habitants"]
    g["pop_txt"] = g["population"].map(lambda v: fr(v) if pd.notna(v) else "n.d.")
    for col, (label, f, _) in FRANCE_MAP.items():
        g[f"{col}_txt"] = g[col].map(lambda v, f=f: f.format(v).replace(".", ",") if pd.notna(v) else "n.d.")
        tip_cols.append(f"{col}_txt")
        aliases.append(label)
    g["meilleur_txt"] = (g["meilleur_epci"].fillna("—") + g["meilleur_rang"].map(lambda r: f" (rang {r:.0f})" if pd.notna(r) else ""))
    tip_cols.append("meilleur_txt")
    aliases.append("EPCI le mieux classé")
    for i, (col, (label, _, hot)) in enumerate(FRANCE_MAP.items()):
        v = g[col].dropna()
        cmap = cm.LinearColormap(colors if hot else colors[::-1], vmin=float(v.quantile(0.02)), vmax=float(v.quantile(0.98)))
        fg = folium.FeatureGroup(name=f"{label} (rouge = élevé)", overlay=False, show=i == 0)
        folium.GeoJson(g[[col] + tip_cols + ["geometry"]].__geo_interface__,
                       style_function=lambda ft, col=col, cmap=cmap: {
                           "fillColor": cmap(min(max(ft["properties"][col], cmap.vmin), cmap.vmax))
                           if ft["properties"][col] is not None else "#dddddd",
                           "color": "#ffffff", "weight": 0.6, "fillOpacity": 0.75},
                       tooltip=folium.GeoJsonTooltip(tip_cols, aliases=aliases)).add_to(fg)
        fg.add_to(m)
    fg = folium.FeatureGroup(name=f"Stations Citiz ({len(citiz)})", show=False)
    for r in citiz.itertuples():
        folium.CircleMarker([r.lat, r.lon], radius=2, color="#e6007e", fill=True, fill_opacity=0.9, weight=0).add_to(fg)
    fg.add_to(m)
    top = epci.dropna(subset=["rang_potentiel"]).nsmallest(20, "rang_potentiel")
    fg = folium.FeatureGroup(name="Top 20 EPCI potentiel Citiz", show=True)
    for r in top.itertuples():
        p = r.geometry.representative_point()
        folium.Marker([p.y, p.x], tooltip=f"#{r.rang_potentiel:.0f} {r.nom} — {fr(r.population)} hab., "
                                          f"score {r.score_potentiel_citiz:.2f}".replace(".", ","),
                      icon=folium.DivIcon(html=f'<div style="font:bold 11px sans-serif;color:#fff;background:#222;'
                                               f'border-radius:9px;padding:1px 5px;">{r.rang_potentiel:.0f}</div>')).add_to(fg)
    fg.add_to(m)
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:12px;left:12px;z-index:9999;background:#fff;padding:6px 10px;'
        'font:12px sans-serif;border-radius:4px;box-shadow:0 0 4px #888;max-width:340px">'
        "<b>France entière, accessibilité à 5 min (V1, vol d'oiseau)</b><br>Un indicateur à la fois (menu en haut à "
        "droite) ; bleu = faible, rouge = élevé. Guadeloupe, Guyane, Mayotte en gris : pas de population au carreau. "
        "DROM : faire glisser la carte.</div>"))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(str(path))
    return path


def write_zip(path: Path, files: list[tuple[Path, str]]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f, arc in files:
            if f.exists():
                z.write(f, arc)
    return path


def export_france(log: list) -> tuple[list[dict], list[Path]]:
    from src.national.common import national

    folder = SHARE / FRANCE
    folder.mkdir(parents=True, exist_ok=True)
    tables = france_tables(log)
    infos = []
    for name, t in tables.items():
        if isinstance(t, gpd.GeoDataFrame):
            infos.append(export_table(name, t, log, sub=FRANCE, geojson=False))
        else:                                                           # classement : CSV seul, trié par rang
            p = folder / f"{name}.csv"
            round_floats(t).to_csv(p, sep=";", decimal=",", index=False, encoding="utf-8-sig")
            infos.append({"table": name, "dossier": FRANCE, "lignes": len(t), "colonnes": list(t.columns),
                          "fichiers": {"csv": p.stat().st_size}})
    off = pd.read_parquet(national("offer.parquet"), columns=["type", "sous_type", "lon", "lat"])
    citiz = off[(off["type"] == "citiz") & (off["sous_type"] == "station")]
    carte = write_france_map(tables["france_departements"], tables["france_epci"], citiz,
                             folder / "carte_france_departements.html")
    return infos, [carte]


def export_city(ville: str, log: list, sub: str = "", prefix: str = "") -> tuple[list[dict], list[Path]]:
    set_city(ville)
    layers: dict[str, gpd.GeoDataFrame] = {}

    zone = gpd.read_file(city_processed("zone.gpkg"))
    zone["superficie_km2"] = zone.area / 1e6
    zone["date_du_recensement"] = pd.to_datetime(zone["date_du_recensement"]).dt.date.astype(str)
    layers["zone_communes"] = zone

    cells = gpd.read_parquet(city_processed("population.parquet"))
    nom = zone.set_index("code_insee")["nom"]
    layers["population_carreaux"] = cells[cells.men >= MIN_MEN].assign(nom_commune=lambda d: d.code_insee.map(nom))
    iris = iris_aggregate(cells)
    layers["population_iris"] = round_counts(iris[iris.men >= MIN_MEN])
    log.append(f"{ville} : carreaux exclus (< {MIN_MEN} ménages) : {int((cells.men < MIN_MEN).sum())} ; "
               f"IRIS exclus : {int((iris.men < MIN_MEN).sum())}")

    served = city_processed("offer_served.parquet")
    layers["offre"] = gpd.read_parquet(served if served.exists() else city_processed("offer.parquet"))
    if city_processed("access_cells.parquet").exists():
        ac = gpd.read_parquet(city_processed("access_cells.parquet"))
        layers["acces_carreaux"] = ac[ac.men >= MIN_MEN]
    if city_processed("access_iris.parquet").exists():
        ai = gpd.read_parquet(city_processed("access_iris.parquet"))
        layers["acces_iris"] = round_counts(ai[ai.menages >= MIN_MEN] if "menages" in ai else ai)
    reco = sorted(city_processed().glob("recommandations_ilp_500000_v2.csv")) or sorted(city_processed().glob("recommandations_ilp_500000*.csv"))
    if reco:
        r = pd.read_csv(reco[0], sep=";", decimal=",", dtype={"code_iris": str})
        layers["recommandations"] = gpd.GeoDataFrame(r, geometry=gpd.points_from_xy(r["x"], r["y"]), crs=zone.crs)

    folder = SHARE / sub
    infos = [export_table(prefix + name, g, log, sub=sub, geojson=not sub) for name, g in layers.items()]
    for f in sorted(city_processed().glob("recommandations_*_v[12].csv")) if sub else []:   # tous budgets / méthodes, V1 et V2
        (folder / f.name).write_bytes(f.read_bytes())
    for f in ("reco_resume_v1.json", "reco_resume_v2.json", "served_by_type.csv", "access_comparaison.json") if sub else ():
        if city_processed(f).exists():
            (folder / f).write_bytes(city_processed(f).read_bytes())
    carte = folder / ("carte_apercu.html" if not sub else f"carte_{ville}.html")
    return infos, [write_map(layers, carte)]


def export_grenoble(log: list) -> tuple[list[dict], list[Path]]:
    return export_city("grenoble", log)


def export_nantes(log: list) -> tuple[list[dict], list[Path]]:
    return export_city("nantes", log, sub=NANTES, prefix="nantes_")


def export_all(parts: tuple[str, ...] = ("grenoble", "nantes", "france")) -> None:
    SHARE.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    meta = load_exports_meta()
    maps: list[Path] = []
    for part, fn in (("grenoble", export_grenoble), ("nantes", export_nantes), ("france", export_france)):
        if part in parts:
            meta[part], m = fn(log)
            maps += m
    (SHARE / EXPORTS_META).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    dico = write_dictionary(meta, log)

    stamp = dt.date.today().strftime("%Y%m%d")
    docs = [(ROOT / "docs" / d, d) for d in ("methodologie.md", "sources.md", "ethique.md")]
    zips = []
    if "grenoble" in parts:
        files = [(f, f.name) for f in sorted(SHARE.iterdir())
                 if f.is_file() and f.suffix != ".zip" and not f.name.startswith(".")]
        zips.append(write_zip(SHARE / f"hackathon_grenoble_donnees_propres_{stamp}.zip", files + docs[:2]))
    if "nantes" in parts:
        files = [(f, f"{NANTES}/{f.name}") for f in sorted((SHARE / NANTES).iterdir())
                 if f.is_file() and not re.fullmatch(r"recommandations_[a-z]+_\d+\.csv", f.name)]   # anciennes sorties sans version
        extra = [(ROOT / "docs" / d, d) for d in ("modele.md", "decisions.md", "choix_ville.md", "chiffres_cles.md")]
        zips.append(write_zip(SHARE / f"hackathon_nantes_donnees_propres_{stamp}.zip", files + [(dico, dico.name)] + docs + extra))
    if "france" in parts:
        files = [(f, f"{FRANCE}/{f.name}") for f in sorted((SHARE / FRANCE).iterdir()) if f.is_file()]
        zips.append(write_zip(SHARE / f"hackathon_france_donnees_propres_{stamp}.zip", files + [(dico, dico.name)] + docs))

    print("\nTable                      lignes  fichiers")
    for part in parts:
        for i in meta[part]:
            print(f"{i['table']:<26} {i['lignes']:>6}  " + "  ".join(f"{k} {v / 1024 ** 2:.1f} Mo" for k, v in i["fichiers"].items()))
    print(f"\n{dico.name}")
    for carte in maps:
        print(f"{carte.relative_to(SHARE)} : {carte.stat().st_size / 1024 ** 2:.1f} Mo")
        if carte.stat().st_size > 5 * 1024 ** 2:
            print(f"  ATTENTION : {carte.name} dépasse 5 Mo : ne pas la commiter (retirer l'exception du .gitignore)")
    for z in zips:
        print(f"ZIP : {z.name} : {z.stat().st_size / 1024 ** 2:.1f} Mo")
    for line in log:
        print("  -", line)


# ---------------------------------------------------------------------------------------------
def estimate_raw_zone() -> dict:
    """Taille estimée d'un zip des données BRUTES limitées à la zone de Grenoble (rien n'est écrit)."""
    set_city("grenoble")
    from src.ingest.archives import filosofi_gpkg, ign_gpkg
    from src.ingest.zone import load_zone
    import pyogrio

    zone = load_zone()
    bbox_l93 = tuple(zone.total_bounds)
    bbox_wgs = tuple(zone.to_crs(4326).total_bounds)
    est, notes = {}, {}

    def size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size

    # tels quels (déjà limités à Grenoble ou petits)
    for key, p in {"gtfs (6 réseaux filtrés Grenoble)": raw("gtfs"), "gbfs_citiz (15 réseaux)": raw("gbfs_citiz"),
                   "gbfs Voi Grenoble": raw("gbfs_all", "voi-trottinettes-et-velos-aire-grenobloise"),
                   "historique Citiz collecté": raw("gbfs_history"),
                   "catalogue transport.data.gouv.fr": raw("transport_data_gouv"),
                   "manifest.csv + check_report.md": raw("manifest.csv")}.items():
        est[key] = size(p)
    est["manifest.csv + check_report.md"] += raw("check_report.md").stat().st_size

    # découpés sur la zone : taille ∝ nombre d'entités (GeoPackage écrit à partir de la source)
    filo = filosofi_gpkg()
    n_filo = len(pyogrio.read_dataframe(filo, bbox=bbox_l93, columns=["idcar_200m"], read_geometry=False))
    est["Filosofi 200 m (carreaux de la zone)"] = filo.stat().st_size * n_filo / pyogrio.read_info(filo)["features"]
    est["ADMIN EXPRESS (communes + EPCI de la zone)"] = city_processed("zone.gpkg").stat().st_size * 1.2
    ir = ign_gpkg("iris")
    n_ir = len(pyogrio.read_dataframe(ir, bbox=bbox_wgs, columns=["code_iris"], read_geometry=False))
    est["Contours IRIS (zone)"] = ir.stat().st_size * n_ir / pyogrio.read_info(ir)["features"]
    bpe = pd.read_parquet(raw("insee", "bpe25.parquet"), columns=["DEPCOM"])
    share_bpe = bpe["DEPCOM"].isin(zone["code_insee"]).mean()
    est["BPE 2025 (équipements de la zone)"] = raw("insee", "bpe25.parquet").stat().st_size * share_bpe
    iris_tab = pd.read_parquet(processed("cache", "logement_iris.parquet"))
    share_log = iris_tab["code_iris"].str[:5].isin(zone["code_insee"]).mean()
    est["Logement IRIS 2023 (lignes de la zone, CSV)"] = 34.5e6 * share_log * 0.6
    est["Omphale (projections, inchangé)"] = raw("insee", "projections_omphale_2021_2070.zip").stat().st_size
    # OSM : voies de la zone (GeoPackage) ; la zone + 1,3 km fait ~2,5 % de la surface de Rhône-Alpes mais
    # concentre une part bien plus forte des objets (urbain dense) : fourchette 6-12 % du PBF, × 3 en GeoPackage
    pbf = raw("osm", "rhone-alpes-latest.osm.pbf").stat().st_size
    notes["OSM"] = (0.06 * pbf * 3, 0.12 * pbf * 3)
    est["OSM voies de la zone (GeoPackage) [estimation haute]"] = notes["OSM"][1]

    total = sum(est.values())
    # compression zip : GTFS/7z/zip/parquet déjà compressés ; GeoPackage/CSV/JSON ≈ ÷ 3
    compressible = sum(v for k, v in est.items() if any(s in k for s in ("Filosofi", "ADMIN", "IRIS", "Logement", "OSM", "gbfs", "historique", "catalogue", "manifest")))
    zipped = total - compressible + compressible / 3
    print(f"{'Élément':<55} {'Mo':>8}")
    for k, v in est.items():
        print(f"{k:<55} {v / 1e6:>8.1f}")
    print(f"{'TOTAL non compressé':<55} {total / 1e6:>8.1f}")
    lo = zipped - (notes["OSM"][1] - notes["OSM"][0]) / 3
    print(f"ZIP estimé : {lo / 1e6:.0f} à {zipped / 1e6:.0f} Mo (OSM : fourchette {notes['OSM'][0] / 1e6:.0f}-{notes['OSM'][1] / 1e6:.0f} Mo avant compression)")
    return {"elements": est, "zip_min": lo, "zip_max": zipped}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estimate-raw-zone", action="store_true", help="estime la taille d'un zip des données brutes de la zone")
    ap.add_argument("--only", choices=["grenoble", "nantes", "france"], help="n'exporter qu'une partie (défaut : toutes)")
    a = ap.parse_args()
    estimate_raw_zone() if a.estimate_raw_zone else export_all((a.only,) if a.only else ("grenoble", "nantes", "france"))
