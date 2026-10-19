"""
Export des données nettoyées pour l'équipe -> data/share/

    python scripts/export_share.py                 # GPKG + CSV + GeoJSON + dictionnaire + carte HTML + zip
    python scripts/export_share.py --estimate-raw-zone   # taille estimée d'un zip des données BRUTES de la zone

Pour chaque table disponible dans data/processed/ (zone, population, offre, accessibilité) :
  - <table>.gpkg     pour QGIS (Lambert-93, EPSG:2154)
  - <table>.csv      pour Excel (séparateur ;, UTF-8 avec BOM, virgule décimale, latitude/longitude WGS84)
  - <table>.geojson  pour le web (WGS84), seulement s'il fait moins de 50 Mo
Secret statistique : seuls les carreaux (et IRIS) d'au moins 11 ménages sont exportés.
Produit aussi DICTIONNAIRE_DONNEES.md, carte_apercu.html (folium) et le zip daté.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.config import ROOT, load_settings, processed, raw  # noqa: E402

SHARE = ROOT / "data" / "share"
GEOJSON_MAX = 50 * 1024 ** 2
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

TABLES = {  # nom exporté -> (description, ce qui a été fait)
    "zone_communes": ("Les 49 communes de Grenoble-Alpes-Métropole (périmètre d'étude).", []),
    "population_carreaux": ("Population et caractéristiques socio-économiques par carreau de 200 m.", []),
    "population_iris": ("Agrégat par IRIS de TOUS les carreaux (y compris < 11 ménages) : affichage public recommandé. "
                        "**Effectifs (pop_calee, ind, men, men_pauv) arrondis à 5 près** (secret statistique) ; "
                        "ratios calculés sur les valeurs exactes.", []),
    "offre": ("Tous les points d'offre de mobilité (arrêts TC, stations Citiz, zones Voi) sur la zone + 800 m.", []),
    "acces_carreaux": ("Indicateurs d'accessibilité à 5 min par carreau (phase 3).", []),
    "acces_iris": ("Indicateurs d'accessibilité agrégés par IRIS (phase 3).", []),
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


def export_table(name: str, g: gpd.GeoDataFrame, log: list) -> dict:
    g = with_latlon(round_floats(g))
    info = {"table": name, "lignes": len(g), "colonnes": [c for c in g.columns if c != "geometry"], "fichiers": {}}
    gp = SHARE / f"{name}.gpkg"
    gp.unlink(missing_ok=True)
    g.to_file(gp, layer=name, driver="GPKG")
    info["fichiers"]["gpkg"] = gp.stat().st_size
    csv = SHARE / f"{name}.csv"
    pd.DataFrame(g.drop(columns="geometry")).to_csv(csv, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    info["fichiers"]["csv"] = csv.stat().st_size
    gj = g.drop(columns=["latitude", "longitude"]).to_crs(4326).to_json(drop_id=True, to_wgs84=True)
    gj_path = SHARE / f"{name}.geojson"
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


def cleaning_notes() -> list[str]:
    s = load_settings()
    notes = []
    rep = processed("population_rapport.json")
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
    dd = processed("offer_dedup_stats.csv")
    if dd.exists():
        d = pd.read_csv(dd)
        detail = ", ".join(f"{x.type} {x.avant}→{x.apres}" for x in d.itertuples())
        notes.append(f"**Dédoublonnage de l'offre** : points d'un même mode à moins de {s['offer']['dedup_m']} m fusionnés "
                     f"(train : {s['offer'].get('dedup_m_by_type', {}).get('train', '-')} m) ; {detail}.")
    gr = processed("offer_gtfs_report.csv")
    if gr.exists():
        g = pd.read_csv(gr)
        days = sorted(set(g["jour_type"].dropna()))
        notes.append(f"**Jour type GTFS** : mardi le plus chargé des 8 prochaines semaines couvertes par chaque réseau "
                     f"({', '.join(days)}) : évite les vacances scolaires. `frequencies.txt` converti en départs réels.")
    notes += [
        f"**Zone tampon** : l'offre est chargée sur la métropole + {s['offer']['buffer_m']} m (colonne `dans_zone`).",
        "**Exclusions** : lignes de covoiturage M covoit' ; flux GBFS « Dott France » (doublon) ; emplacement interne "
        "« DEMOBOX (Réservé Citiz) ».",
        "**Corrections de typage GTFS** : `route_type = 5` du téléphérique -> téléphérique ; arrêts SNCF « OCECar » "
        "(autocars de substitution) -> bus.",
        "**Zones Voi** : chaque zone de stationnement donne un point `velo` et un point `trottinette`.",
        "**Coordonnées** : filtrage des points (0,0) ou hors de France métropolitaine.",
    ]
    return notes


def write_dictionary(infos: list[dict], log: list) -> Path:
    lines = ["# Dictionnaire des données — Hackathon Mobility Grenoble (Epitech × Citiz)", "",
             f"Généré par `scripts/export_share.py` le {dt.date.today().isoformat()}. "
             "Méthode détaillée : `docs/methodologie.md` ; sources : `docs/sources.md`.", "",
             "## Formats", "",
             "| Format | Pour qui | Détails |", "|---|---|---|",
             "| `.csv` | Excel | séparateur `;`, UTF-8 avec BOM, virgule décimale ; colonnes `latitude`/`longitude` en WGS84 (centroïde pour les surfaces), pas de géométrie |",
             "| `.gpkg` | QGIS | géométries complètes, Lambert-93 (EPSG:2154) |",
             "| `.geojson` | web, outils en ligne | WGS84 (EPSG:4326), produit si < 50 Mo |",
             "| `carte_apercu.html` | tout le monde | double-clic : carte interactive de toutes les couches (connexion internet requise pour le fond de carte) |",
             "", "## Choix de nettoyage", ""] + [f"- {n}" for n in cleaning_notes()] + [""]
    for info in infos:
        desc = TABLES.get(info["table"], ("", []))[0]
        size = ", ".join(f"{k} {fr(v / 1024 ** 2, 1)} Mo" for k, v in info["fichiers"].items())
        lines += [f"## {info['table']}", "", desc, "", f"**{fr(info['lignes'])} lignes** — fichiers : {size}", "",
                  "| Colonne | Signification | Unité | Source |", "|---|---|---|---|"]
        for c in info["colonnes"]:
            sig, unit, src = COLUMNS.get(c, ("**à documenter**", "", ""))
            if c not in COLUMNS:
                log.append(f"colonne non documentée : {info['table']}.{c}")
            lines.append(f"| `{c}` | {sig} | {unit} | {src} |")
        lines.append("")
    path = SHARE / "DICTIONNAIRE_DONNEES.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------------
TYPE_COLORS = {"bus": "#0072b2", "tram": "#d55e00", "train": "#555555", "telepherique": "#009e73",
               "velo": "#2ca02c", "trottinette": "#bcbd22", "citiz": "#e6007e", "metro": "#cc79a7"}


def write_map(layers: dict[str, gpd.GeoDataFrame]) -> Path:
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
    path = SHARE / "carte_apercu.html"
    m.save(str(path))
    return path


# ---------------------------------------------------------------------------------------------
def export_all() -> None:
    SHARE.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    layers: dict[str, gpd.GeoDataFrame] = {}

    zone = gpd.read_file(processed("zone.gpkg"))
    zone["superficie_km2"] = zone.area / 1e6
    zone["date_du_recensement"] = pd.to_datetime(zone["date_du_recensement"]).dt.date.astype(str)
    layers["zone_communes"] = zone

    cells = gpd.read_parquet(processed("population.parquet"))
    nom = zone.set_index("code_insee")["nom"]
    layers["population_carreaux"] = cells[cells.men >= MIN_MEN].assign(nom_commune=lambda d: d.code_insee.map(nom))
    iris = iris_aggregate(cells)
    layers["population_iris"] = round_counts(iris[iris.men >= MIN_MEN])
    log.append(f"carreaux exclus (< {MIN_MEN} ménages) : {int((cells.men < MIN_MEN).sum())} ; "
               f"IRIS exclus : {int((iris.men < MIN_MEN).sum())}")

    layers["offre"] = gpd.read_parquet(processed("offer.parquet"))
    if processed("access_cells.parquet").exists():
        ac = gpd.read_parquet(processed("access_cells.parquet"))
        layers["acces_carreaux"] = ac[ac.men >= MIN_MEN]
    if processed("access_iris.parquet").exists():
        ai = gpd.read_parquet(processed("access_iris.parquet"))
        layers["acces_iris"] = round_counts(ai[ai.menages >= MIN_MEN] if "menages" in ai else ai)
    else:
        log.append("tables d'accessibilité absentes (phase 3 en cours) : non exportées")

    infos = [export_table(name, g, log) for name, g in layers.items()]
    dico = write_dictionary(infos, log)
    carte = write_map(layers)

    stamp = dt.date.today().strftime("%Y%m%d")
    zpath = SHARE / f"hackathon_grenoble_donnees_propres_{stamp}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(SHARE.iterdir()):
            if f.is_file() and f.suffix != ".zip":
                z.write(f, f.name)
        for doc in ("methodologie.md", "sources.md"):
            if (ROOT / "docs" / doc).exists():
                z.write(ROOT / "docs" / doc, doc)

    print("\nTable                    lignes  fichiers")
    for i in infos:
        print(f"{i['table']:<24} {i['lignes']:>6}  " + "  ".join(f"{k} {v / 1024 ** 2:.1f} Mo" for k, v in i["fichiers"].items()))
    print(f"\n{dico.name} ; {carte.name} : {carte.stat().st_size / 1024 ** 2:.1f} Mo")
    if carte.stat().st_size > 5 * 1024 ** 2:
        print("  ATTENTION : carte_apercu.html dépasse 5 Mo : ne pas la commiter (retirer l'exception du .gitignore)")
    print(f"ZIP : {zpath.name} : {zpath.stat().st_size / 1024 ** 2:.1f} Mo")
    for line in log:
        print("  -", line)


# ---------------------------------------------------------------------------------------------
def estimate_raw_zone() -> dict:
    """Taille estimée d'un zip des données BRUTES limitées à la zone (rien n'est écrit)."""
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
    est["ADMIN EXPRESS (communes + EPCI de la zone)"] = processed("zone.gpkg").stat().st_size * 1.2
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
    a = ap.parse_args()
    estimate_raw_zone() if a.estimate_raw_zone else export_all()
