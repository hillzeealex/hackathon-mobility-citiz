from src.common.config import ROOT, load_settings, processed, raw


def test_settings_keys():
    s = load_settings()
    for key in ("study_area", "crs", "walk", "offer", "mode_weights", "costs", "privacy", "paths"):
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
