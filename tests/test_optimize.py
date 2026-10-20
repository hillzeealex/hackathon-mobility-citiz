"""Optimiseur sur une petite instance synthétique : 10 carreaux, 5 candidats Citiz."""
import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from src.optim.optimize import OUTPUT_COLUMNS, Problem, evaluate, greedy, ilp, optimize

#            carreaux : 0    1    2    3   4   5   6    7    8    9
POP = np.array([100, 100, 100, 90, 90, 90, 150, 150, 150, 100])
COVERS = {"A": [0, 1, 2, 3, 4], "B": [0, 1, 2], "C": [3, 4, 5], "D": [6, 7, 8], "E": [9]}
COST = {"A": 50, "B": 20, "C": 20, "D": 40, "E": 5}


def build(usage=None, prio=None, types=None):
    ids = list(COVERS)
    rows = [i for j in ids for i in COVERS[j]]
    cols = [k for k, j in enumerate(ids) for _ in COVERS[j]]
    cov = sp.csr_matrix((np.ones(len(rows), bool), (rows, cols)), shape=(10, len(ids)))
    cells = pd.DataFrame({"population": POP, "priorite_equite": prio if prio is not None else 0.0,
                          "couvert_citiz_station": [False] * 9 + [True]})   # carreau 9 déjà desservi
    cand = pd.DataFrame({"id": ids, "type": types or ["citiz_station"] * 5, "nom": ids,
                         "cout": [COST[j] for j in ids], "usage_predit": usage or [1.0] * 5,
                         "x": np.arange(5) * 100.0, "y": 0.0})
    if types:
        for t in set(types):
            cells[f"couvert_{t}"] = cells.get(f"couvert_{t}", False)
    return Problem(cov, cells, cand)


@pytest.mark.parametrize("solver", [greedy, ilp])
def test_same_output_interface_and_budget(solver):
    res = solver(build(), budget=60)
    sel = res.selection
    assert list(sel.columns) == OUTPUT_COLUMNS
    assert sel["rang"].tolist() == list(range(1, len(sel) + 1))
    assert sel["cout"].sum() <= 60
    assert np.all(np.diff(sel["budget_cumule"]) > 0) and sel["budget_cumule"].iloc[-1] == sel["cout"].sum()
    assert "E" not in set(sel["id"])                       # ne couvre qu'un carreau déjà desservi
    assert {"methode", "objectif", "cout_total", "pop_nouvellement_desservie", "statut"} <= res.summary.keys()


def test_greedy_suboptimal_ilp_optimal():
    p = build()
    g, i = greedy(p, 60), ilp(p, 60)
    assert set(g.selection["id"]) == {"B", "C"} and g.summary["objectif"] == pytest.approx(570)
    assert set(i.selection["id"]) in ({"B", "D"},) and i.summary["objectif"] == pytest.approx(750)
    assert i.summary["statut"] == "Optimal"


def test_new_population_not_double_counted():
    sel = ilp(build(), 1000).selection          # budget illimité : tout ce qui est utile
    assert sel["pop_nouvellement_desservie"].sum() == POP[:9].sum()
    assert (sel["pop_nouvellement_desservie"] > 0).all()


def test_equity_shifts_choice():
    prio = np.array([0, 0, 0, 1, 1, 1, 0, 0, 0, 0], float)
    assert greedy(build(prio=prio), 20, equity=0).selection["id"].tolist() == ["B"]   # 300 > 270
    assert greedy(build(prio=prio), 20, equity=1).selection["id"].tolist() == ["C"]   # 270 × 2 > 300


def test_usage_weights_value():
    p = build(usage=[1, 1, 3, 1, 1])                       # C a un usage prédit 3× plus élevé
    assert greedy(p, 20).selection["id"].tolist() == ["C"]
    assert evaluate(p, [2]) == pytest.approx(270 * 3 / np.mean([1, 1, 3, 1, 1]))


def test_types_counted_separately_and_filter():
    p = build(types=["citiz_station", "bus_stop", "citiz_station", "citiz_station", "citiz_station"])
    # B (arrêt de bus) couvre les mêmes carreaux que A (Citiz) : la population compte pour chaque type
    both = evaluate(p, [0, 1])
    assert both == pytest.approx(480 + 300)
    only_bus = optimize(p, 1000, types=["bus_stop"], method="ilp").selection
    assert only_bus["id"].tolist() == ["B"]


def test_scenario_pro_and_mixte():
    # Carreau 0-2: forte pop (300 hab), 0 emplois (B couvre 0-2)
    # Carreau 3-5: faible pop (30 hab), très forts emplois (1000 emplois) (C couvre 3-5)
    p = build()
    p.cells["emplois"] = [0, 0, 0, 400, 300, 300, 0, 0, 0, 0]
    # Particuliers : B choisi (300 hab > 270 hab)
    sel_part = greedy(p, 20, scenario="particuliers").selection
    assert sel_part["id"].tolist() == ["B"]
    
    # Pros : C choisi car 1000 emplois > 0 emplois
    sel_pros = greedy(p, 20, scenario="pros").selection
    assert sel_pros["id"].tolist() == ["C"]
    assert "emplois_nouvellement_desservis" in sel_pros.columns
    assert sel_pros["emplois_nouvellement_desservis"].iloc[0] == 1000

    # Mixte avec alpha = 0.3 : score B = 300, score C = 270 + 0.3 * 1000 = 570 -> C gagne
    sel_mixte = greedy(p, 20, scenario="mixte", alpha=0.3).selection
    assert sel_mixte["id"].tolist() == ["C"]


def test_invalid_problem():
    p = build()
    with pytest.raises(ValueError):
        Problem(p.coverage[:, :4], p.cells, p.candidates)
    with pytest.raises(ValueError):
        Problem(p.coverage, p.cells.drop(columns="couvert_citiz_station"), p.candidates)
    with pytest.raises(ValueError):
        optimize(p, 10, method="recuit")
