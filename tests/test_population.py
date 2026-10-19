import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from src.ingest.population import calage, motorisation, part_sans_voiture
from src.ingest.zone import select_communes


def test_select_communes_by_epci_and_list():
    c = pd.DataFrame({"code_insee": ["1", "2", "3", "4"],
                      "codes_siren_des_epci": ["200040715", "200040715/243800000", "243800000", None]})
    assert select_communes(c, "200040715", None).tolist() == [True, True, False, False]
    assert select_communes(c, None, ["3", 4]).tolist() == [False, False, True, True]
    with pytest.raises(ValueError):
        select_communes(c, None, None)


def test_calage_restores_census_totals():
    cells = pd.DataFrame({"code_insee": ["A", "A", "B"], "ind": [80.0, 20.0, 50.0]})
    communes = pd.DataFrame({"code_insee": ["A", "B", "C"], "nom": ["a", "b", "c"], "population": [125, 50, 10]})
    out, ratio = calage(cells, communes)
    assert out.groupby("code_insee").pop_calee.sum().to_dict() == {"A": 125, "B": 50}
    assert out.pop_calee.tolist() == [100, 25, 50]                       # répartition Filosofi conservée
    assert ratio.set_index("code_insee").loc["A", "ratio"] == pytest.approx(1.25)
    assert np.isnan(ratio.set_index("code_insee").loc["C", "ratio"])     # commune sans carreau : ratio indéfini


def test_part_sans_voiture():
    t = pd.DataFrame({"menages": [100, 0, 50], "menages_voiture": [70, 0, 60]})
    assert part_sans_voiture(t).tolist()[0] == pytest.approx(0.3)
    assert np.isnan(part_sans_voiture(t).tolist()[1])                     # 0 ménage : indéfini
    assert part_sans_voiture(t).tolist()[2] == 0                          # incohérence bornée à [0, 1]


def test_motorisation_iris_then_commune_fallback():
    # 4 carreaux : IRIS connu / IRIS sans ménage (repli) / commune non irisée / commune inconnue
    cells = gpd.GeoDataFrame({"code_insee": ["38185", "38185", "38258", "99999"]},
                             geometry=[box(i * 300, 0, i * 300 + 200, 200) for i in range(4)], crs=2154)
    contours = gpd.GeoDataFrame({"code_iris": ["381850101", "381850102", "382580000", "999990000"]},
                                geometry=[box(i * 300 - 50, -50, i * 300 + 250, 250) for i in range(4)], crs=2154)
    iris_tab = pd.DataFrame({"code_iris": ["381850101", "381850102"], "menages": [100, 0], "menages_voiture": [40, 0]})
    com_tab = pd.DataFrame({"code_insee": ["38185", "38258"], "menages": [1000, 100], "menages_voiture": [500, 90]})
    out, rep = motorisation(cells, contours, iris_tab, com_tab)
    assert out.part_sans_voiture.round(2).tolist()[:3] == [0.6, 0.5, 0.1]
    assert np.isnan(out.part_sans_voiture.iloc[3])
    assert out.motorisation_source.tolist() == ["iris", "repli_commune", "commune_non_irisee", "absente"]
    assert rep["taux_jointure_iris"] == 0.5 and rep["repli_commune"] == 1 and rep["sans_valeur"] == 1
