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


@pytest.mark.skipif(not processed("grenoble", "population.parquet").exists(), reason="données réelles absentes")
def test_every_real_column_is_documented():
    tables = [gpd.read_file(processed("grenoble", "zone.gpkg")), gpd.read_parquet(processed("grenoble", "population.parquet")),
              gpd.read_parquet(processed("grenoble", "offer.parquet"))]
    cols = {c for t in tables for c in t.columns if c != "geometry"} | {"latitude", "longitude", "nom_commune", "superficie_km2"}
    assert cols - set(es.COLUMNS) == set()


def test_round_counts_only_counts():
    df = pd.DataFrame({"pop_calee": [12.4, 13.0, 0.4], "men": [7, 8, 2], "part_sans_voiture": [0.123, 0.5, 0.9]})
    out = es.round_counts(df)
    assert out.pop_calee.tolist() == [10, 15, 0] and out.men.tolist() == [5, 10, 0]
    assert out.part_sans_voiture.tolist() == [0.123, 0.5, 0.9]       # ratios intacts
    assert df.pop_calee.tolist() == [12.4, 13.0, 0.4]                 # pas d'effet de bord


@pytest.mark.skipif(not (ROOT / "data" / "share" / "population_iris.csv").exists(), reason="export absent")
def test_shared_iris_counts_are_multiples_of_5():
    c = pd.read_csv(ROOT / "data" / "share" / "population_iris.csv", sep=";", decimal=",", encoding="utf-8-sig")
    for col in ("pop_calee", "ind", "men", "men_pauv"):
        assert (c[col] % 5 == 0).all(), col


def test_security_rates_group_communes():
    from src.national.ranking import security_rates
    sec = pd.DataFrame({"pop_3ans": [3000, 6000, 300], "vols": [30, None, 3], "degradations": [6, 12, None]},
                       index=pd.Index(["38185", "38421", "06088"], name="code_insee"))
    r = security_rates(sec, es.dep_of(sec.index.to_series()).to_numpy())
    assert r.loc["38", "vols_vehicules_1000"] == pytest.approx(1000 * 30 / 9000)   # commune sans fait : 0, pas NaN
    assert pd.isna(r.loc["06", "degradations_1000"])                                 # aucune donnée -> NaN


def test_dep_of_handles_drom_and_corsica():
    assert es.dep_of(pd.Series(["97411", "2A004", "06088"])).tolist() == ["974", "2A", "06"]


@pytest.mark.skipif(not processed("national", "classement_epci.parquet").exists(), reason="niveau 1 absent")
def test_every_france_column_is_documented():
    cols = set(pd.read_parquet(processed("national", "classement_epci.parquet")).columns) | \
        set(pd.read_parquet(processed("national", "agg_commune.parquet")).columns)
    extra = {"dep", "nom_epci", "score_potentiel_epci", "rang_potentiel_epci", "score_potentiel_moyen",
             "part_pop_epci_classes", "meilleur_epci", "meilleur_rang", "latitude", "longitude"}
    for t in ("france_communes", "france_departements", "france_epci"):
        assert {c for c in cols | extra if es.describe(t, c) is None} == set(), t


@pytest.mark.skipif(not (ROOT / "data" / "share" / "france" / "france_communes.csv").exists(), reason="export absent")
def test_shared_france_has_no_cells_and_rounded_counts():
    folder = ROOT / "data" / "share" / "france"
    assert not any("carreau" in f.name for f in folder.iterdir())
    c = pd.read_csv(folder / "france_communes.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype={"code_insee": str})
    assert (c["population"] % 5 == 0).all() and (c["menages"] >= 10).all()
    assert c.loc[c["population"] < es.RISK_MIN_POP, "vols_vehicules_1000"].isna().all()
