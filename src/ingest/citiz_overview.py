#!/usr/bin/env python3
"""
Vue d'ensemble des stations Citiz (GBFS) : une ligne par station, rattachée à sa commune et à son EPCI.

Le rattachement commune/EPCI utilise l'API publique geo.api.gouv.fr (réponses mises en cache dans
data/raw/geo_cache/) : utile pour choisir le périmètre d'étude avant de télécharger ADMIN EXPRESS.

Usage :
    python src/ingest/citiz_overview.py
Sorties :
    data/processed/citiz_stations.csv    une ligne par station
    data/processed/citiz_by_epci.csv     agrégat par EPCI (stations, capacité, véhicules)
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CACHE = RAW / "geo_cache" / "citiz_communes.json"
GEO_API = "https://geo.api.gouv.fr/communes"
UA = "Mozilla/5.0 (hackathon-mobility-epitech)"


def text(v) -> str:
    """GBFS v3 : chaînes localisées [{text, language}] ; v2 : chaîne simple."""
    if isinstance(v, list):
        return (v[0].get("text") if v else "") or ""
    return v or ""


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8")).get("data", {})
    return d.get("stations") or d.get("vehicles") or d.get("bikes") or []


def read_stations() -> list[dict]:
    index = json.loads((RAW / "gbfs_citiz" / "index.json").read_text(encoding="utf-8"))
    rows = []
    for s in index:
        d = Path(s["dir"])
        sysinfo = json.loads((d / "system_information.json").read_text(encoding="utf-8"))["data"]
        network = sysinfo.get("system_id") or s["dataset"]
        status = {x["station_id"]: x for x in load(d / "station_status.json")}
        n_veh_by_station = defaultdict(int)
        for v in load(d / "vehicle_status.json"):
            if v.get("station_id"):
                n_veh_by_station[v["station_id"]] += 1
        for st in load(d / "station_information.json"):
            sid = st["station_id"]
            ss = status.get(sid, {})
            rows.append({
                "network": network, "network_name": text(sysinfo.get("name")).strip(),
                "station_id": sid, "uid": f"{network}:{sid}", "name": text(st.get("name")).strip(),
                "lat": st.get("lat"), "lon": st.get("lon"), "capacity": st.get("capacity") or 0,
                "vehicles_available": ss.get("num_vehicles_available", ss.get("num_bikes_available")) or 0,
                "vehicles_at_station": n_veh_by_station.get(sid, 0),
                "is_virtual": st.get("is_virtual_station", False), "parking_type": st.get("parking_type", ""),
            })
    return rows


def geocode(lat: float, lon: float) -> dict:
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "fields": "nom,code,codeEpci,epci,population,codeDepartement"})
    req = urllib.request.Request(f"{GEO_API}?{q}", headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
            return res[0] if res else {}
        except Exception:  # noqa: BLE001  (limite de débit / coupure : on retente)
            time.sleep(1 + attempt)
    return {}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = read_stations()
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    key = lambda r: f"{float(r['lat']):.5f},{float(r['lon']):.5f}"  # noqa: E731
    todo = sorted({key(r) for r in rows if r["lat"] and r["lon"]} - cache.keys())
    print(f"{len(rows)} stations, {len(todo)} à géocoder (cache : {len(cache)})")
    with cf.ThreadPoolExecutor(8) as ex:  # geo.api.gouv.fr : 50 requêtes/s max
        for k, res in zip(todo, ex.map(lambda k: geocode(*map(float, k.split(","))), todo)):
            cache[k] = res
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    for r in rows:
        g = cache.get(key(r), {}) if r["lat"] and r["lon"] else {}
        r.update({"commune": g.get("nom", ""), "code_insee": g.get("code", ""),
                  "code_epci": g.get("codeEpci", ""), "epci": (g.get("epci") or {}).get("nom", ""),
                  "departement": g.get("codeDepartement", "")})
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED / "citiz_stations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["code_epci"] or "?", {"code_epci": r["code_epci"], "epci": r["epci"] or "(hors France / non trouvé)",
                                                   "networks": set(), "communes": set(), "stations": 0,
                                                   "capacity": 0, "vehicles_available": 0})
        a["networks"].add(r["network"])
        a["communes"].add(r["commune"])
        a["stations"] += 1
        a["capacity"] += int(r["capacity"])
        a["vehicles_available"] += int(r["vehicles_available"])
    out = sorted(agg.values(), key=lambda a: -a["stations"])
    with open(PROCESSED / "citiz_by_epci.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code_epci", "epci", "networks", "n_communes", "stations",
                                          "capacity", "vehicles_available"])
        w.writeheader()
        for a in out:
            w.writerow({**{k: a[k] for k in ("code_epci", "epci", "stations", "capacity", "vehicles_available")},
                        "networks": " ".join(sorted(a["networks"])), "n_communes": len(a["communes"])})
    missing = sum(1 for r in rows if not r["code_insee"])
    print(f"{len(out)} EPCI ; {missing} stations sans commune trouvée")
    print(f"{'EPCI':<55} {'stations':>8} {'capacité':>8} {'dispo':>6}  communes")
    for a in out[:20]:
        print(f"{a['epci'][:55]:<55} {a['stations']:>8} {a['capacity']:>8} {a['vehicles_available']:>6}  {len(a['communes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
