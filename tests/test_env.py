"""L'environnement fournit un solveur ILP (PuLP 4 n'embarque plus CBC) et les briques géo."""
import pulp


def test_pulp_highs_solves_small_ilp():
    # API PuLP 4 : les variables se créent via le problème (LpVariable.dicts n'existe plus)
    m = pulp.LpProblem("sac_a_dos", pulp.LpMaximize)
    x = m.add_variable_dicts("x", range(3), cat=pulp.LpBinary)
    m += 5 * x[0] + 4 * x[1] + 3 * x[2]
    m += 2 * x[0] + 3 * x[1] + x[2] <= 4
    stats = m.solve(pulp.HiGHS(msg=False))
    assert stats.status == pulp.LpSolveStatus.Optimal
    assert pulp.value(m.objective) == 8


def test_lambert93_projection():
    from pyproj import Transformer
    x, y = Transformer.from_crs(4326, 2154, always_xy=True).transform(7.7521, 48.5734)  # Strasbourg
    assert 1_040_000 < x < 1_060_000 and 6_830_000 < y < 6_850_000
