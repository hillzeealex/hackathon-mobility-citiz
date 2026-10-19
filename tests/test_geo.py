import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.common.geo import dedup_points, valid_coords


def make(points):
    """points : [(id, type, x, y, passages)] en Lambert-93."""
    df = pd.DataFrame(points, columns=["id", "type", "x", "y", "passages_jour"])
    return gpd.GeoDataFrame(df.drop(columns=["x", "y"]),
                            geometry=[Point(x, y) for x, y in zip(df.x, df.y)], crs=2154)


def test_two_platforms_merged_with_summed_frequency():
    g = make([("a", "bus", 0, 0, 100), ("b", "bus", 30, 0, 80), ("c", "bus", 400, 0, 50)])
    out, st = dedup_points(g, radius=40)
    assert len(out) == 2
    merged = out[out.n_fusionnes == 2].iloc[0]
    assert merged.passages_jour == 180
    assert merged.geometry.x == pytest.approx(15)
    assert set(merged.ids_fusionnes.split("|")) == {"a", "b"}
    assert st.loc[0, "avant"] == 3 and st.loc[0, "apres"] == 2


def test_different_modes_never_merged():
    g = make([("a", "bus", 0, 0, 10), ("t", "tram", 5, 0, 10)])
    out, st = dedup_points(g, radius=40)
    assert len(out) == 2 and st.fusionnes.sum() == 0


def test_boundary_and_chaining():
    # 39 m : fusion ; 41 m : pas de fusion ; chaîne a-b-c à 35 m : un seul groupe (lien simple)
    g = make([("a", "bus", 0, 0, 1), ("b", "bus", 35, 0, 1), ("c", "bus", 70, 0, 1),
              ("d", "velo", 0, 1000, 1), ("e", "velo", 41, 1000, 1)])
    out, _ = dedup_points(g, radius=40)
    assert sorted(out.n_fusionnes.tolist()) == [1, 1, 3]


def test_requires_metric_crs():
    g = make([("a", "bus", 0, 0, 1)]).set_crs(4326, allow_override=True)
    with pytest.raises(ValueError):
        dedup_points(g, radius=40)


def test_valid_coords():
    lon = pd.Series([5.72, 0, 5.72, None, -120])
    lat = pd.Series([45.18, 0, 145, 45, 45])
    assert valid_coords(lon, lat).tolist() == [True, False, False, False, False]


def test_missing_values_stay_missing():
    g = make([("a", "velo", 0, 0, None), ("b", "velo", 10, 0, None)])
    out, _ = dedup_points(g, radius=40)
    assert len(out) == 1 and pd.isna(out.passages_jour.iloc[0])


def test_radius_per_group():
    g = make([("a", "train", 0, 0, 1), ("b", "train", 120, 0, 1), ("c", "bus", 0, 500, 1), ("d", "bus", 120, 500, 1)])
    out, _ = dedup_points(g, radius={"default": 40, "train": 150})
    assert sorted(out.groupby("type").size().to_dict().items()) == [("bus", 2), ("train", 1)]


def test_cross_source_max_within_source_sum():
    # même arrêt : réseau local (2 quais, 60 + 40) et flux régional agrégé (100) -> 100, pas 200
    g = make([("a", "bus", 0, 0, 60), ("b", "bus", 20, 0, 40), ("c", "bus", 10, 5, 100)])
    g["source"] = ["local", "local", "regional"]
    out, _ = dedup_points(g, radius=40, source_col="source")
    assert len(out) == 1 and out.passages_jour.iloc[0] == 100
    out2, _ = dedup_points(g, radius=40)
    assert out2.passages_jour.iloc[0] == 200          # comportement historique (une seule source à Grenoble)
