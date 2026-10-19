"""
Contrat de données entre le pipeline (src/) et l'application : l'appli ne lit QUE ces fichiers précalculés.

Dossier : data/processed/ (données réelles) ou data/processed/demo/ (données factices, scripts/make_demo_data.py).
Toutes les géométries sont en GeoParquet, CRS EPSG:2154 ; l'appli les reprojette en WGS84 pour l'affichage.

cells.parquet       un carreau habité de 200 m par ligne
    id, population, menages, priorite_equite [0-1], n_options (pondéré), score_acces (options / 1 000 hab),
    code_iris, couvert_<type> (bool, pour chaque type d'équipement candidat), geometry (Polygon)
iris.parquet        agrégat IRIS pour l'affichage public
    code_iris, nom, population, menages, n_options, score_acces, geometry (MultiPolygon)
offer_served.parquet  un point d'offre par ligne (offer.parquet + population desservie)
    id, type, sous_type, nom, source, capacite, passages_jour, pop_desservie, pop_seule_option,
    part_seule_option, geometry (Point)
candidates.parquet  emplacements candidats, dans l'ordre des colonnes de coverage.npz
    id, type, nom, cout, usage_predit, x, y (Lambert-93), geometry (Point)
coverage.npz        matrice creuse booléenne carreaux × candidats (scipy.sparse.save_npz), lignes = cells.parquet
meta.json           {"zone": ..., "date": ..., "demo": bool, ...}
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "processed"
DEMO = REAL / "demo"
FILES = ("cells.parquet", "iris.parquet", "offer_served.parquet", "candidates.parquet", "coverage.npz", "meta.json")


def available(folder: Path) -> bool:
    return all((folder / f).exists() for f in FILES)


def load_all(folder: Path) -> dict:
    d = {name.split(".")[0]: gpd.read_parquet(folder / name) for name in FILES if name.endswith(".parquet")}
    d["coverage"] = sp.load_npz(folder / "coverage.npz").tocsr()
    d["meta"] = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    return d
