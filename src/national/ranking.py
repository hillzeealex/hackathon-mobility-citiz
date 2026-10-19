"""
Niveau 1 : classement national des EPCI -> data/processed/national/classement_epci.{parquet,csv}

Par EPCI : population calée, densité vécue (moyenne des densités des carreaux pondérée par la population),
accessibilité V1 (options moyennes, part sans option, part avec TC), motorisation, autopartage existant
(stations Citiz, autres stations d'autopartage, voitures en free-floating GBFS) et risque de vol / dégradation
(SSMSI 2023-2025, faits pour 1 000 habitants).

Potentiel Citiz (EPCI >= MIN_POP habitants) = moyenne des rangs-percentiles de
  densité vécue (↑), part de ménages sans voiture (↑), autopartage existant pour 10 000 hab. (↓).
Le risque de vol est affiché à côté et dans une variante (score_avec_risque), pas dans le score principal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from src.common.config import raw
from src.ingest.archives import ign_gpkg
from src.national.common import bbox_territory, national, save_stages, stage

MIN_POP = 50_000
THEFT = ["Vols de véhicule", "Vols dans les véhicules", "Vols d'accessoires sur véhicules"]
DEGRADATION = "Destructions et dégradations volontaires"


def freefloating_cars() -> pd.DataFrame:
    """Voitures d'autopartage sans station (GBFS free_bike_status / vehicle_status, form_factor = car)."""
    rows = []
    for root in (raw("gbfs_citiz"), raw("gbfs_all")):
        for s in json.loads((root / "index.json").read_text(encoding="utf-8")):
            d = Path(s["dir"])
            vt_path = d / "vehicle_types.json"
            cars = set()
            if vt_path.exists():
                vts = json.loads(vt_path.read_text(encoding="utf-8")).get("data", {}).get("vehicle_types", [])
                cars = {v.get("vehicle_type_id") for v in vts if v.get("form_factor") == "car"}
            for name in ("vehicle_status.json", "free_bike_status.json"):
                p = d / name
                if not p.exists() or not cars:
                    continue
                data = json.loads(p.read_text(encoding="utf-8")).get("data", {})
                for v in data.get("vehicles") or data.get("bikes") or []:
                    if v.get("vehicle_type_id") in cars and not v.get("station_id") and v.get("lat") is not None:
                        rows.append({"dataset": s["dataset"], "lon": float(v["lon"]), "lat": float(v["lat"])})
                break
    df = pd.DataFrame(rows, columns=["dataset", "lon", "lat"])
    return df[bbox_territory(df["lon"].to_numpy(), df["lat"].to_numpy()) != ""] if len(df) else df


def points_to_epci(df: pd.DataFrame, epci: gpd.GeoDataFrame) -> pd.Series:
    pts = gpd.GeoDataFrame(index=df.index, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    j = gpd.sjoin(pts, epci[["code_epci", "geometry"]], how="left", predicate="within")
    return j[~j.index.duplicated()]["code_epci"].reindex(df.index)


def security_by_commune() -> pd.DataFrame:
    """Faits 2023-2025 par commune (index code_insee) : vols liés aux véhicules, dégradations, population cumulée."""
    d = pd.read_parquet(raw("securite", "delinquance_communale_2025.parquet"),
                        columns=["CODGEO_2026", "annee", "indicateur", "nombre", "complement_info_nombre", "insee_pop"])
    d = d[d["annee"].isin([2023, 2024, 2025]) & d["indicateur"].isin(THEFT + [DEGRADATION])]
    d["faits"] = d["nombre"].fillna(d["complement_info_nombre"]).fillna(0)
    pop = d.drop_duplicates(["CODGEO_2026", "annee"]).groupby("CODGEO_2026")["insee_pop"].sum()
    theft = d[d["indicateur"].isin(THEFT)].groupby("CODGEO_2026")["faits"].sum()
    degr = d[d["indicateur"] == DEGRADATION].groupby("CODGEO_2026")["faits"].sum()
    return pd.DataFrame({"pop_3ans": pop, "vols": theft, "degradations": degr}).rename_axis("code_insee")


def security_rates(sec: pd.DataFrame, key) -> pd.DataFrame:
    """Taux pour 1 000 habitants (moyenne annuelle 2023-2025) après regroupement des communes selon `key`."""
    g = sec.groupby(key).sum(min_count=1)
    return pd.DataFrame({"vols_vehicules_1000": 1000 * g["vols"] / g["pop_3ans"],
                         "degradations_1000": 1000 * g["degradations"] / g["pop_3ans"]})


def security_by_epci() -> pd.DataFrame:
    com = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="commune", read_geometry=False,
                                 columns=["code_insee", "codes_siren_des_epci"])
    com["code_epci"] = com["codes_siren_des_epci"].fillna("").str.split(r"[/,; ]+").str[0]
    sec = security_by_commune()
    return security_rates(sec, sec.index.map(com.set_index("code_insee")["code_epci"]))


def build_ranking() -> pd.DataFrame:
    with stage("classement EPCI"):
        epci = pyogrio.read_dataframe(ign_gpkg("admin_express"), layer="epci",
                                      columns=["code_siren", "nom_officiel", "nature"]).rename(
            columns={"code_siren": "code_epci", "nom_officiel": "nom"})
        epci["superficie_km2"] = epci.to_crs(6933).area / 1e6          # équivalente (métropole + DROM)
        agg = pd.read_parquet(national("agg_epci.parquet"))
        offer = pd.read_parquet(national("offer.parquet"), columns=["type", "sous_type", "capacite", "lon", "lat"])
        cs = offer[offer["type"].isin(["citiz", "autopartage"]) & (offer["sous_type"] == "station")].copy()
        cs["code_epci"] = points_to_epci(cs, epci)
        ff = freefloating_cars()
        ff["code_epci"] = points_to_epci(ff, epci) if len(ff) else pd.Series(dtype=str)
        t = epci.drop(columns="geometry").merge(agg, on="code_epci", how="inner")
        t["stations_citiz"] = t["code_epci"].map(cs[cs["type"] == "citiz"].groupby("code_epci").size()).fillna(0).astype(int)
        t["vehicules_citiz"] = t["code_epci"].map(cs[cs["type"] == "citiz"].groupby("code_epci")["capacite"].sum()).fillna(0)
        t["stations_autres_autopartage"] = t["code_epci"].map(cs[cs["type"] == "autopartage"].groupby("code_epci").size()).fillna(0).astype(int)
        t["voitures_free_floating"] = t["code_epci"].map(ff.groupby("code_epci").size() if len(ff) else pd.Series(dtype=int)).fillna(0).astype(int)
        t["autopartage_10k_hab"] = 1e4 * (t.stations_citiz + t.stations_autres_autopartage + t.voitures_free_floating) / t.population
        t["citiz_stations_100k_hab"] = 1e5 * t.stations_citiz / t.population
        t = t.merge(security_by_epci(), left_on="code_epci", right_index=True, how="left")
        big = t["population"] >= MIN_POP
        pct = lambda c: t.loc[big, c].rank(pct=True)  # noqa: E731
        t.loc[big, "score_potentiel_citiz"] = (pct("densite_vecue_hab_km2") + pct("part_menages_sans_voiture")
                                               + (1 - pct("autopartage_10k_hab"))) / 3
        t.loc[big, "score_avec_risque"] = t.loc[big, "score_potentiel_citiz"] - 0.25 * pct("vols_vehicules_1000").fillna(0.5)
        t["rang_potentiel"] = t["score_potentiel_citiz"].rank(ascending=False, method="min")
        t = t.sort_values("rang_potentiel")
        t.to_parquet(national("classement_epci.parquet"), index=False)
        t.round(4).to_csv(national("classement_epci.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
        geo = epci[["code_epci", "nom", "geometry"]].merge(t[["code_epci"]], on="code_epci")
        geo["geometry"] = geo.to_crs(2154).simplify(300).to_crs(4326) if len(geo) else geo.geometry
        geo.to_parquet(national("geo_epci.parquet"))
    save_stages("ranking")
    return t


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pd.set_option("display.width", 250)
    t = build_ranking()
    cols = ["nom", "population", "densite_vecue_hab_km2", "part_menages_sans_voiture", "autopartage_10k_hab",
            "stations_citiz", "n_options_moyen", "part_pop_sans_option", "vols_vehicules_1000", "score_potentiel_citiz"]
    print(t[cols].head(25).round(3).to_string(index=False))
