"""
Niveau 1 : fichiers légers pour l'application (WGS84) -> data/processed/national/app/

  departements.parquet        polygones simplifiés (~200 m) + indicateurs agrégés
  epci.parquet                polygones simplifiés (~300 m) + classement
  dep/<dep>_iris.parquet      IRIS du département (~10 m) + indicateurs   (chargé à la demande)
  dep/<dep>_carreaux.parquet  carreaux >= 11 ménages, carrés de 200 m      (chargé à la demande)
"""
from __future__ import annotations

import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

from src.common.config import load_settings
from src.ingest.archives import ign_gpkg
from src.national.common import TERRITORIES, national, read_parquet_dir, save_stages, stage

CELL_COLS = ["idcar_200m", "dep", "code_iris", "x", "y", "territoire", "pop_calee", "men", "part_sans_voiture",
             "n_options", "n_points", "n_tc", "n_citiz", "acces_1000", "citiz_1000"]


def squares(df: pd.DataFrame, half: float = 100.0) -> gpd.GeoSeries:
    """Carrés de 200 m autour des centroïdes (CRS métrique du territoire), reprojetés en WGS84."""
    out = []
    for terr, g in df.groupby("territoire"):
        geom = shapely.box(g.x - half, g.y - half, g.x + half, g.y + half)
        out.append(gpd.GeoSeries(geom, index=g.index, crs=TERRITORIES[terr]).to_crs(4326))
    return pd.concat(out).reindex(df.index)


def build_app_files() -> dict:
    min_men = load_settings()["privacy"]["min_households"]
    folder = national("app", "dep")
    folder.mkdir(parents=True, exist_ok=True)
    ade = ign_gpkg("admin_express")
    with stage("carte nationale (départements, EPCI)"):
        deps = pyogrio.read_dataframe(ade, layer="departement", columns=["code_insee", "nom_officiel"]).rename(
            columns={"code_insee": "dep", "nom_officiel": "nom"})
        deps["geometry"] = deps.geometry.simplify(0.002)
        agg_dep = pd.read_parquet(national("agg_departement.parquet"))
        deps.merge(agg_dep, on="dep", how="left").to_parquet(national("app", "departements.parquet"))
        epci = gpd.read_parquet(national("geo_epci.parquet"))
        rank = pd.read_parquet(national("classement_epci.parquet")).drop(columns=["nom"], errors="ignore")
        epci.merge(rank, on="code_epci", how="left").to_parquet(national("app", "epci.parquet"))
    with stage("IRIS par département"):
        iris = pyogrio.read_dataframe(ign_gpkg("iris"), columns=["code_iris", "nom_iris", "nom_commune", "code_insee"])
        iris["geometry"] = iris.geometry.simplify(0.0001)
        agg_iris = pd.read_parquet(national("agg_iris.parquet"))
        iris = iris.merge(agg_iris, on="code_iris", how="inner")
        iris["dep"] = np.where(iris["code_insee"].str.startswith("97"), iris["code_insee"].str[:3], iris["code_insee"].str[:2])
        for dep, g in iris.groupby("dep"):
            g.to_parquet(folder / f"{dep}_iris.parquet")
    sizes = {}
    with stage("carreaux par département (>= 11 ménages)"):
        cells = read_parquet_dir(national("access"), columns=CELL_COLS)
        hidden = int((cells["men"] < min_men).sum())
        cells = cells[cells["men"] >= min_men]
        for dep, g in cells.groupby("dep"):
            gdf = gpd.GeoDataFrame(g.drop(columns=["x", "y"]), geometry=squares(g), crs=4326)
            path = folder / f"{dep}_carreaux.parquet"
            gdf.to_parquet(path)
            sizes[dep] = round(path.stat().st_size / 1024 ** 2, 2)
    rep = {"carreaux_masques_lt_11_menages": hidden, "fichiers_departement": len(sizes),
           "taille_max_carreaux_mo": max(sizes.values()), "taille_totale_mo": round(sum(sizes.values()), 1)}
    national("app_rapport.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    save_stages("app_files")
    print(json.dumps(rep, indent=1))
    return rep


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_app_files()
