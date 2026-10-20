import datetime as dt

import pytest

from src.common.config import (ROOT, city_from_args, city_processed, current_city, load_settings, processed,
                               raw, set_city, study_area)


def test_settings_keys():
    s = load_settings()
    for key in ("default_city", "cities", "gtfs_exclude_patterns", "crs", "walk", "offer", "mode_weights", "costs", "privacy", "paths"):
        assert key in s
    assert s["crs"]["metric"] == "EPSG:2154"


def test_walk_radius_matches_5_minutes():
    w = load_settings()["walk"]
    distance_m = w["speed_kmh"] * 1000 / 60 * w["minutes"]
    assert abs(distance_m - w["radius_m"]) <= 0.05 * w["radius_m"]


def test_paths_anchored_on_repo_root():
    assert (ROOT / "src" / "ingest").is_dir()
    assert raw("x.json") == ROOT / "data" / "raw" / "x.json"
    assert processed("x.parquet").parent.is_dir()


def test_cities_have_required_keys():
    for name, c in load_settings()["cities"].items():
        assert {"name", "epci_siren", "osm_region", "gtfs_feeds"} <= set(c), name
    assert {"grenoble", "nantes"} <= set(load_settings()["cities"])


def test_typical_weekday_is_a_fixed_tuesday():
    day = dt.date.fromisoformat(load_settings()["offer"]["typical_weekday"])
    assert day.weekday() == 1


def test_city_selection_and_paths(monkeypatch):
    monkeypatch.setenv("HACKATHON_VILLE", "grenoble")   # restauré après le test
    monkeypatch.delenv("HACKATHON_VILLE")
    assert current_city() == load_settings()["default_city"]
    assert city_from_args(["--ville", "nantes", "--autre", "x"]) == "nantes"
    assert study_area()["epci_siren"] == "244400404" and study_area()["ville"] == "nantes"
    assert city_processed("offer.parquet") == ROOT / "data" / "processed" / "nantes" / "offer.parquet"
    with pytest.raises(ValueError):
        set_city("paris")
    set_city("grenoble")
    assert city_processed("x.parquet").parent.name == "grenoble"
