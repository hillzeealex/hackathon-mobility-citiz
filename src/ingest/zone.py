"""
Périmètre d'étude.

- load_zone() : lit data/processed/zone.gpkg (construit depuis ADMIN EXPRESS) ; à défaut, se rabat
  PROVISOIREMENT sur le contour de l'EPCI servi par geo.api.gouv.fr (mis en cache), pour avancer
  avant la fin du téléchargement IGN. Le repli est signalé par l'attribut `provisoire`.
"""
from __future__ import annotations

import urllib.request
import warnings

import geopandas as gpd

from src.common.config import load_settings, processed, raw

GEO_API = "https://geo.api.gouv.fr/epcis/{siren}?format=geojson&geometry=contour"


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
    path = processed("zone.gpkg")
    if path.exists():
        zone = gpd.read_file(path)
        zone.attrs["provisoire"] = False
    else:
        warnings.warn("zone.gpkg absent : contour EPCI provisoire (geo.api.gouv.fr)", stacklevel=2)
        zone = _epci_contour(s["study_area"]["epci_siren"])
        zone.attrs["provisoire"] = True
    return zone.to_crs(s["crs"]["metric"])
