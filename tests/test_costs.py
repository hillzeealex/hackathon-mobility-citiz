import pytest

from src.optim.costs import co2_avoided_t_per_year, equipment_cost, load_costs


def test_every_value_has_three_ordered_scenarios():
    c = load_costs()
    for eq in c["equipements"].values():
        for block in ("investissement", "exploitation_annuelle"):
            for v in eq[block].values():
                assert v["basse"] <= v["moyenne"] <= v["haute"]


@pytest.mark.parametrize("kind", ["citiz_station", "bus_stop", "bike_station", "free_floating_zone"])
def test_total_is_capex_plus_horizon_opex(kind):
    c = equipment_cost(kind, "moyenne", horizon_ans=3)
    assert c["total"] == pytest.approx(c["investissement"] + 3 * c["exploitation_annuelle"])
    assert equipment_cost(kind, "basse")["total"] <= equipment_cost(kind, "haute")["total"]


def test_bike_station_opex_scales_with_bikes():
    c = equipment_cost("bike_station", "moyenne")
    assert c["exploitation_annuelle"] == 15 * 2500


def test_co2_prudent_default():
    # 1 véhicule, scénario bas : 10 000 km × 0,142 kg = 1,42 t/an
    assert co2_avoided_t_per_year(1) == pytest.approx(1.42)


def test_unknown_scenario():
    with pytest.raises(ValueError):
        equipment_cost("bus_stop", "extreme")


def test_risk_surcharge_only_above_reference_and_capped():
    from src.optim.costs import risk_surcharge
    out = risk_surcharge([0.5, 1.0, 1.5, 10.0, float("nan")], scenario="moyenne", horizon_ans=3)
    # 3 ans × 1 700 € × 0,5 × excès (plafonné à 2)
    assert out.tolist() == [0, 0, 1275.0, 5100.0, 0]
