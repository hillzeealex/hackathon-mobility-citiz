"""Outils géographiques partagés : dédoublonnage spatial, filtrage des coordonnées aberrantes."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

# Emprise large de la France métropolitaine en WGS84 (lon_min, lat_min, lon_max, lat_max)
FRANCE_BBOX = (-5.8, 41.2, 10.0, 51.3)


def valid_coords(lon: pd.Series, lat: pd.Series, bbox=FRANCE_BBOX) -> pd.Series:
    """Masque des coordonnées plausibles : non nulles, non (0,0), dans l'emprise."""
    lon, lat = pd.to_numeric(lon, errors="coerce"), pd.to_numeric(lat, errors="coerce")
    return (lon.between(bbox[0], bbox[2]) & lat.between(bbox[1], bbox[3])
            & ~((lon == 0) & (lat == 0)))


def cluster_labels(xy: np.ndarray, radius: float) -> np.ndarray:
    """Composantes connexes du graphe « distance < radius » (agrégation à lien simple)."""
    n = len(xy)
    if n == 0:
        return np.empty(0, dtype=int)
    pairs = cKDTree(xy).query_pairs(radius, output_type="ndarray")
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    return connected_components(graph, directed=False)[1]


def dedup_points(gdf: gpd.GeoDataFrame, radius: float | dict, by: str = "type",
                 sum_cols: tuple[str, ...] = ("capacite", "passages_jour"),
                 ) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Fusionne les points d'un même groupe (`by`, ex. le mode) distants de moins de `radius` mètres.

    `radius` : un rayon commun, ou {groupe: rayon} avec la clé "default" pour les autres groupes.
    `gdf` doit être dans un CRS métrique. Le point fusionné est le barycentre du groupe ;
    les colonnes `sum_cols` sont sommées, les autres prennent la première valeur ;
    `ids_fusionnes` liste les identifiants d'origine. Renvoie (points fusionnés, stats avant/après).
    """
    if gdf.crs is None or not gdf.crs.is_projected:
        raise ValueError("dedup_points attend un CRS métrique (ex. EPSG:2154)")
    parts, stats = [], []
    for key, g in gdf.groupby(by, sort=True):
        g = g.copy()
        xy = np.column_stack([g.geometry.x.to_numpy(), g.geometry.y.to_numpy()])
        r = radius.get(key, radius.get("default")) if isinstance(radius, dict) else radius
        g["_cl"] = cluster_labels(xy, r)
        g["_x"], g["_y"] = xy[:, 0], xy[:, 1]
        agg = {c: "first" for c in g.columns if c not in ("geometry", "_cl", "_x", "_y")}
        for c in sum_cols:
            if c in g.columns:
                agg[c] = lambda s: s.sum(min_count=1)  # NaN reste NaN (pas de fréquence pour le GBFS)
        agg.update({"_x": "mean", "_y": "mean"})
        merged = g.groupby("_cl", sort=False).agg(agg)
        merged["ids_fusionnes"] = g.groupby("_cl", sort=False)["id"].agg(lambda s: "|".join(map(str, s)))
        merged["n_fusionnes"] = g.groupby("_cl", sort=False).size()
        parts.append(gpd.GeoDataFrame(merged.drop(columns=["_x", "_y"]),
                                      geometry=gpd.points_from_xy(merged["_x"], merged["_y"]), crs=gdf.crs))
        stats.append({by: key, "avant": len(g), "apres": len(merged)})
    out = pd.concat(parts, ignore_index=True) if parts else gdf.iloc[:0].copy()
    st = pd.DataFrame(stats)
    if not st.empty:
        st["fusionnes"] = st["avant"] - st["apres"]
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs), st
