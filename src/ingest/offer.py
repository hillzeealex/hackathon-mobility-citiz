"""
Table unifiée de l'offre de mobilité sur la zone d'étude -> data/processed/offer.parquet

Colonnes : id, type, sous_type, nom, source, capacite, passages_jour, n_fusionnes, ids_fusionnes, geometry
  type ∈ {bus, tram, metro, train, telepherique, velo, trottinette, citiz, autopartage}

- GTFS : un point par (arrêt, mode) avec le nombre de passages un jour de semaine type
  (le mardi de la période de validité qui a le plus de services : évite les vacances scolaires).
- GBFS : stations physiques (vélo, Citiz, autopartage) et zones de stationnement virtuelles du
  free-floating (une ligne par mode proposé dans la zone : vélo et/ou trottinette).
- Dédoublonnage par mode à `offer.dedup_m` mètres (src/common/geo.py), statistiques avant/après
  dans data/processed/offer_dedup_stats.csv.

On garde l'offre dans la zone élargie du rayon de marche : un arrêt juste hors limite dessert
les habitants de la bordure.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from src.common.config import load_settings, processed, raw
from src.common.geo import dedup_points, valid_coords
from src.ingest.zone import load_zone

# route_type GTFS (standard + étendu) -> type d'offre
# 5 (« cable tram ») : utilisé en France par erreur pour des téléphériques (ex. Bastille, Grenoble)
ROUTE_TYPES = {0: "tram", 1: "metro", 2: "train", 3: "bus", 4: "bus", 5: "telepherique", 6: "telepherique",
               7: "telepherique", 11: "bus", 12: "metro"}
EXTENDED = [((100, 199), "train"), ((200, 299), "bus"), ((400, 499), "metro"), ((700, 799), "bus"),
            ((800, 899), "bus"), ((900, 999), "tram"), ((1300, 1399), "telepherique"),
            ((1400, 1499), "telepherique")]
GTFS_EXCLUDE = ("covoit",)  # lignes de covoiturage : pas une offre de transport collectif


def route_mode(rt) -> str | None:
    try:
        rt = int(rt)
    except (TypeError, ValueError):
        return None
    if rt in ROUTE_TYPES:
        return ROUTE_TYPES[rt]
    for (lo, hi), mode in EXTENDED:
        if lo <= rt <= hi:
            return mode
    return None


# ---------------------------------------------------------------------------------------------
# GTFS
# ---------------------------------------------------------------------------------------------
def _read(z: zipfile.ZipFile, name: str, **kw) -> pd.DataFrame:
    member = next((n for n in z.namelist() if Path(n).name == name), None)
    if member is None:
        return pd.DataFrame()
    with z.open(member) as f:
        return pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"), dtype=str, **kw)


def active_services(cal: pd.DataFrame, cal_dates: pd.DataFrame, day: dt.date) -> set[str]:
    """Services actifs à la date `day` (calendar.txt + exceptions calendar_dates.txt)."""
    d = day.strftime("%Y%m%d")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    act = set()
    if not cal.empty:
        m = (cal["start_date"] <= d) & (cal["end_date"] >= d) & (cal[wd] == "1")
        act = set(cal.loc[m, "service_id"])
    if not cal_dates.empty:
        cd = cal_dates[cal_dates["date"] == d]
        act |= set(cd.loc[cd["exception_type"] == "1", "service_id"])
        act -= set(cd.loc[cd["exception_type"] == "2", "service_id"])
    return act


def pick_weekday(cal: pd.DataFrame, cal_dates: pd.DataFrame, trips: pd.DataFrame,
                 forced: str | None = None, weeks: int = 8) -> dt.date:
    """Mardi « type » : celui des `weeks` prochaines semaines couvertes qui a le plus de courses."""
    if forced:
        return dt.date.fromisoformat(forced)
    dates = pd.concat([cal.get("start_date", pd.Series(dtype=str)), cal_dates.get("date", pd.Series(dtype=str))])
    start = max(dt.date.today(), dt.datetime.strptime(dates.min(), "%Y%m%d").date()) if len(dates) else dt.date.today()
    start += dt.timedelta(days=(1 - start.weekday()) % 7)  # prochain mardi
    trips_by_service = trips.groupby("service_id").size()
    best, best_n = start, -1
    for k in range(weeks):
        day = start + dt.timedelta(weeks=k)
        n = int(trips_by_service.reindex(list(active_services(cal, cal_dates, day))).fillna(0).sum())
        if n > best_n:
            best, best_n = day, n
    return best


def _seconds(hms: str) -> int:
    h, m, s = (int(x) for x in str(hms).split(":"))
    return h * 3600 + m * 60 + s


def trip_departures(freq: pd.DataFrame) -> pd.Series:
    """Nombre de départs réels par trip_id décrit dans frequencies.txt (les autres courses valent 1)."""
    if freq.empty:
        return pd.Series(dtype=float)
    span = freq["end_time"].map(_seconds) - freq["start_time"].map(_seconds)
    n = np.ceil(span / freq["headway_secs"].astype(float)).clip(lower=1)
    return n.groupby(freq["trip_id"]).sum()


def gtfs_stop_frequencies(path: Path, area_wgs84, forced_day: str | None = None) -> tuple[pd.DataFrame, dict]:
    """[stop_id, nom, lon, lat, type, passages_jour] pour les arrêts de `area_wgs84`."""
    with zipfile.ZipFile(path) as z:
        stops = _read(z, "stops.txt")
        if stops.empty:
            return pd.DataFrame(), {"fichier": path.name, "erreur": "stops.txt absent"}
        if "location_type" in stops:
            stops = stops[stops["location_type"].fillna("0").isin(["0", ""])]
        stops = stops[valid_coords(stops["stop_lon"], stops["stop_lat"])]
        minx, miny, maxx, maxy = area_wgs84.bounds
        lon, lat = stops["stop_lon"].astype(float), stops["stop_lat"].astype(float)
        stops = stops[lon.between(minx, maxx) & lat.between(miny, maxy)]
        pts = gpd.GeoSeries(gpd.points_from_xy(stops["stop_lon"].astype(float), stops["stop_lat"].astype(float)), crs=4326)
        stops = stops[pts.within(area_wgs84).to_numpy()]
        info = {"fichier": path.name, "arrets_zone": len(stops)}
        if stops.empty:
            return pd.DataFrame(), info
        routes = _read(z, "routes.txt", usecols=lambda c: c in ("route_id", "route_type"))
        trips = _read(z, "trips.txt", usecols=lambda c: c in ("route_id", "service_id", "trip_id"))
        cal = _read(z, "calendar.txt")
        cal_dates = _read(z, "calendar_dates.txt")
        day = pick_weekday(cal, cal_dates, trips, forced_day)
        act = active_services(cal, cal_dates, day)
        trips = trips[trips["service_id"].isin(act)].merge(routes, on="route_id", how="left")
        trips["type"] = trips["route_type"].map(route_mode)
        trip_mode = trips.dropna(subset=["type"]).set_index("trip_id")["type"]
        weight = trip_departures(_read(z, "frequencies.txt"))
        keep = set(stops["stop_id"])
        counts = []
        member = next(n for n in z.namelist() if Path(n).name == "stop_times.txt")
        with z.open(member) as f:
            for chunk in pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"), dtype=str,
                                     usecols=["trip_id", "stop_id"], chunksize=1_000_000):
                chunk = chunk[chunk["stop_id"].isin(keep)]
                chunk = chunk.assign(type=chunk["trip_id"].map(trip_mode)).dropna(subset=["type"])
                chunk["w"] = chunk["trip_id"].map(weight).fillna(1.0)
                counts.append(chunk.groupby(["stop_id", "type"])["w"].sum())
    freq = pd.concat(counts).groupby(level=[0, 1]).sum().rename("passages_jour").reset_index() if counts else pd.DataFrame()
    info.update({"jour_type": day.isoformat(), "services_actifs": len(act), "courses": len(trip_mode)})
    if freq.empty:
        return freq, info
    out = freq.merge(stops[["stop_id", "stop_name", "stop_lon", "stop_lat"]], on="stop_id")
    out = out.rename(columns={"stop_name": "nom", "stop_lon": "lon", "stop_lat": "lat"})
    info["points_desservis"] = len(out)
    return out, info


def gtfs_offer(area_wgs84, forced_day: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, report = [], []
    for path in sorted(raw("gtfs").glob("*.zip")):
        if any(k in path.name.lower() for k in GTFS_EXCLUDE):
            report.append({"fichier": path.name, "erreur": "exclu (covoiturage)"})
            continue
        try:
            df, info = gtfs_stop_frequencies(path, area_wgs84, forced_day)
        except (zipfile.BadZipFile, KeyError, ValueError, StopIteration) as e:
            df, info = pd.DataFrame(), {"fichier": path.name, "erreur": f"{type(e).__name__}: {e}"}
        report.append(info)
        if not df.empty:
            src = path.name.split("__")[0]
            df["id"] = src + ":" + df["stop_id"] + ":" + df["type"]
            df["source"] = "gtfs:" + src
            df["sous_type"] = "arret"
            rows.append(df)
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), pd.DataFrame(report)


# ---------------------------------------------------------------------------------------------
# GBFS
# ---------------------------------------------------------------------------------------------
FORM_FACTOR = {"bicycle": "velo", "cargo_bicycle": "velo", "scooter": "trottinette",
               "scooter_standing": "trottinette", "scooter_seated": "trottinette", "car": "autopartage",
               "moped": "scooter"}


def _gbfs_list(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
    return data.get(key, []) if isinstance(data, dict) else []


def _text(v) -> str:
    return (v[0].get("text", "") if v else "") if isinstance(v, list) else (v or "")


def gbfs_offer(area_wgs84, exclude: set[str], name_patterns: tuple[str, ...] = ()) -> pd.DataFrame:
    catalog = {d["slug"]: d for d in json.loads(raw("transport_data_gouv", "catalogue_datasets.json").read_text(encoding="utf-8"))}
    rows = []
    for root, is_citiz in ((raw("gbfs_citiz"), True), (raw("gbfs_all"), False)):
        for s in json.loads((root / "index.json").read_text(encoding="utf-8")):
            if s.get("error") or s["dataset"] in exclude:
                continue
            d = Path(s["dir"])
            subs = catalog.get(s["dataset"], {}).get("sub_types") or []
            modes = sorted({FORM_FACTOR.get(t.get("form_factor"))
                            for t in _gbfs_list(d / "vehicle_types.json", "vehicle_types")} - {None})
            if is_citiz:
                modes = ["citiz"]
            elif not modes:
                modes = (["velo"] if "bicycle" in subs else []) + (["trottinette"] if "scooter" in subs else []) \
                        or (["autopartage"] if "carsharing" in subs else [])
            modes = [m for m in modes if m != "scooter"]  # scooters thermiques/électriques : hors périmètre
            for st in _gbfs_list(d / "station_information.json", "stations"):
                virtual = bool(st.get("is_virtual_station"))
                for m in (modes if virtual or is_citiz else modes[:1]):
                    rows.append({"id": f"{s['dataset']}:{st['station_id']}:{m}", "type": m,
                                 "sous_type": "zone_free_floating" if virtual else "station",
                                 "nom": _text(st.get("name")).strip(), "source": f"gbfs:{s['dataset']}",
                                 "capacite": st.get("capacity"), "lon": st.get("lon"), "lat": st.get("lat")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[valid_coords(df["lon"], df["lat"])]
    if name_patterns:
        df = df[~df["nom"].str.lower().str.contains("|".join(name_patterns), regex=True)]
    pts = gpd.GeoSeries(gpd.points_from_xy(df["lon"].astype(float), df["lat"].astype(float)), crs=4326)
    return df[pts.within(area_wgs84).to_numpy()].copy()


# ---------------------------------------------------------------------------------------------
def build_offer(parts: tuple[str, ...] = ("gtfs", "gbfs")) -> gpd.GeoDataFrame:
    s = load_settings()
    zone = load_zone()
    zone_union = zone.union_all()
    area = zone_union.buffer(s["walk"]["radius_large_m"])
    area_wgs84 = gpd.GeoSeries([area], crs=s["crs"]["metric"]).to_crs(4326).iloc[0]

    frames, gtfs_report = [], pd.DataFrame()
    if "gtfs" in parts:
        gtfs, gtfs_report = gtfs_offer(area_wgs84, s["offer"].get("typical_weekday"))
        frames.append(gtfs)
        print(gtfs_report.to_string(index=False), end="\n\n")
    if "gbfs" in parts:
        frames.append(gbfs_offer(area_wgs84, set(s["study_area"].get("gbfs_exclude_datasets") or []),
                                 tuple(s["offer"].get("exclude_name_patterns") or ())))
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    for c in ("passages_jour", "capacite"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"].astype(float), df["lat"].astype(float)),
                           crs=4326).to_crs(s["crs"]["metric"])
    cols = ["id", "type", "sous_type", "nom", "source", "capacite", "passages_jour", "geometry"]
    out, stats = dedup_points(gdf[cols], radius=s["offer"]["dedup_m"], by="type")
    out["dans_zone"] = out.within(zone_union)
    out = out[cols[:-1] + ["n_fusionnes", "ids_fusionnes", "dans_zone", "geometry"]]
    out.attrs["zone_provisoire"] = zone.attrs.get("provisoire", False)

    out.to_parquet(processed("offer.parquet"))
    stats.to_csv(processed("offer_dedup_stats.csv"), index=False)
    if not gtfs_report.empty:
        gtfs_report.to_csv(processed("offer_gtfs_report.csv"), index=False)
    print(stats.to_string(index=False), end="\n\n")
    print(f"offer.parquet : {len(out)} points ({int(out.dans_zone.sum())} dans la zone), parties : {', '.join(parts)}"
          + ("  [zone PROVISOIRE]" if zone.attrs.get("provisoire") else ""))
    return out


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Construit data/processed/offer.parquet")
    ap.add_argument("--parts", nargs="+", choices=["gtfs", "gbfs"], default=["gtfs", "gbfs"])
    build_offer(tuple(ap.parse_args().parts))
