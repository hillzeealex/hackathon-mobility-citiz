"""Lecture de config/costs.yaml : coût total d'un équipement et paramètres d'impact (CO2)."""
from __future__ import annotations

from functools import lru_cache

import yaml

from src.common.config import ROOT, load_settings

SCENARIOS = ("basse", "moyenne", "haute")


@lru_cache(maxsize=None)
def load_costs() -> dict:
    with open(ROOT / load_settings()["costs"]["file"], encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sum(block: dict, scenario: str, factor: dict | None = None) -> float:
    return float(sum(v[scenario] * (factor or {}).get(k, 1) for k, v in block.items()))


def equipment_cost(kind: str, scenario: str | None = None, horizon_ans: float | None = None) -> dict:
    """{investissement, exploitation_annuelle, total} en € pour un équipement de `kind`."""
    c = load_costs()
    scenario = scenario or c["scenario"]
    if scenario not in SCENARIOS:
        raise ValueError(f"scénario inconnu : {scenario}")
    horizon = c["horizon_ans"] if horizon_ans is None else horizon_ans
    eq = c["equipements"][kind]
    capex = _sum(eq["investissement"], scenario)
    factor = {"par_velo": eq.get("nb_velos", 1)}
    opex = _sum(eq["exploitation_annuelle"], scenario, factor)
    return {"type": kind, "libelle": eq["libelle"], "scenario": scenario, "investissement": capex,
            "exploitation_annuelle": opex, "horizon_ans": horizon, "total": capex + horizon * opex}


def co2_avoided_t_per_year(n_citiz_vehicles: float, scenario: str | None = None,
                           motorisation: str = "voiture_thermique") -> float:
    """CO2 évité (tonnes/an) par l'ajout de véhicules en autopartage : km évités × facteur d'émission.

    Hypothèse prudente : seuls les km de voiture personnelle évités comptent (ADEME 2022) ;
    aucun gain n'est compté pour les arrêts de bus ou stations vélo faute de donnée locale de report modal.
    """
    imp = load_costs()["impact"]
    scenario = scenario or imp["scenario"]
    km = imp["autopartage"]["km_voiture_evites_par_vehicule_an"][scenario]
    fe = imp["facteur_emission_kgco2e_par_km"][motorisation][scenario]
    return n_citiz_vehicles * km * fe / 1000
