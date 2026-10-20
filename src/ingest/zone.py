"""
Périmètre d'étude -> data/processed/zone.gpkg (une ligne par commune, Lambert-93)

- build_zone() : communes de l'EPCI (cities.<ville>.epci_siren) ou liste explicite (cities.<ville>.insee_communes),
  depuis ADMIN EXPRESS COG ; colonnes code_insee, nom, population (recensement, millésime ADMIN EXPRESS).
- load_zone() : lit zone.gpkg ; à défaut, se rabat PROVISOIREMENT sur le contour de l'EPCI servi par
  geo.api.gouv.fr (attribut `provisoire`).
- buffer_area() : zone élargie (offre chargée sur zone + offer.buffer_m).
"""
from __future__ import annotations

import urllib.request
import warnings

import geopandas as gpd
import pandas as pd

from src.common.config import city_from_args, city_processed, load_settings, raw, study_area

GEO_API = "https://geo.api.gouv.fr/epcis/{siren}?format=geojson&geometry=contour"


def select_communes(communes: pd.DataFrame, epci_siren: str | None, insee: list[str] | None) -> pd.Series:
    """Masque des communes du périmètre. `codes_siren_des_epci` peut lister plusieurs EPCI séparés par / , ;"""
    if insee:
        return communes["code_insee"].isin([str(c) for c in insee])
    if not epci_siren:
        raise ValueError("study_area : renseigner epci_siren ou insee_communes")
    sirens = communes["codes_siren_des_epci"].fillna("").str.split(r"[/,; ]+")
    return sirens.map(lambda s: str(epci_siren) in s)


def build_zone() -> gpd.GeoDataFrame:
    from src.ingest.archives import ign_gpkg

    s = load_settings()
    sa = study_area()
    gpkg = ign_gpkg("admin_express")
    cols = ["code_insee", "nom_officiel", "population", "codes_siren_des_epci", "date_du_recensement"]
    communes = gpd.read_file(gpkg, layer="commune", columns=cols)
    zone = communes[select_communes(communes, sa.get("epci_siren"), sa.get("insee_communes"))]
    if zone.empty:
        raise ValueError(f"aucune commune trouvée pour {sa}")
    zone = zone.rename(columns={"nom_officiel": "nom"}).to_crs(s["crs"]["metric"])
    zone = zone[["code_insee", "nom", "population", "date_du_recensement", "geometry"]].reset_index(drop=True)
    zone.to_file(city_processed("zone.gpkg"), driver="GPKG")
    print(f"zone.gpkg : {len(zone)} communes, {zone.population.sum():,} habitants "
          f"(recensement {zone.date_du_recensement.iloc[0]}), {zone.area.sum() / 1e6:.0f} km²")
    return zone


def _epci_contour(siren: str) -> gpd.GeoDataFrame:
    cache = raw("geo_cache", f"epci_{siren}.geojson")
    if not cache.exists():
        req = urllib.request.Request(GEO_API.format(siren=siren), headers={"User-Agent": "hackathon-mobility"})
        with urllib.request.urlopen(req, timeout=60) as r:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(r.read())
    zone = gpd.read_file(cache)[["nom", "geometry"]]
    zone.insert(0, "code_epci", siren)
    return zone.set_crs(4326, allow_override=True)


def load_zone() -> gpd.GeoDataFrame:
    """Communes (ou contour) de la zone d'étude, en CRS métrique."""
    s = load_settings()
    path = city_processed("zone.gpkg")
    if path.exists():
        zone = gpd.read_file(path)
        zone.attrs["provisoire"] = False
    else:
        warnings.warn("zone.gpkg absent : contour EPCI provisoire (geo.api.gouv.fr)", stacklevel=2)
        zone = _epci_contour(study_area()["epci_siren"])
        zone.attrs["provisoire"] = True
    return zone.to_crs(s["crs"]["metric"])


def buffer_area(zone: gpd.GeoDataFrame | None = None):
    """Zone + offer.buffer_m (géométrie Lambert-93) : emprise de l'offre prise en compte."""
    zone = load_zone() if zone is None else zone
    return zone.union_all().buffer(load_settings()["offer"]["buffer_m"])


if __name__ == "__main__":
    city_from_args()
    build_zone()
