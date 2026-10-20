"""
Accessibilité à 5 min à pied : matrices de couverture (carreaux × points d'offre) et indicateurs.

- V1 « buffer » : point d'offre à moins de R m (vol d'oiseau) du centroïde du carreau.
- V2 « réseau »  : distance de marche sur le réseau piéton OSM ≤ R, rabattements compris (projection du
  centroïde et du point d'offre sur l'arête la plus proche ; Dijkstra borné depuis chaque point d'offre).

Poids d'un point d'offre j :  w_j = poids_mode × facteur_fréquence
  - poids_mode : settings.mode_weights ; zones free-floating : settings.free_floating_weight par mode
  - facteur_fréquence (TC) : clip(passages_jour / reference, min, max) ; 1 pour le reste
Indicateurs par carreau i (couverture C, population calée P) :
  - n_options_i = Σ_j C_ij · w_j                       (A : options accessibles à un habitant du carreau)
  - acces_1000_i = 1000 · Σ_j C_ij · w_j / Σ_k C_kj · P_k   (B : 2SFCA, options pour 1 000 habitants)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.spatial import cKDTree


# ---------------------------------------------------------------------------------------------
def coverage_buffer(cells_xy: np.ndarray, offer_xy: np.ndarray, radius: float) -> sp.csr_matrix:
    """C[i, j] = 1 si le point d'offre j est à moins de `radius` m du centroïde i (vol d'oiseau)."""
    pairs = cKDTree(cells_xy).query_ball_point(offer_xy, radius)
    rows = np.concatenate([np.asarray(p, dtype=np.int64) for p in pairs]) if len(pairs) else np.empty(0, np.int64)
    cols = np.repeat(np.arange(len(pairs)), [len(p) for p in pairs])
    return sp.csr_matrix((np.ones(len(rows), bool), (rows, cols)), shape=(len(cells_xy), len(offer_xy)))


def snap_to_edges(points_xy: np.ndarray, edges) -> pd.DataFrame:
    """Projection de chaque point sur l'arête la plus proche : arête, distance, abscisse depuis u."""
    import shapely

    geoms = edges.geometry.to_numpy()
    pts = shapely.points(points_xy)
    _, e = shapely.STRtree(geoms).query_nearest(pts, all_matches=False)
    g = geoms[e]
    return pd.DataFrame({"edge": e, "d": shapely.distance(g, pts), "a": shapely.line_locate_point(g, pts),
                         "L": edges["length"].to_numpy()[e], "u": edges["u"].to_numpy()[e],
                         "v": edges["v"].to_numpy()[e]})


def nearest_walk_distance(graph, edges, from_xy: np.ndarray, to_xy: np.ndarray, cutoff: float = 3000) -> np.ndarray:
    """Distance de marche (m) de chaque point `from_xy` au point `to_xy` le plus proche sur le réseau piéton
    (Dijkstra multi-sources, rabattements compris) ; inf au-delà de `cutoff`."""
    import networkx as nx

    st, sf = snap_to_edges(to_xy, edges), snap_to_edges(from_xy, edges)
    src = "__sources__"
    for o in st.itertuples(index=False):
        for node, w in ((o.u, o.d + o.a), (o.v, o.d + o.L - o.a)):
            if not graph.has_edge(src, node) or graph[src][node]["length"] > w:
                graph.add_edge(src, node, length=w)
    try:
        D = nx.single_source_dijkstra_path_length(graph, src, cutoff=cutoff, weight="length")
    finally:
        graph.remove_node(src)
    du = sf.u.map(D).astype(float).fillna(np.inf).to_numpy() + sf.d.to_numpy() + sf.a.to_numpy()
    dv = sf.v.map(D).astype(float).fillna(np.inf).to_numpy() + sf.d.to_numpy() + (sf.L - sf.a).to_numpy()
    return np.minimum(du, dv)


def coverage_network(graph, edges, cells_xy: np.ndarray, offer_xy: np.ndarray, radius: float) -> tuple[sp.csr_matrix, dict]:
    """Couverture par distance de marche ≤ radius sur le réseau piéton.

    Distance = rabattement du point d'offre sur son arête + chemin réseau + rabattement du centroïde
    du carreau sur son arête (projection orthogonale, puis le long de l'arête jusqu'au nœud).
    `graph` : networkx.Graph pondéré par 'length' ; `edges` : GeoDataFrame (u, v, length, geometry) métrique.
    """
    import networkx as nx

    sc, so = snap_to_edges(cells_xy, edges), snap_to_edges(offer_xy, edges)
    at_node: dict = {}
    on_edge: dict = {}
    for i, r in enumerate(sc.itertuples(index=False)):
        at_node.setdefault(r.u, []).append((i, r.d + r.a))
        at_node.setdefault(r.v, []).append((i, r.d + r.L - r.a))
        on_edge.setdefault(r.edge, []).append((i, r.d, r.a))
    rows, cols = [], []
    src = "__source__"
    for j, o in enumerate(so.itertuples(index=False)):
        budget = radius - o.d
        if budget <= 0:
            continue
        best: dict[int, float] = {}
        for i, d_i, a_i in on_edge.get(o.edge, ()):              # même arête : trajet direct le long de l'arête
            best[i] = d_i + abs(a_i - o.a)
        graph.add_edge(src, o.u, length=o.a)
        graph.add_edge(src, o.v, length=min(o.L - o.a, graph[src][o.v]["length"]) if graph.has_edge(src, o.v) else o.L - o.a)
        try:
            lengths = nx.single_source_dijkstra_path_length(graph, src, cutoff=budget, weight="length")
        finally:
            graph.remove_node(src)
        for node, D in lengths.items():
            for i, c in at_node.get(node, ()):
                if D + c < best.get(i, np.inf):
                    best[i] = D + c
        for i, dist in best.items():
            if dist <= budget:
                rows.append(i)
                cols.append(j)
    cov = sp.csr_matrix((np.ones(len(rows), bool), (rows, cols)), shape=(len(cells_xy), len(offer_xy)))
    info = {"rabattement_carreau_median_m": round(float(sc.d.median()), 1),
            "carreaux_rabattement_gt_200m": int((sc.d > 200).sum()),
            "offre_rabattement_median_m": round(float(so.d.median()), 1),
            "offre_rabattement_gt_100m": int((so.d > 100).sum())}
    return cov, info


# ---------------------------------------------------------------------------------------------
def offer_weights(offer: pd.DataFrame, settings: dict, free_floating_weight: float | None = None) -> np.ndarray:
    """Poids w_j de chaque point d'offre (mode × fréquence ; free-floating au poids dédié par mode)."""
    mw = settings["mode_weights"]
    ffw = settings["free_floating_weight"] if free_floating_weight is None else free_floating_weight
    w = offer["type"].map(mw).fillna(1.0).to_numpy(float)
    ff = (offer["sous_type"] == "zone_free_floating").to_numpy()
    w = np.where(ff, ffw, w)
    fq = settings.get("frequency", {})
    if fq.get("enabled"):
        p = offer["passages_jour"].to_numpy(float)
        factor = np.clip(p / fq["reference_passages_jour"], fq["min_factor"], fq["max_factor"])
        w = np.where(np.isnan(p), w, w * factor)
    return w


def indicators(cov: sp.csr_matrix, weights: np.ndarray, population: np.ndarray) -> pd.DataFrame:
    """n_options (A) et acces_1000 (B, 2SFCA) pour chaque carreau."""
    cov = sp.csr_matrix(cov, dtype=float)
    n_options = cov @ weights
    demand = cov.T @ population                       # habitants à 5 min de chaque point d'offre
    ratio = np.divide(weights, demand, out=np.zeros_like(weights), where=demand > 0)
    return pd.DataFrame({"n_options": n_options, "n_points": np.asarray(cov.sum(axis=1)).ravel(),
                         "acces_1000": 1000 * (cov @ ratio)})


def options_by_type(cov: sp.csr_matrix, types: pd.Series) -> pd.DataFrame:
    """Nombre de points accessibles par type (colonnes n_<type>)."""
    out = {}
    for t in sorted(types.unique()):
        mask = (types == t).to_numpy().astype(float)
        out[f"n_{t}"] = sp.csr_matrix(cov, dtype=float) @ mask
    return pd.DataFrame(out)


def weighted_share(flag: np.ndarray, population: np.ndarray) -> float:
    return float((population * flag).sum() / population.sum()) if population.sum() else 0.0
