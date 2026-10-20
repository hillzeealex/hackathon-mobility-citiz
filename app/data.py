"""
Contrat de données entre le pipeline (src/) et l'application : l'appli ne lit QUE ces fichiers précalculés,
produits par `python -m scripts.build_all --ville <ville>` dans data/processed/<ville>/.
Toutes les géométries sont en GeoParquet, CRS EPSG:2154 ; l'appli les reprojette en WGS84 pour l'affichage.

cells.parquet       un carreau habité de 200 m par ligne
    id, population, menages, priorite_equite [0-1], n_options (pondéré), score_acces (2SFCA, options / 1 000 hab.),
    code_iris, couvert_citiz_station (déjà à 5 min d'un autopartage), part_sans_voiture, geometry (Polygon)
iris.parquet        agrégat IRIS pour l'affichage public
    code_iris, nom, population, menages, n_options, score_acces, geometry (MultiPolygon)
offer_served.parquet  un point d'offre par ligne (offer.parquet + population desservie, objectif 2)
    id, type, sous_type, nom, source, capacite, passages_jour, dans_zone, pop_desservie, pop_seule_option,
    part_seule_option, version, geometry (Point)
meta.json           {"zone", "ville", "date", "demo": false, "version_acces", "jour_type_gtfs", ...}
Recommandations (villes avec `recommandations: true`) :
candidates.parquet  emplacements candidats, dans l'ordre des colonnes de coverage.npz
    id, type, nom, cout, usage_predit, x, y (Lambert-93), origine, commune, geometry (Point)
coverage.npz        matrice creuse booléenne carreaux × candidats (scipy.sparse.save_npz), lignes = cells.parquet
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "processed"
FILES = ("cells.parquet", "iris.parquet", "offer_served.parquet", "meta.json")
RECO_FILES = ("candidates.parquet", "coverage.npz")


def city_folder(ville: str) -> Path:
    return REAL / ville


def available(folder: Path) -> bool:
    return all((folder / f).exists() for f in FILES)


def has_reco(folder: Path) -> bool:
    return all((folder / f).exists() for f in RECO_FILES)


def load_all(folder: Path) -> dict:
    names = FILES + (RECO_FILES if has_reco(folder) else ())
    d = {name.split(".")[0]: gpd.read_parquet(folder / name) for name in names if name.endswith(".parquet")}
    if has_reco(folder):
        d["coverage"] = sp.load_npz(folder / "coverage.npz").tocsr()
    d["meta"] = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    return d
