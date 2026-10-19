import importlib.util

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.common.config import ROOT, processed

spec = importlib.util.spec_from_file_location("export_share", ROOT / "scripts" / "export_share.py")
es = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es)


def test_export_table_formats(tmp_path, monkeypatch):
    monkeypatch.setattr(es, "SHARE", tmp_path)
    g = gpd.GeoDataFrame({"id": ["a", "b"], "passages_jour": [12.345678, None]},
                         geometry=[Point(913000, 6458000), Point(914000, 6459000)], crs=2154)
    info = es.export_table("offre", g, [])
    raw = (tmp_path / "offre.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                                   # BOM pour Excel
    header, first = raw[3:].decode("utf-8").splitlines()[:2]
    assert header == "id;passages_jour;latitude;longitude"
    assert "12,3457" in first and first.count(";") == 3                      # virgule décimale, séparateur ;
    lat = float(first.split(";")[2].replace(",", "."))
    assert 45.1 < lat < 45.3                                                  # Lambert-93 -> WGS84
    assert set(info["fichiers"]) == {"gpkg", "csv", "geojson"}
    assert gpd.read_file(tmp_path / "offre.gpkg").crs.to_epsg() == 2154


def test_geojson_skipped_when_too_big(tmp_path, monkeypatch):
    monkeypatch.setattr(es, "SHARE", tmp_path)
    monkeypatch.setattr(es, "GEOJSON_MAX", 10)
    g = gpd.GeoDataFrame({"id": ["a"]}, geometry=[box(0, 0, 1, 1)], crs=2154)
    log = []
    info = es.export_table("zone_communes", g, log)
    assert "geojson" not in info["fichiers"] and not (tmp_path / "zone_communes.geojson").exists() and log


@pytest.mark.skipif(not processed("population.parquet").exists(), reason="données réelles absentes")
def test_every_real_column_is_documented():
    tables = [gpd.read_file(processed("zone.gpkg")), gpd.read_parquet(processed("population.parquet")),
              gpd.read_parquet(processed("offer.parquet"))]
    cols = {c for t in tables for c in t.columns if c != "geometry"} | {"latitude", "longitude", "nom_commune", "superficie_km2"}
    assert cols - set(es.COLUMNS) == set()
