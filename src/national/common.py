"""Niveau 1 (France entière) : territoires, chemins et mesure du temps / de la mémoire."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from pyproj import Transformer

from src.common.config import processed

# Territoire -> CRS métrique de calcul. Filosofi 200 m n'existe que pour la métropole, la Martinique et la Réunion.
TERRITORIES = {"met": 2154, "mart": 5490, "reun": 2975}
FILOSOFI_FILES = {"met": "carreaux_200m_met.gpkg", "mart": "carreaux_200m_mart.gpkg", "reun": "carreaux_200m_reun.gpkg"}
DROM_DEPS = {"971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte"}
DEP_TERRITORY = {"972": "mart", "974": "reun"}           # les autres départements de Filosofi : métropole
# Emprises WGS84 (lon_min, lat_min, lon_max, lat_max) pour filtrer les coordonnées aberrantes
BBOXES = {"met": (-5.8, 41.2, 10.0, 51.3), "971": (-61.9, 15.8, -60.9, 16.6), "972": (-61.3, 14.3, -60.7, 14.9),
          "973": (-54.7, 2.0, -51.5, 5.9), "974": (55.1, -21.5, 55.9, -20.8), "976": (44.9, -13.1, 45.4, -12.5)}


def national(*parts: str) -> Path:
    return processed("national", *parts)


def territory_of_dep(dep: str) -> str:
    return DEP_TERRITORY.get(dep, "met")


def bbox_territory(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Nom de l'emprise (met, 971…976) contenant chaque point, '' si aucune (coordonnée aberrante)."""
    out = np.full(len(lon), "", dtype=object)
    for name, (x0, y0, x1, y1) in BBOXES.items():
        m = (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1) & ~((lon == 0) & (lat == 0))
        out[m & (out == "")] = name
    return out


def to_metric(lon, lat, territory: str):
    return Transformer.from_crs(4326, TERRITORIES[territory], always_xy=True).transform(lon, lat)


# ---------------------------------------------------------------------------------------------
STAGES: list[dict] = []


def peak_mb() -> float:
    mi = psutil.Process().memory_info()
    return round(getattr(mi, "peak_wset", mi.rss) / 1024 ** 2)


@contextmanager
def stage(name: str):
    """Mesure la durée d'une étape et le pic de mémoire du processus (working set de pointe Windows)."""
    t0 = time.perf_counter()
    rss0 = psutil.Process().memory_info().rss
    yield
    rec = {"etape": name, "duree_s": round(time.perf_counter() - t0, 1),
           "memoire_fin_mo": round(psutil.Process().memory_info().rss / 1024 ** 2),
           "delta_mo": round((psutil.Process().memory_info().rss - rss0) / 1024 ** 2),
           "pic_processus_mo": peak_mb()}
    STAGES.append(rec)
    print(f"  [{name}] {rec['duree_s']} s, mémoire {rec['memoire_fin_mo']} Mo (pic {rec['pic_processus_mo']} Mo)", flush=True)


def save_stages(script: str) -> None:
    path = national("mesures.json")
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old[script] = STAGES
    path.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")


def read_parquet_dir(folder: Path, columns=None) -> pd.DataFrame:
    files = sorted(folder.glob("*.parquet"))
    return pd.concat([pd.read_parquet(f, columns=columns) for f in files], ignore_index=True) if files else pd.DataFrame()
