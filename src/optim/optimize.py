"""
Choix d'emplacements sous contrainte de budget : glouton et ILP de couverture maximale (PuLP + HiGHS).

Les deux méthodes partagent la même entrée (`Problem`) et la même sortie (`Result`).

Fonction objectif (identique pour les deux méthodes) :
    pour chaque type d'équipement t et chaque carreau i NON couvert par l'offre existante de type t,
    si au moins un candidat retenu j de type t couvre i :
        gain_i = population_i × (1 + equite × priorite_equite_i) × usage_rel_j
    où usage_rel_j = usage_predit_j / moyenne(usage_predit) et j est, parmi les candidats retenus
    qui couvrent i, celui d'usage maximal. Un carreau compte au plus une fois par type.

- Glouton : à chaque étape, le candidat de meilleur ratio gain marginal / coût qui tient dans le budget
  restant ; la couverture est mise à jour après chaque choix.
- ILP : x_j ∈ {0,1} (candidat retenu), z_ij ∈ {0,1} (carreau i crédité à j) ;
  max Σ z_ij·gain_ij  s.c.  z_ij ≤ x_j,  Σ_{j de type t} z_ij ≤ 1,  Σ cout_j·x_j ≤ budget.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pulp
import scipy.sparse as sp

OUTPUT_COLUMNS = ["rang", "id", "type", "nom", "x", "y", "cout", "pop_nouvellement_desservie",
                  "usage_predit", "cout_par_habitant", "budget_cumule", "gain_objectif"]


@dataclass
class Problem:
    coverage: sp.csr_matrix   # carreaux × candidats, True si le candidat couvre le carreau (≤ 5 min à pied)
    cells: pd.DataFrame       # population, priorite_equite ∈ [0,1], couvert_<type> (bool) pour chaque type candidat
    candidates: pd.DataFrame  # id, type, nom, cout, usage_predit, x, y

    def __post_init__(self):
        self.coverage = sp.csr_matrix(self.coverage, dtype=bool)
        n_cells, n_cand = self.coverage.shape
        if n_cells != len(self.cells) or n_cand != len(self.candidates):
            raise ValueError(f"matrice {self.coverage.shape} incohérente avec "
                             f"{len(self.cells)} carreaux / {len(self.candidates)} candidats")
        missing = {f"couvert_{t}" for t in self.candidates["type"].unique()} - set(self.cells.columns)
        if missing:
            raise ValueError(f"colonnes de couverture existante manquantes : {sorted(missing)}")
        self.cells = self.cells.reset_index(drop=True)
        self.candidates = self.candidates.reset_index(drop=True)


@dataclass
class Result:
    selection: pd.DataFrame                  # colonnes OUTPUT_COLUMNS, triées par rang
    summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------
def _weights(p: Problem, equity: float, scenario: str = "particuliers", alpha: float = 0.0) -> np.ndarray:
    pop = p.cells["population"].to_numpy(float)
    emplois = p.cells["emplois"].to_numpy(float) if "emplois" in p.cells.columns else np.zeros_like(pop)
    if scenario == "pros":
        base = emplois
    elif scenario == "mixte" or alpha > 0:
        base = pop + alpha * emplois
    else:  # particuliers (défaut officiel)
        base = pop
    prio = p.cells.get("priorite_equite", pd.Series(0.0, index=p.cells.index)).fillna(0).to_numpy(float)
    return base * (1.0 + equity * prio)


def _usage_rel(p: Problem) -> np.ndarray:
    u = p.candidates["usage_predit"].to_numpy(float)
    m = u.mean() if len(u) and u.mean() > 0 else 1.0
    return np.clip(u / m, 1e-6, None)


def _uncovered(p: Problem, t: str) -> np.ndarray:
    return ~p.cells[f"couvert_{t}"].fillna(False).to_numpy(bool)


def evaluate(p: Problem, chosen: list[int], equity: float = 0.0, scenario: str = "particuliers",
             alpha: float = 0.0) -> float:
    """Valeur de la fonction objectif pour un ensemble de candidats (indices)."""
    w, u, total = _weights(p, equity, scenario, alpha), _usage_rel(p), 0.0
    cov = p.coverage.tocsc()
    types = p.candidates["type"].to_numpy()
    for t in set(types[chosen]) if chosen else ():
        best = np.zeros(cov.shape[0])
        for j in (j for j in chosen if types[j] == t):
            rows = cov.indices[cov.indptr[j]:cov.indptr[j + 1]]
            best[rows] = np.maximum(best[rows], u[j])
        total += float((w * best * _uncovered(p, t)).sum())
    return total


def _order_and_format(p: Problem, chosen: list[int], equity: float, scenario: str = "particuliers",
                       alpha: float = 0.0) -> pd.DataFrame:
    """Range les candidats retenus par ratio gain marginal / coût et calcule les colonnes de sortie."""
    w, u = _weights(p, equity, scenario, alpha), _usage_rel(p)
    pop = p.cells["population"].to_numpy(float)
    emplois = p.cells["emplois"].to_numpy(float) if "emplois" in p.cells.columns else None
    cov = p.coverage.tocsc()
    cand = p.candidates
    types = cand["type"].to_numpy()
    cost = cand["cout"].to_numpy(float)
    covered = {t: ~_uncovered(p, t) for t in set(types)}
    remaining, rows, cum = list(chosen), [], 0.0
    while remaining:
        best_j, best_r, best_gain, best_new = None, -1.0, 0.0, None
        for j in remaining:
            idx = cov.indices[cov.indptr[j]:cov.indptr[j + 1]]
            new = idx[~covered[types[j]][idx]]
            gain = float(w[new].sum() * u[j])
            r = gain / cost[j] if cost[j] > 0 else np.inf
            if r > best_r:
                best_j, best_r, best_gain, best_new = j, r, gain, new
        remaining.remove(best_j)
        covered[types[best_j]][best_new] = True
        cum += cost[best_j]
        newpop = float(pop[best_new].sum())
        row = {
            "id": cand.at[best_j, "id"],
            "type": types[best_j],
            "nom": cand.get("nom", pd.Series("", index=cand.index))[best_j],
            "x": cand.get("x", pd.Series(np.nan, index=cand.index))[best_j],
            "y": cand.get("y", pd.Series(np.nan, index=cand.index))[best_j],
            "cout": cost[best_j],
            "pop_nouvellement_desservie": newpop,
            "usage_predit": float(cand.at[best_j, "usage_predit"]),
            "cout_par_habitant": cost[best_j] / newpop if newpop > 0 else np.inf,
            "budget_cumule": cum,
            "gain_objectif": best_gain
        }
        if emplois is not None:
            newemp = float(emplois[best_new].sum())
            row["emplois_nouvellement_desservis"] = newemp
            tot_pers = newpop + newemp
            row["cout_par_personne"] = cost[best_j] / tot_pers if tot_pers > 0 else np.inf
        rows.append(row)
    cols = list(OUTPUT_COLUMNS[1:])
    if emplois is not None:
        cols += ["emplois_nouvellement_desservis", "cout_par_personne"]
    df = pd.DataFrame(rows, columns=cols)
    df.insert(0, "rang", np.arange(1, len(df) + 1))
    return df


def _summary(p: Problem, method: str, budget: float, equity: float, sel: pd.DataFrame, chosen, t0, status,
             scenario: str = "particuliers", alpha: float = 0.0) -> dict:
    s = {"methode": method, "budget": budget, "equite": equity, "statut": status,
         "n_retenus": len(sel), "cout_total": float(sel["cout"].sum()),
         "pop_nouvellement_desservie": float(sel["pop_nouvellement_desservie"].sum()),
         "objectif": evaluate(p, list(chosen), equity, scenario=scenario, alpha=alpha),
         "duree_s": round(time.perf_counter() - t0, 3),
         "scenario": scenario}
    if "emplois_nouvellement_desservis" in sel:
        s["emplois_nouvellement_desservis"] = float(sel["emplois_nouvellement_desservis"].sum())
    return s


# ---------------------------------------------------------------------------------------------
def greedy(p: Problem, budget: float, equity: float = 0.0, scenario: str = "particuliers",
           alpha: float = 0.0) -> Result:
    t0 = time.perf_counter()
    w, u = _weights(p, equity, scenario, alpha), _usage_rel(p)
    cov = p.coverage.tocsc()
    types = p.candidates["type"].to_numpy()
    cost = p.candidates["cout"].to_numpy(float)
    covered = {t: ~_uncovered(p, t) for t in set(types)}
    chosen, left, avail = [], float(budget), set(range(len(cost)))
    while True:
        best_j, best_r, best_new = None, 0.0, None
        for j in avail:
            if cost[j] > left:
                continue
            idx = cov.indices[cov.indptr[j]:cov.indptr[j + 1]]
            new = idx[~covered[types[j]][idx]]
            gain = float(w[new].sum() * u[j])
            r = gain / cost[j] if cost[j] > 0 else (np.inf if gain > 0 else 0.0)
            if r > best_r:
                best_j, best_r, best_new = j, r, new
        if best_j is None:  # plus aucun candidat finançable avec un gain positif
            break
        chosen.append(best_j)
        avail.discard(best_j)
        covered[types[best_j]][best_new] = True
        left -= cost[best_j]
    sel = _order_and_format(p, chosen, equity, scenario, alpha)
    return Result(sel, _summary(p, "glouton", budget, equity, sel, chosen, t0, "ok", scenario, alpha))


def ilp(p: Problem, budget: float, equity: float = 0.0, time_limit: float = 60, gap: float = 1e-4,
        scenario: str = "particuliers", alpha: float = 0.0) -> Result:
    t0 = time.perf_counter()
    w, u = _weights(p, equity, scenario, alpha), _usage_rel(p)
    cov = p.coverage.tocoo()
    types = p.candidates["type"].to_numpy()
    cost = p.candidates["cout"].to_numpy(float)
    unc = {t: _uncovered(p, t) for t in set(types)}
    # seules les paires (carreau non couvert, candidat) avec un gain positif portent une variable z
    pairs = [(i, j) for i, j in zip(cov.row, cov.col) if unc[types[j]][i] and w[i] > 0 and cost[j] <= budget]
    useful = sorted({j for _, j in pairs})

    m = pulp.LpProblem("couverture_maximale", pulp.LpMaximize)
    x = m.add_variable_dicts("x", useful, cat=pulp.LpBinary)
    z = m.add_variable_dicts("z", range(len(pairs)), lowBound=0, upBound=1)  # continu : entier à l'optimum
    # Pénalité infime sur le coût : sans elle, un candidat sans gain marginal peut être retenu
    # (objectif inchangé). Elle reste < 0,1 % du plus petit gain : la couverture optimale n'est pas modifiée.
    gains = [w[i] * u[j] for i, j in pairs]
    eps = 1e-3 * min(gains) / max(1.0, sum(cost[j] for j in useful)) if gains else 0.0
    m += pulp.lpSum(z[k] * g for k, g in enumerate(gains)) - pulp.lpSum(eps * cost[j] * x[j] for j in useful)
    m += pulp.lpSum(cost[j] * x[j] for j in useful) <= budget
    by_cell_type: dict[tuple, list] = {}
    for k, (i, j) in enumerate(pairs):
        m += z[k] <= x[j]
        by_cell_type.setdefault((i, types[j]), []).append(k)
    for ks in by_cell_type.values():
        if len(ks) > 1:
            m += pulp.lpSum(z[k] for k in ks) <= 1
    stats = m.solve(pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=gap)) if useful else None
    chosen = [j for j in useful if (x[j].value() or 0) > 0.5] if stats else []
    status = stats.status.name if stats else "rien_a_optimiser"
    sel = _order_and_format(p, chosen, equity, scenario, alpha)
    return Result(sel, _summary(p, "ILP", budget, equity, sel, chosen, t0, status, scenario, alpha))


def optimize(p: Problem, budget: float, equity: float = 0.0, method: str = "glouton",
             types: list[str] | None = None, scenario: str = "particuliers", alpha: float = 0.0,
             **kw) -> Result:
    """Point d'entrée unique (application, scripts). `types` restreint les types d'équipement candidats."""
    if types is not None:
        keep = p.candidates["type"].isin(types).to_numpy()
        p = Problem(p.coverage[:, np.flatnonzero(keep)], p.cells, p.candidates[keep])
    if method in ("glouton", "greedy"):
        return greedy(p, budget, equity, scenario=scenario, alpha=alpha)
    if method in ("ilp", "ILP"):
        return ilp(p, budget, equity, scenario=scenario, alpha=alpha, **kw)
    raise ValueError(f"méthode inconnue : {method}")
