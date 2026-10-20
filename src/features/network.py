"""
Réseau piéton depuis l'extrait OSM Geofabrik local (.osm.pbf, pilote OSM de GDAL via pyogrio)
-> data/processed/cache/walk_edges.parquet (arêtes Lambert-93 : u, v, length, geometry)

Hors ligne et reproductible (date de l'extrait dans walk_edges_meta.json), contrairement à Overpass.
Filtre piéton repris d'osmnx (network_type="walk") : on exclut les voies
  highway ∈ {abandoned, bus_guideway, construction, cycleway, motorway(_link), no, planned, platform,
             proposed, raceway, razed}, ainsi que foot=no, access=no/private, service=private, area=yes ;
une autorisation piétonne explicite (foot=yes/designated/permissive) l'emporte sur access et sur cycleway.
Graphe : nœuds = intersections et extrémités de voies ; on garde la plus grande composante connexe.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pyogrio
import shapely

from src.common.config import city_from_args, city_processed, load_settings, raw, study_area
from src.ingest.zone import buffer_area, load_zone

EDGES = "cache/walk_edges.parquet"
MARGIN_M = 0     # réseau découpé exactement sur la zone + offer.buffer_m (800 m) : couvre tout trajet de 400 m
EXCLUDED_HIGHWAY = {"abandoned", "bus_guideway", "construction", "cycleway", "motorway", "motorway_link", "no",
                    "planned", "platform", "proposed", "raceway", "razed"}
EXCLUDED_TAGS = re.compile(r'"foot"=>"no"|"(?:access|service)"=>"(?:no|private)"|"area"=>"yes"')
FOOT_ALLOWED = re.compile(r'"foot"=>"(?:yes|designated|permissive)"')   # prime sur access=no/private et cycleway


def walkable(lines: pd.DataFrame) -> pd.Series:
    tags = lines["other_tags"].fillna("")
    foot_ok = tags.str.contains(FOOT_ALLOWED)
    hw_ok = ~lines["highway"].isin(EXCLUDED_HIGHWAY) | (foot_ok & (lines["highway"] == "cycleway"))
    tags_ok = ~tags.str.contains(EXCLUDED_TAGS) | (foot_ok & ~tags.str.contains('"area"=>"yes"', regex=False))
    return lines["highway"].notna() & hw_ok & tags_ok


def split_at_nodes(geoms: gpd.GeoSeries, precision: float = 0.01) -> gpd.GeoDataFrame:
    """Découpe les voies aux sommets partagés (intersections) : une arête par tronçon entre deux nœuds."""
    coords, line_idx = shapely.get_coordinates(geoms.to_numpy(), return_index=True)
    keys = np.round(coords / precision).astype(np.int64)
    _, vid = np.unique(keys, axis=0, return_inverse=True)
    vid = vid.ravel()
    # nombre de voies distinctes passant par chaque sommet
    pairs = np.unique(np.column_stack([vid, line_idx]), axis=0)
    n_lines = np.bincount(pairs[:, 0], minlength=vid.max() + 1)
    starts = np.r_[0, np.flatnonzero(np.diff(line_idx)) + 1]
    ends = np.r_[starts[1:] - 1, len(line_idx) - 1]
    is_node = n_lines[vid] >= 2
    is_node[starts] = True
    is_node[ends] = True
    rows = []
    for s, e in zip(starts, ends):
        k = s
        for m in np.flatnonzero(is_node[s + 1:e + 1]) + s + 1:
            seg = coords[k:m + 1]
            if len(seg) >= 2 and vid[k] != vid[m]:
                rows.append((vid[k], vid[m], seg))
            k = m
    sizes = [len(r[2]) for r in rows]
    geom = shapely.linestrings(np.concatenate([r[2] for r in rows]), indices=np.repeat(np.arange(len(rows)), sizes))
    return gpd.GeoDataFrame({"u": [r[0] for r in rows], "v": [r[1] for r in rows]}, geometry=geom, crs=geoms.crs) \
        .assign(length=lambda d: d.length)


def largest_component(edges: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = nx.Graph()
    g.add_edges_from(zip(edges["u"], edges["v"]))
    keep = max(nx.connected_components(g), key=len)
    return edges[edges["u"].isin(keep)].reset_index(drop=True)


def load_walk_edges(force: bool = False, rebuild: bool = False) -> gpd.GeoDataFrame:
    """force : relit le PBF ; rebuild : recalcule les arêtes depuis le cache des voies (après un changement de filtre)."""
    path = city_processed(EDGES)
    if path.exists() and not (force or rebuild):
        return gpd.read_parquet(path)
    s = load_settings()
    pbf = raw("osm", f"{study_area()['osm_region']}-latest.osm.pbf")
    area = buffer_area(load_zone()).buffer(MARGIN_M)
    bbox = tuple(gpd.GeoSeries([area], crs=s["crs"]["metric"]).to_crs(4326).total_bounds)
    t0 = time.time()
    lines_cache = city_processed("cache", "walk_lines.parquet")   # lecture du PBF (lente) mise en cache
    if lines_cache.exists() and not force:
        lines = gpd.read_parquet(lines_cache)
    else:
        lines = pyogrio.read_dataframe(pbf, layer="lines", bbox=bbox, columns=["osm_id", "highway", "other_tags"])
        lines.to_parquet(lines_cache)
    n_lines = len(lines)
    lines = lines[walkable(lines)].to_crs(s["crs"]["metric"])
    lines = lines[lines.intersects(area)]
    edges = split_at_nodes(lines.geometry.reset_index(drop=True))
    n_before = len(edges)
    edges = largest_component(edges)
    edges.to_parquet(path)
    meta = {"source": pbf.name, "date_extrait": dt.datetime.fromtimestamp(pbf.stat().st_mtime).date().isoformat(),
            "voies_lues": n_lines, "voies_pietonnes": len(lines), "aretes": len(edges),
            "aretes_hors_composante_principale": n_before - len(edges),
            "longueur_km": round(edges["length"].sum() / 1000), "duree_s": round(time.time() - t0)}
    city_processed("cache", "walk_edges_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(meta)
    return edges


def to_graph(edges: pd.DataFrame) -> nx.Graph:
    """Graphe non orienté simple (longueur minimale entre deux nœuds)."""
    e = edges.groupby(["u", "v"], as_index=False)["length"].min()
    g = nx.Graph()
    g.add_weighted_edges_from(zip(e["u"], e["v"], e["length"]), weight="length")
    return g


if __name__ == "__main__":
    import sys
    city_from_args()
    load_walk_edges(force="--force" in sys.argv, rebuild="--rebuild" in sys.argv)
