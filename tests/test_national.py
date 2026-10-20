import numpy as np
import pandas as pd
import pytest

from src.national.cells import centroids_from_id
from src.national.common import bbox_territory


def test_centroid_from_id_matches_filosofi_geometry():
    # carreau de Corse : centroïde de la géométrie Filosofi (Lambert-93) = (1225057.744, 6049923.811)
    x, y, lon, lat = centroids_from_id(pd.Series(["CRS3035RES200mN2029400E4259000"]), 2154)
    assert x[0] == pytest.approx(1225057.744, abs=0.5) and y[0] == pytest.approx(6049923.811, abs=0.5)
    assert 8 < lon[0] < 10 and 41 < lat[0] < 43


def test_centroid_drom_same_crs():
    x, y, lon, lat = centroids_from_id(pd.Series(["CRS5490RES200mN1592600E728800"]), 5490)
    assert (x[0], y[0]) == (728900, 1592700)                      # Martinique : +100 m, pas de reprojection
    assert -61.3 < lon[0] < -60.7 and 14.3 < lat[0] < 14.9


def test_mixed_crs_rejected():
    with pytest.raises(ValueError):
        centroids_from_id(pd.Series(["CRS3035RES200mN1E1", "CRS5490RES200mN1E1"]), 2154)


def test_bbox_territory():
    lon = np.array([5.72, -61.0, 55.5, 0.0, -120.0])
    lat = np.array([45.18, 14.6, -21.1, 0.0, 45.0])
    assert bbox_territory(lon, lat).tolist() == ["met", "972", "974", "", ""]


def test_coverage_and_demand():
    from scipy.spatial import cKDTree
    from src.national.access import coverage, demand
    cells = np.array([[0.0, 0.0], [300.0, 0.0], [1000.0, 0.0]])
    offer = np.array([[0.0, 0.0], [350.0, 0.0]])
    cov = coverage(cells, cKDTree(offer), 400, len(offer)).toarray()
    assert cov.tolist() == [[True, True], [True, True], [False, False]]   # distance 0 incluse
    d = demand(offer, cells, np.array([100.0, 50.0, 10.0]), 400)
    assert d.tolist() == [150.0, 150.0]


def test_aggregate_population_weighted():
    from src.national.access import aggregate
    a = pd.DataFrame({"idcar_200m": ["a", "b"], "code_iris": ["X", "X"], "pop_calee": [300.0, 100.0],
                      "men": [100.0, 50.0], "ind": [300.0, 100.0], "men_pauv": [10.0, 5.0], "ind_snv": [6e6, 2e6],
                      "n_points": [3, 0], "n_tc": [1, 0], "n_citiz": [0, 0], "n_options": [6.0, 0.5],
                      "acces_1000": [1.0, 2.0], "citiz_1000": [0.0, 0.0], "part_sans_voiture": [0.2, 0.5]})
    g = aggregate(a, "code_iris").iloc[0]
    assert g.n_options_moyen == pytest.approx((300 * 6 + 100 * 0.5) / 400)    # exemple de la méthodologie
    assert g.part_pop_sans_option == pytest.approx(0.25)
    assert g.part_menages_sans_voiture == pytest.approx((100 * 0.2 + 50 * 0.5) / 150)


def test_grid_sum_disk_on_200m_grid():
    from src.model.features import disk_kernel, grid_sum
    assert disk_kernel(400).sum() == 13          # centre + 4 voisins à 200 m + 4 diagonales (283 m) + 4 à 400 m
    cells = np.array([[100.0, 100.0], [300.0, 100.0], [900.0, 100.0]])   # centroïdes de carreaux 200 m
    pop = np.array([10.0, 5.0, 7.0])
    assert grid_sum(cells, cells, pop, 400).tolist() == [15, 15, 7]   # 600 m entre 2e et 3e : hors disque
    pts = np.array([[150.0, 50.0], [250.0, 150.0], [950.0, 120.0]])  # équipements rangés dans leur carreau
    assert grid_sum(cells, pts, None, 200).tolist() == [2, 2, 1]


def test_model_capture_and_station_capture():
    import pandas as pd
    from src.model.train import capture, station_capture
    y = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    score = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05])
    assert capture(y, score, tops=(0.1, 0.2, 1.0)) == {"top_10pct": 0.5, "top_20pct": 0.5, "top_100pct": 1.0}
    cells = pd.DataFrame({"x": [0.0, 200.0, 400.0, 600.0], "y": [0.0] * 4})
    st = np.array([[10.0, 0.0], [590.0, 5.0]])           # stations dans le 1er et le 4e carreau
    assert station_capture(cells, np.array([0.9, 0.5, 0.4, 0.1]), st, tops=(0.25, 1.0)) == {"top_25pct": 0.5, "top_100pct": 1.0}
