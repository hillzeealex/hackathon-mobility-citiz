"""
Niveau 1 : offre de mobilité de toute la France -> data/processed/national/offer.parquet (sans géométrie)

- GTFS : chaque flux est traité une fois (cache data/processed/national/gtfs_stops/<flux>.parquet, reprise possible),
  2 processus en parallèle (mémoire bornée). Mêmes règles qu'à Grenoble (mardi type, frequencies.txt,
  route_type, autocars OCECar) ; flux expiré : mardi type pris dans sa propre période de validité (signalé).
- GBFS : toutes les stations Citiz et autres (zones free-floating : une ligne par mode).
- Dédoublonnage par territoire et par mode ; passages et capacités sommés au sein d'une source, MAXIMUM entre
  sources (les flux régionaux agrégés reprennent les réseaux locaux).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer

from src.common.config import load_settings, raw
from src.common.geo import dedup_points
from src.ingest.archives import ign_gpkg
from src.ingest.offer import GTFS_EXCLUDE, gbfs_offer, gtfs_stop_frequencies
from src.national.common import bbox_territory, national, save_stages, stage

# CRS métrique de dédoublonnage par emprise
OFFER_CRS = {"met": 2154, "971": 5490, "972": 5490, "973": 2972, "974": 2975, "976": 4471}
COLS = ["id", "type", "sous_type", "nom", "source", "capacite", "passages_jour", "lon", "lat"]


def coord_mask(lon: pd.Series, lat: pd.Series) -> pd.Series:
    lo = pd.to_numeric(lon, errors="coerce").to_numpy(float)
    la = pd.to_numeric(lat, errors="coerce").to_numpy(float)
    return pd.Series(bbox_territory(lo, la) != "", index=lon.index)


def process_feed(path: str) -> dict:
    """Traite un flux GTFS (exécuté dans un processus fils) et écrit son cache."""
    path = Path(path)
    out = national("gtfs_stops", path.stem + ".parquet")
    t0 = time.perf_counter()
    try:
        df, info = gtfs_stop_frequencies(path, None, None, coord_mask)
    except Exception as e:  # noqa: BLE001  (flux corrompu ou non conforme : signalé, non bloquant)
        df, info = pd.DataFrame(), {"fichier": path.name, "erreur": f"{type(e).__name__}: {str(e)[:150]}"}
    if not df.empty:
        src = path.name.split("__")[0]
        df = df.assign(id=src + ":" + df["stop_id"] + ":" + df["type"], source="gtfs:" + src, sous_type="arret",
                       capacite=np.nan)[COLS]
    df.to_parquet(out, index=False)
    info["duree_s"] = round(time.perf_counter() - t0, 1)
    return info


def gtfs_national(workers: int = 2) -> pd.DataFrame:
    national("gtfs_stops").mkdir(parents=True, exist_ok=True)
    report_path = national("gtfs_report.csv")
    done = pd.read_csv(report_path) if report_path.exists() else pd.DataFrame(columns=["fichier"])
    todo = [str(p) for p in sorted(raw("gtfs").glob("*.zip"))
            if not any(k in p.name.lower() for k in GTFS_EXCLUDE)
            and not (national("gtfs_stops", p.stem + ".parquet").exists() and p.name in set(done["fichier"]))]
    todo.sort(key=lambda p: -Path(p).stat().st_size)          # gros flux d'abord : meilleur équilibrage
    print(f"  GTFS : {len(todo)} flux à traiter ({len(done)} déjà en cache)", flush=True)
    rows = []
    with cf.ProcessPoolExecutor(workers) as ex:
        for k, info in enumerate(ex.map(process_feed, todo), 1):
            rows.append(info)
            if k % 50 == 0 or info.get("duree_s", 0) > 60:
                print(f"    {k}/{len(todo)} {info['fichier'][:60]} {info.get('duree_s')} s", flush=True)
    rep = pd.concat([done, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("fichier", keep="last")
    rep.to_csv(report_path, index=False)
    return rep


def assign_departments(df: pd.DataFrame) -> pd.Series:
    deps = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="departement", columns=["code_insee"])
    pts = gpd.GeoDataFrame(index=df.index, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    j = gpd.sjoin(pts, deps, how="left", predicate="within")
    dep = j[~j.index.duplicated()]["code_insee"].reindex(df.index)
    miss = dep.isna()
    if miss.any():   # points en mer ou sur la frontière : département le plus proche (≤ 2 km)
        p = pts[miss].to_crs(2154)
        n = gpd.sjoin_nearest(p, deps.to_crs(2154), how="left", max_distance=2000)
        dep.loc[miss] = n[~n.index.duplicated()]["code_insee"].reindex(p.index)
    return dep


def build_offer() -> pd.DataFrame:
    s = load_settings()
    with stage("GTFS France (2 processus)"):
        rep = gtfs_national()
    with stage("assemblage GTFS"):
        gtfs = pd.concat([pd.read_parquet(f) for f in sorted(national("gtfs_stops").glob("*.parquet"))
                          if f.stat().st_size > 0], ignore_index=True)
    with stage("GBFS France"):
        gbfs = gbfs_offer(None, set(s["study_area"].get("gbfs_exclude_datasets") or []),
                          tuple(s["offer"].get("exclude_name_patterns") or ()), coord_mask=coord_mask)
    df = pd.concat([gtfs, gbfs.reindex(columns=COLS)], ignore_index=True)
    for c in ("passages_jour", "capacite", "lon", "lat"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["territoire"] = bbox_territory(df["lon"].to_numpy(), df["lat"].to_numpy())
    radius = {"default": s["offer"]["dedup_m"], **(s["offer"].get("dedup_m_by_type") or {})}
    parts, stats = [], []
    with stage("dédoublonnage par territoire et mode"):
        for terr, g in df.groupby("territoire"):
            crs = OFFER_CRS[terr]
            x, y = Transformer.from_crs(4326, crs, always_xy=True).transform(g["lon"].to_numpy(), g["lat"].to_numpy())
            gg = gpd.GeoDataFrame(g.drop(columns=["lon", "lat"]), geometry=gpd.points_from_xy(x, y), crs=crs)
            out, st = dedup_points(gg, radius=radius, by="type", source_col="source")
            ll = out.to_crs(4326)
            parts.append(pd.DataFrame(out.drop(columns="geometry")).assign(
                territoire=terr, x=out.geometry.x, y=out.geometry.y, lon=ll.geometry.x, lat=ll.geometry.y, crs=crs))
            stats.append(st.assign(territoire=terr))
        offer = pd.concat(parts, ignore_index=True)
    with stage("départements"):
        offer["dep"] = assign_departments(offer)
    offer.to_parquet(national("offer.parquet"), index=False)
    st = pd.concat(stats, ignore_index=True)
    st.to_csv(national("offer_dedup_stats.csv"), index=False)
    summary = {"flux_gtfs": len(rep), "flux_gtfs_en_erreur": int(rep["erreur"].notna().sum()) if "erreur" in rep else 0,
               "flux_gtfs_hors_periode": int(rep.get("jour_type_hors_periode", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
               "points_avant": int(st["avant"].sum()), "points_apres": len(offer),
               "par_type": offer["type"].value_counts().to_dict(), "par_territoire": offer["territoire"].value_counts().to_dict(),
               "sans_departement": int(offer["dep"].isna().sum())}
    national("offer_rapport.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    save_stages("offer")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return offer


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_offer()
