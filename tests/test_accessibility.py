"""Couverture V1/V2 et indicateurs sur de petits cas construits à la main."""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from src.features.accessibility import coverage_buffer, coverage_network, indicators, offer_weights
from src.features.network import split_at_nodes, to_graph, walkable

SETTINGS = {"mode_weights": {"bus": 1.0, "tram": 2.0, "velo": 1.0, "trottinette": 0.5},
            "free_floating_weight": 0.5,
            "frequency": {"enabled": True, "reference_passages_jour": 100, "min_factor": 0.25, "max_factor": 2.0}}


def test_buffer_radius():
    cells = np.array([[0, 0], [1000, 0]])
    offer = np.array([[399, 0], [401, 0], [1000, 300]])
    cov = coverage_buffer(cells, offer, 400).toarray()
    assert cov.tolist() == [[True, False, False], [False, False, True]]


def test_network_detour_breaks_buffer_coverage():
    # Rivière : carreau en (0,0), arrêt en (0,300) à 300 m à vol d'oiseau, mais le seul pont est à 400 m à l'est
    nodes = {1: (0, 0), 2: (400, 0), 3: (400, 300), 4: (0, 300), 5: (0, 100)}
    links = [(1, 2), (2, 3), (3, 4), (1, 5)]
    edges = gpd.GeoDataFrame({"u": [a for a, _ in links], "v": [b for _, b in links]},
                             geometry=[LineString([nodes[a], nodes[b]]) for a, b in links], crs=2154)
    edges["length"] = edges.length
    g = to_graph(edges)
    cells = np.array([[0.0, 0.0], [0.0, 100.0], [200.0, 30.0]])
    offer = np.array([[0.0, 300.0], [0.0, 50.0]])
    v1 = coverage_buffer(cells, offer, 400).toarray()
    v2, info = coverage_network(g, edges, cells, offer, 400)
    v2 = v2.toarray()
    assert v1[0, 0] and not v2[0, 0]          # 300 m à vol d'oiseau, 1 100 m à pied
    assert v2[0, 1] and v2[1, 1]              # même côté : 50 m
    # carreau à 30 m de la rue sud, abscisse 200 : 30 + 200 jusqu'au nœud 1 + 50 = 280 m -> couvert
    assert v2[2, 1] and not v2[2, 0]          # vers le nord : 30 + 200 + 300 + 400 = 930 m
    assert info["offre_rabattement_median_m"] == 0 and g.number_of_nodes() == 5   # nœud virtuel retiré


def test_offer_weights_mode_frequency_and_free_floating():
    offer = pd.DataFrame({"type": ["bus", "tram", "velo", "trottinette", "bus"],
                          "sous_type": ["arret", "arret", "zone_free_floating", "zone_free_floating", "arret"],
                          "passages_jour": [100, 400, np.nan, np.nan, 5]})
    w = offer_weights(offer, SETTINGS)
    assert w.tolist() == [1.0, 4.0, 0.5, 0.5, 0.25]   # tram plafonné à ×2, bus rare plancher ×0,25
    assert offer_weights(offer, SETTINGS, free_floating_weight=1.0)[2:4].tolist() == [1.0, 1.0]


def test_indicators_2sfca():
    # 2 carreaux (100 et 300 hab.) partagent un arrêt de poids 1 ; le 2e a en plus un arrêt pour lui seul
    cov = np.array([[1, 0], [1, 1]], bool)
    out = indicators(cov, np.array([1.0, 1.0]), np.array([100.0, 300.0]))
    assert out.n_options.tolist() == [1, 2]
    assert out.acces_1000.round(3).tolist() == [2.5, round(1000 / 400 + 1000 / 300, 3)]
    # conservation : Σ population × accès = 1000 × Σ poids des points utilisés
    assert (out.acces_1000 * [100, 300]).sum() == pytest.approx(2000)


def test_walkable_filter():
    lines = pd.DataFrame({"highway": ["footway", "motorway", "residential", "service", "cycleway", None, "steps"],
                          "other_tags": [None, None, '"foot"=>"no"', '"access"=>"private"', None, None, '"area"=>"yes"']})
    assert walkable(lines).tolist() == [True, False, False, False, False, False, False]
    explicit = pd.DataFrame({"highway": ["cycleway", "service", "footway"],
                             "other_tags": ['"foot"=>"designated"', '"access"=>"no","foot"=>"yes"', '"foot"=>"no"']})
    assert walkable(explicit).tolist() == [True, True, False]


def test_split_at_shared_vertices():
    # deux voies qui se croisent en (100, 0) : 4 arêtes, longueurs conservées
    a = LineString([(0, 0), (100, 0), (200, 0)])
    b = LineString([(100, -100), (100, 0), (100, 50), (100, 100)])   # tronçon nord à 3 sommets
    e = split_at_nodes(gpd.GeoSeries([a, b], crs=2154))
    assert len(e) == 4 and e.length.sum() == pytest.approx(400)
    assert sorted(len(g.coords) for g in e.geometry) == [2, 2, 2, 3]
    assert to_graph(e).number_of_nodes() == 5
