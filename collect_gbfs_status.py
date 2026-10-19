#!/usr/bin/env python3
"""
Collecte l'historique de disponibilité des stations GBFS (Citiz par défaut).

Les flux GBFS ne donnent que l'état instantané. En prenant une "photo" de station_status
toutes les N minutes pendant le hackathon, on peut estimer l'usage réel de chaque station
(nombre de départs / retours = variations du nombre de véhicules disponibles), ce qui
fournit une cible pour le modèle prédictif.

Pré-requis : avoir lancé `python download_all.py --only citiz` (crée data/raw/gbfs_citiz/index.json).

Usage :
    python collect_gbfs_status.py                       # Citiz, toutes les 5 min, sans fin
    python collect_gbfs_status.py --interval 2 --hours 48
    python collect_gbfs_status.py --index data/raw/gbfs_all/index.json   # tous les GBFS

Sortie : data/raw/gbfs_history/station_status_AAAAMMJJ.csv (une ligne par station et par photo)
Laisse-le tourner dans un terminal à part (ou sur un serveur) dès le début du hackathon.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (hackathon-mobility-epitech gbfs collector)"
FIELDS = ["snapshot_utc", "dataset", "station_id", "num_vehicles_available",
          "num_docks_available", "is_renting", "is_returning", "last_reported"]


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def status_rows(dataset: str, payload: dict, snap: str):
    for s in payload.get("data", {}).get("stations", []):
        # GBFS v2 : num_bikes_available ; v3 : num_vehicles_available
        n = s.get("num_vehicles_available", s.get("num_bikes_available"))
        yield {"snapshot_utc": snap, "dataset": dataset, "station_id": s.get("station_id"),
               "num_vehicles_available": n, "num_docks_available": s.get("num_docks_available"),
               "is_renting": s.get("is_renting"), "is_returning": s.get("is_returning"),
               "last_reported": s.get("last_reported")}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", default="data/raw/gbfs_citiz/index.json")
    p.add_argument("--out", default="data/raw/gbfs_history")
    p.add_argument("--interval", type=float, default=5, help="minutes entre deux photos")
    p.add_argument("--hours", type=float, default=0, help="durée totale (0 = sans fin)")
    a = p.parse_args()

    systems = json.loads(Path(a.index).read_text(encoding="utf-8"))
    targets = [(s["dataset"], s["feeds"]["station_status"]) for s in systems
               if s.get("feeds", {}).get("station_status")]
    if not targets:
        print("Aucun flux station_status dans l'index. Lance d'abord download_all.py.")
        return 1
    print(f"{len(targets)} systèmes suivis, une photo toutes les {a.interval} min. Ctrl+C pour arrêter.")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    end = time.time() + a.hours * 3600 if a.hours else None
    try:
        while end is None or time.time() < end:
            t0 = time.time()
            now = dt.datetime.now(dt.timezone.utc)
            snap = now.isoformat(timespec="seconds")
            path = out / f"station_status_{now:%Y%m%d}.csv"
            new = not path.exists()
            n_rows, n_err = 0, 0
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    w.writeheader()
                for ds, url in targets:
                    try:
                        for row in status_rows(ds, get_json(url), snap):
                            w.writerow(row)
                            n_rows += 1
                    except Exception:  # noqa: BLE001
                        n_err += 1
            print(f"{snap}  {n_rows} stations  ({n_err} flux en erreur)", flush=True)
            time.sleep(max(0, a.interval * 60 - (time.time() - t0)))
    except KeyboardInterrupt:
        print("Arrêt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
