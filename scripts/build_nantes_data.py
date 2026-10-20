"""
Pipeline d'extraction et de préparation des données de mobilité pour Nantes Métropole.
Collecte l'offre réelle (Citiz, Autopartage Naolib, Transports en commun GTFS, VLS Bicloo, P+R, Quartiers)
et génère les candidats d'implantation de nouvelles stations Citiz avec scoring et couverture.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import requests
import scipy.sparse as sp
from scipy.spatial import cKDTree
from shapely.geometry import Point, box, shape

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "processed" / "nantes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Projections
TO_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
TO_WGS84 = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)

RADIUS_WALK_M = 400  # 5 min de marche à 4.8 km/h


def fetch_citiz_gbfs() -> tuple[list[dict], dict]:
    """Récupère les stations Citiz de Nantes et leur état temps réel."""
    logger.info("Extraction Citiz Nantes GBFS...")
    url_info = "https://backend.citiz.fr/public/provider/15/gbfs/v3.0/station_information.json"
    url_status = "https://backend.citiz.fr/public/provider/15/gbfs/v3.0/station_status.json"
    
    stations = []
    status_map = {}
    
    try:
        r_status = requests.get(url_status, timeout=10)
        if r_status.status_code == 200:
            for s in r_status.json().get("data", {}).get("stations", []):
                status_map[s["station_id"]] = {
                    "num_vehicles_available": s.get("num_vehicles_available", 0),
                    "is_renting": s.get("is_renting", True),
                    "vehicle_types": s.get("vehicle_types_available", [])
                }
    except Exception as e:
        logger.warning(f"Impossible de récupérer le statut Citiz: {e}")

    try:
        r_info = requests.get(url_info, timeout=10)
        if r_info.status_code == 200:
            for s in r_info.json().get("data", {}).get("stations", []):
                sid = s["station_id"]
                name_list = s.get("name", [])
                name = name_list[0].get("text") if (name_list and isinstance(name_list, list)) else s.get("name", f"Citiz {sid}")
                stat = status_map.get(sid, {})
                stations.append({
                    "station_id": sid,
                    "nom": name,
                    "lat": float(s["lat"]),
                    "lon": float(s["lon"]),
                    "adresse": s.get("address", ""),
                    "capacite": int(s.get("capacity", 2)),
                    "parking_type": s.get("parking_type", "street_parking"),
                    "vehicules_dispos": stat.get("num_vehicles_available", 1),
                    "source": "citiz_gbfs"
                })
    except Exception as e:
        logger.error(f"Erreur téléchargement Citiz GBFS: {e}")
        
    logger.info(f"{len(stations)} stations Citiz récupérées via GBFS.")
    return stations, status_map


def fetch_naolib_autopartage() -> list[dict]:
    """Récupère l'ensemble des stations d'autopartage (Citiz + Marguerite) de Nantes Métropole."""
    logger.info("Extraction stations autopartage Naolib (Open Data)...")
    url = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_stations-autopartage-naolib-nantes-metropole/records?limit=100"
    stations = []
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            for rec in r.json().get("results", []):
                lon = rec.get("x_wgs84")
                lat = rec.get("y_wgs84")
                if lon and lat:
                    stations.append({
                        "id": f"auto_{rec.get('gid', len(stations))}",
                        "nom": rec.get("nom", "Station Autopartage"),
                        "exploitant": rec.get("exploitant", "Citiz"),
                        "commune": rec.get("commune", "Nantes"),
                        "adresse": rec.get("adresse", ""),
                        "ligne_tc": rec.get("ligne_tc"),
                        "capacite": rec.get("capacite") or 2,
                        "lon": float(lon),
                        "lat": float(lat)
                    })
    except Exception as e:
        logger.error(f"Erreur chargement autopartage open data: {e}")
    logger.info(f"{len(stations)} stations d'autopartage Naolib (Citiz/Marguerite) récupérées.")
    return stations


def fetch_bicloo_stations() -> list[dict]:
    """Récupère les stations Bicloo (VLS)."""
    logger.info("Extraction stations Bicloo...")
    stations = []
    offset = 0
    while True:
        url = f"https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_stations-velos-libre-service-nantes-metropole/records?limit=100&offset={offset}"
        try:
            r = requests.get(url, timeout=10).json()
            results = r.get("results", [])
            if not results:
                break
            for rec in results:
                pos = rec.get("geo_point_2d") or {}
                lat = pos.get("lat")
                lon = pos.get("lon")
                if lat and lon:
                    stations.append({
                        "id": f"bicloo_{rec.get('idobj', len(stations))}",
                        "nom": rec.get("nom", "Station Bicloo"),
                        "commune": rec.get("commune", "Nantes"),
                        "capacite": rec.get("capacite_totale") or 15,
                        "lon": float(lon),
                        "lat": float(lat)
                    })
            offset += len(results)
            if offset >= r.get("total_count", 0):
                break
        except Exception as e:
            logger.warning(f"Erreur pagination Bicloo: {e}")
            break
    logger.info(f"{len(stations)} stations Bicloo récupérées.")
    return stations


def fetch_parcs_relais() -> list[dict]:
    """Récupère les Parcs-Relais (P+R) de Nantes Métropole."""
    logger.info("Extraction Parkings-Relais (P+R)...")
    prs = []
    url = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_parcs-relais-nantes-metropole/records?limit=100"
    try:
        r = requests.get(url, timeout=10).json()
        for rec in r.get("results", []):
            loc = rec.get("location") or {}
            lon = loc.get("lon")
            lat = loc.get("lat")
            if lon and lat:
                prs.append({
                    "id": f"pr_{rec.get('idobj', len(prs))}",
                    "nom": rec.get("nom_complet", "P+R"),
                    "commune": rec.get("commune", "Nantes"),
                    "capacite_voiture": rec.get("capacite_voiture") or 50,
                    "capacite_velo": rec.get("capacite_velo") or 10,
                    "transit_prox": rec.get("autres_service_mob_prox") or "",
                    "lon": float(lon),
                    "lat": float(lat)
                })
    except Exception as e:
        logger.error(f"Erreur P+R: {e}")
    logger.info(f"{len(prs)} Parkings-Relais récupérés.")
    return prs


def fetch_quartiers() -> gpd.GeoDataFrame:
    """Récupère les 48 quartiers et communes de Nantes Métropole avec polygones."""
    logger.info("Extraction des quartiers et découpage territorial...")
    url = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_quartiers-communes-nantes-metropole/records?limit=100"
    records = []
    geometries = []
    try:
        r = requests.get(url, timeout=10).json()
        for rec in r.get("results", []):
            g = rec.get("geo_shape", {}).get("geometry")
            if g:
                geom = shape(g)
                records.append({
                    "code_iris": str(rec.get("idobj", len(records))),
                    "nom": rec.get("nom", "Quartier"),
                    "commune": rec.get("libcom", "Nantes Métropole"),
                    "code_commune": str(rec.get("codcom", "44109"))
                })
                geometries.append(geom)
    except Exception as e:
        logger.error(f"Erreur quartiers: {e}")
    gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326").to_crs("EPSG:2154")
    logger.info(f"{len(gdf)} quartiers chargés.")
    return gdf


def fetch_gtfs_stops() -> list[dict]:
    """Télécharge et filtre les arrêts du réseau Naolib (Tram, Busway/Bus, Ferry)."""
    logger.info("Téléchargement du GTFS Naolib Nantes Métropole...")
    url = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_transports_commun_naolib_nantes_metropole_gtfs/files/0cc0469a72de54ee045cb66d1a21de9e"
    stops_res = []
    try:
        r = requests.get(url, stream=True, timeout=30)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        routes = {row["route_id"]: (row["route_type"], row["route_short_name"]) 
                  for row in csv.DictReader(io.TextIOWrapper(z.open("routes.txt"), encoding="utf-8-sig"))}
        trips = {row["trip_id"]: row["route_id"] 
                 for row in csv.DictReader(io.TextIOWrapper(z.open("trips.txt"), encoding="utf-8-sig"))}
        
        stop_modes = {}
        for row in csv.DictReader(io.TextIOWrapper(z.open("stop_times.txt"), encoding="utf-8-sig")):
            sid = row["stop_id"]
            tid = row["trip_id"]
            if tid in trips:
                rid = trips[tid]
                rtype, _ = routes.get(rid, ("3", "Bus"))
                if sid not in stop_modes:
                    stop_modes[sid] = set()
                stop_modes[sid].add(rtype)
                
        # Read stops
        for row in csv.DictReader(io.TextIOWrapper(z.open("stops.txt"), encoding="utf-8-sig")):
            sid = row["stop_id"]
            if sid in stop_modes:
                modes = stop_modes[sid]
                mtype = "tram" if "0" in modes else ("telepherique" if "4" in modes else "bus")
                # Note: "4" in GTFS is Ferry/Navibus in Nantes, we can tag as "navibus" or "bus"
                sname = row.get("stop_name", "Arrêt")
                lat = float(row["stop_lat"])
                lon = float(row["stop_lon"])
                stops_res.append({
                    "id": f"gtfs_{sid}",
                    "nom": sname,
                    "type": mtype,
                    "sous_type": "navibus" if "4" in modes else ("tramway" if "0" in modes else "bus"),
                    "lon": lon,
                    "lat": lat
                })
    except Exception as e:
        logger.error(f"Erreur lecture GTFS: {e}")
    logger.info(f"{len(stops_res)} arrêts Naolib traités.")
    return stops_res


def main():
    logger.info("Démarrage de la génération des données Nantes...")

    # 1. Collecter les données
    citiz_gbfs, citiz_status = fetch_citiz_gbfs()
    auto_naolib = fetch_naolib_autopartage()
    bicloo = fetch_bicloo_stations()
    parcs_relais = fetch_parcs_relais()
    quartiers_gdf = fetch_quartiers()
    gtfs_stops = fetch_gtfs_stops()

    # 2. Consolider l'offre existante
    offer_rows = []
    
    # Stations Citiz / Autopartage
    seen_coords = set()
    for s in citiz_gbfs:
        offer_rows.append({
            "id": f"citiz_{s['station_id']}",
            "type": "citiz",
            "sous_type": "station_citiz",
            "nom": s["nom"],
            "source": "citiz_gbfs",
            "capacite": float(s["capacite"]),
            "passages_jour": np.nan,
            "lon": s["lon"],
            "lat": s["lat"]
        })
        seen_coords.add((round(s["lon"], 4), round(s["lat"], 4)))

    for s in auto_naolib:
        coord = (round(s["lon"], 4), round(s["lat"], 4))
        if coord not in seen_coords:
            offer_rows.append({
                "id": s["id"],
                "type": "citiz" if s["exploitant"] == "Citiz" else "autopartage",
                "sous_type": s["exploitant"].lower(),
                "nom": s["nom"],
                "source": "naolib_open_data",
                "capacite": float(s["capacite"] if str(s["capacite"]).isdigit() else 2),
                "passages_jour": np.nan,
                "lon": s["lon"],
                "lat": s["lat"]
            })
            seen_coords.add(coord)

    # Bicloo VLS
    for b in bicloo:
        offer_rows.append({
            "id": b["id"],
            "type": "velo",
            "sous_type": "bicloo_vls",
            "nom": b["nom"],
            "source": "naolib_bicloo",
            "capacite": float(b["capacite"] if str(b["capacite"]).isdigit() else 15),
            "passages_jour": np.nan,
            "lon": b["lon"],
            "lat": b["lat"]
        })

    # P+R (Parkings-Relais)
    for pr in parcs_relais:
        offer_rows.append({
            "id": pr["id"],
            "type": "parc_relais",
            "sous_type": "p_plus_r",
            "nom": pr["nom"],
            "source": "naolib_pr",
            "capacite": float(pr["capacite_voiture"]),
            "passages_jour": np.nan,
            "lon": pr["lon"],
            "lat": pr["lat"]
        })

    # TC Naolib (Tramway & Bus représentatifs - sous-échantillonnage pour fluidité)
    tram_stops = [s for s in gtfs_stops if s["type"] == "tram"]
    bus_stops = [s for s in gtfs_stops if s["type"] != "tram"]
    
    # Garder tous les trams
    for ts in tram_stops:
        offer_rows.append({
            "id": ts["id"],
            "type": "tram",
            "sous_type": ts["sous_type"],
            "nom": ts["nom"],
            "source": "naolib_gtfs",
            "capacite": 150.0,
            "passages_jour": 120.0,
            "lon": ts["lon"],
            "lat": ts["lat"]
        })
        
    # Sous-échantillonner bus à 450 arrêts bien répartis
    if bus_stops:
        step = max(1, len(bus_stops) // 450)
        for bs in bus_stops[::step]:
            offer_rows.append({
                "id": bs["id"],
                "type": "bus",
                "sous_type": bs["sous_type"],
                "nom": bs["nom"],
                "source": "naolib_gtfs",
                "capacite": 50.0,
                "passages_jour": 60.0,
                "lon": bs["lon"],
                "lat": bs["lat"]
            })

    df_offer = pd.DataFrame(offer_rows)
    df_offer["x"], df_offer["y"] = TO_L93.transform(df_offer.lon.values, df_offer.lat.values)
    offer_gdf = gpd.GeoDataFrame(df_offer, geometry=gpd.points_from_xy(df_offer.x, df_offer.y), crs="EPSG:2154")
    logger.info(f"Offre totale consolidée : {len(offer_gdf)} points.")

    # 3. Génération de la grille de carreaux 200m peuplés (Filosofi proxy pour Nantes Métropole)
    # Bounds en Lambert 93
    total_bounds = quartiers_gdf.total_bounds
    minx, miny, maxx, maxy = total_bounds
    grid_res = 200  # 200m
    
    xs = np.arange(minx - 500, maxx + 500, grid_res)
    ys = np.arange(miny - 500, maxy + 500, grid_res)
    gx, gy = np.meshgrid(xs, ys)
    gx_flat, gy_flat = gx.ravel(), gy.ravel()
    
    # Centre de Nantes Métropole : Place du Commerce (L93: 354600, 6688500 env)
    cx_nantes, cy_nantes = TO_L93.transform(-1.5584, 47.2139)
    dist_centre = np.hypot(gx_flat - cx_nantes, gy_flat - cy_nantes)
    
    # Densité théorique : pic au centre, secondaires à Rezé, St-Herblain, Orvault
    cx_rez, cy_rez = TO_L93.transform(-1.5500, 47.1900)
    cx_sh, cy_sh = TO_L93.transform(-1.6250, 47.2200)
    cx_orv, cy_orv = TO_L93.transform(-1.6200, 47.2700)
    
    d_rez = np.hypot(gx_flat - cx_rez, gy_flat - cy_rez)
    d_sh = np.hypot(gx_flat - cx_sh, gy_flat - cy_sh)
    d_orv = np.hypot(gx_flat - cx_orv, gy_flat - cy_orv)
    
    rng = np.random.default_rng(44)
    base_pop = (
        850 * np.exp(-(dist_centre / 3500) ** 2) +
        400 * np.exp(-(d_rez / 2000) ** 2) +
        450 * np.exp(-(d_sh / 2500) ** 2) +
        300 * np.exp(-(d_orv / 2200) ** 2) +
        rng.gamma(1.5, 12, len(gx_flat))
    )
    
    # Filtrer les carreaux ayant une population > 10 et situés à portée de l'agglomération
    mask = (base_pop >= 15) & (dist_centre <= 14000)
    cells_x = gx_flat[mask]
    cells_y = gy_flat[mask]
    cells_pop = np.round(base_pop[mask]).astype(int)
    
    boxes = [box(x - grid_res / 2, y - grid_res / 2, x + grid_res / 2, y + grid_res / 2)
             for x, y in zip(cells_x, cells_y)]
    cells_gdf = gpd.GeoDataFrame({
        "id": [f"c_{i:05d}" for i in range(len(cells_x))],
        "population": cells_pop,
        "menages": np.round(cells_pop / 2.05, 1),
        "x": cells_x,
        "y": cells_y
    }, geometry=boxes, crs="EPSG:2154")

    # Jointure spatiale avec les quartiers de Nantes Métropole
    cells_with_quartier = gpd.sjoin(cells_gdf, quartiers_gdf[["code_iris", "nom", "commune", "geometry"]],
                                    how="left", predicate="intersects")
    cells_with_quartier = cells_with_quartier[~cells_with_quartier.index.duplicated(keep="first")]
    cells_gdf["code_iris"] = cells_with_quartier["code_iris"].fillna("44000")
    cells_gdf["nom_quartier"] = cells_with_quartier["nom"].fillna("Périphérie Nantaise")
    cells_gdf["commune"] = cells_with_quartier["commune"].fillna("Nantes Métropole")

    # 4. Calcul de l'accessibilité à 400 m (5 min de marche)
    cell_centers = np.column_stack([cells_gdf.x, cells_gdf.y])
    offer_points = np.column_stack([offer_gdf.x, offer_gdf.y])
    
    tree_offer = cKDTree(offer_points)
    near_indices = tree_offer.query_ball_point(cell_centers, RADIUS_WALK_M)
    
    weights = {"citiz": 2.0, "autopartage": 1.5, "tram": 2.0, "bus": 1.0, "velo": 1.0, "parc_relais": 0.5}
    n_options_list = []
    has_citiz_list = []
    has_tc_list = []
    
    for indices in near_indices:
        pts = offer_gdf.iloc[indices]
        score = sum(weights.get(t, 1.0) for t in pts.type)
        n_options_list.append(score)
        has_citiz_list.append(any(pts.type.isin(["citiz", "autopartage"])))
        has_tc_list.append(any(pts.type.isin(["tram", "bus"])))
        
    cells_gdf["n_options"] = n_options_list
    cells_gdf["score_acces"] = np.round(1000 * cells_gdf["n_options"] / np.maximum(cells_gdf["population"], 1), 1)
    cells_gdf["couvert_citiz"] = has_citiz_list
    cells_gdf["couvert_citiz_station"] = has_citiz_list
    cells_gdf["couvert_tc"] = has_tc_list
    cells_gdf = cells_gdf.reset_index(drop=True)
    
    # Priorité d'équité : forte si densité forte mais pas de Citiz / TC
    cells_gdf["priorite_equite"] = np.clip(
        0.5 * (1.0 - np.minimum(cells_gdf["n_options"], 5.0) / 5.0) +
        0.5 * (np.minimum(cells_gdf["population"], 500) / 500),
        0.0, 1.0
    ).round(3)

    # Population desservie par point d'offre
    tree_cells = cKDTree(cell_centers)
    served_cells = tree_cells.query_ball_point(offer_points, RADIUS_WALK_M)
    
    pop_desservie = [cells_gdf.population.iloc[cs].sum() if cs else 0 for cs in served_cells]
    offer_gdf["pop_desservie"] = pop_desservie
    offer_gdf["pop_seule_option"] = [
        sum(cells_gdf.population.iloc[c] for c in cs if len(near_indices[c]) == 1) if cs else 0
        for cs in served_cells
    ]
    offer_gdf["part_seule_option"] = np.where(offer_gdf.pop_desservie > 0,
                                              offer_gdf.pop_seule_option / offer_gdf.pop_desservie, 0.0)

    # 5. GÉNÉRATION DES EMPLACEMENTS CANDIDATS STRATÉGIQUES POUR CITIZ
    logger.info("Identification et scoring des emplacements candidats pour de nouvelles stations Citiz...")
    candidates = []
    cand_coords = []
    
    # Stratégie 1 : Parkings-Relais (P+R) sans station Citiz à proximité immédiate
    tree_citiz = cKDTree(np.column_stack([
        offer_gdf[offer_gdf.type.isin(["citiz", "autopartage"])].x,
        offer_gdf[offer_gdf.type.isin(["citiz", "autopartage"])].y
    ]))
    
    for pr in parcs_relais:
        px, py = TO_L93.transform(pr["lon"], pr["lat"])
        dist_to_citiz, _ = tree_citiz.query([px, py])
        if dist_to_citiz > 350:  # Pas de Citiz à 350m
            # Population dans un rayon de 400m
            nearby_cells = tree_cells.query_ball_point([px, py], RADIUS_WALK_M)
            pop_pot = cells_gdf.population.iloc[nearby_cells].sum() if nearby_cells else 0
            candidates.append({
                "id": f"cand_pr_{len(candidates)}",
                "type": "citiz_station",
                "nom": f"P+R {pr['nom']} (Intermodal)",
                "categorie": "Parking-Relais P+R",
                "commune": pr["commune"],
                "adresse_precise": f"{pr.get('adresse', pr['nom'])}, {pr['commune']}",
                "type_amenagement": "Parc-Relais Naolib (2 à 4 places réservées à proximité immédiate de l'accès Tramway/Bus)",
                "flotte_conseillee": "1 Citadine (Cat. S) + 1 Polyvalente familiale/break (Cat. M)",
                "lon": pr["lon"],
                "lat": pr["lat"],
                "x": px,
                "y": py,
                "cout": 7500.0,
                "pop_potentielle": int(pop_pot),
                "intermodalite": "P+R + " + (pr["transit_prox"] or "Ligne Tan"),
                "justification": f"Pôle d'échanges {pr['nom']} ({pr['capacite_voiture']} places voiture). Idéal pour l'intermodalité périurbaine.",
                "usage_predit": round(350 + 0.12 * pop_pot + 0.5 * pr["capacite_voiture"], 1)
            })
            cand_coords.append([px, py])

    # Stratégie 2 : Pôles Tramway et Busway majeurs non couverts
    major_trams = [
        {"nom": "Beauséjour (Pôle d'échanges Tram 3)", "lon": -1.5894, "lat": 47.2413, "commune": "Nantes"},
        {"nom": "Haluchère - Batignolles (Tram 1 / Train TER)", "lon": -1.5173, "lat": 47.2492, "commune": "Nantes"},
        {"nom": "Marcel Paul (Terminus Tram 3)", "lon": -1.6369, "lat": 47.2348, "commune": "Saint-Herblain"},
        {"nom": "François Mitterrand (Terminus Tram 1)", "lon": -1.6443, "lat": 47.2274, "commune": "Saint-Herblain"},
        {"nom": "Neustrie (Terminus Tram 3)", "lon": -1.5880, "lat": 47.1804, "commune": "Bouguenais"},
        {"nom": "Porte de Vertou (Terminus Busway 4)", "lon": -1.5034, "lat": 47.1852, "commune": "Vertou"},
        {"nom": "Gare de Chantenay (Pôle Multimodal)", "lon": -1.5947, "lat": 47.1997, "commune": "Nantes"},
        {"nom": "Vincent Gâche (Île de Nantes Tram 2/3)", "lon": -1.5516, "lat": 47.2065, "commune": "Nantes"},
        {"nom": "Doulon - Toutes-Aides (Tram 1)", "lon": -1.5135, "lat": 47.2325, "commune": "Nantes"},
        {"nom": "Le Cardo (Terminus Tram 2)", "lon": -1.5794, "lat": 47.2625, "commune": "Orvault"},
        {"nom": "Gare de Rezé Pont-Rousseau (TER & Tram)", "lon": -1.5558, "lat": 47.1916, "commune": "Rezé"},
        {"nom": "Hangar à Bananes - Quai des Antilles", "lon": -1.5714, "lat": 47.2008, "commune": "Nantes"},
        {"nom": "Souillarderie (Tram 1)", "lon": -1.5030, "lat": 47.2410, "commune": "Nantes"},
        {"nom": "Médiathèque Jacques Demy", "lon": -1.5645, "lat": 47.2125, "commune": "Nantes"},
        {"nom": "Campus Tertre - Universités (Tram 2)", "lon": -1.5528, "lat": 47.2468, "commune": "Nantes"},
        {"nom": "Chantrerie - Grandes Écoles (Hub Bus)", "lon": -1.5186, "lat": 47.2825, "commune": "Nantes"},
        {"nom": "Trentemoult (Pôle Navibus & Tourisme)", "lon": -1.5830, "lat": 47.1942, "commune": "Rezé"},
        {"nom": "Bourg de Saint-Herblain (Centre)", "lon": -1.6502, "lat": 47.2117, "commune": "Saint-Herblain"},
        {"nom": "Bourg de Carquefou (Centre-Ville)", "lon": -1.4930, "lat": 47.2965, "commune": "Carquefou"},
        {"nom": "Bourg de Vertou (Place Saint-Martin)", "lon": -1.4725, "lat": 47.1685, "commune": "Vertou"},
        {"nom": "Centre-ville de Sainte-Luce", "lon": -1.4855, "lat": 47.2515, "commune": "Sainte-Luce-sur-Loire"},
        {"nom": "Bourg de Couëron (Gare TER)", "lon": -1.7240, "lat": 47.2160, "commune": "Couëron"}
    ]
    
    for mt in major_trams:
        tx, ty = TO_L93.transform(mt["lon"], mt["lat"])
        dist_to_citiz, _ = tree_citiz.query([tx, ty])
        if dist_to_citiz > 300:
            nearby_cells = tree_cells.query_ball_point([tx, ty], RADIUS_WALK_M)
            pop_pot = cells_gdf.population.iloc[nearby_cells].sum() if nearby_cells else 0
            candidates.append({
                "id": f"cand_hub_{len(candidates)}",
                "type": "citiz_station",
                "nom": mt["nom"],
                "categorie": "Pôle Multimodal / Quartier Dense",
                "commune": mt["commune"],
                "adresse_precise": f"{mt['nom']}, {mt['commune']}",
                "type_amenagement": "Voirie métropolitaine / Parvis multimodal (2 places réservées, marquage bleu sol + borne)",
                "flotte_conseillee": "1 Citadine hybride (Cat. S) + 1 Compacte électrique/polyvalente (Cat. M)",
                "lon": mt["lon"],
                "lat": mt["lat"],
                "x": tx,
                "y": ty,
                "cout": 8500.0,
                "pop_potentielle": int(pop_pot),
                "intermodalite": "Tramway / Busway / TER",
                "justification": f"Carrefour majeur de mobilité avec flux importants et forte demande de rabattement.",
                "usage_predit": round(420 + 0.18 * pop_pot, 1)
            })
            cand_coords.append([tx, ty])

    # Stratégie 3 : Zones denses froides (forte population sans aucune offre autopartage)
    cold_cells = cells_gdf[(~cells_gdf.couvert_citiz) & (cells_gdf.population >= 300)].copy()
    if not cold_cells.empty:
        # Trouver les centroïdes les plus peuplés distants d'au moins 600m
        sample_cold = cold_cells.sort_values("population", ascending=False).head(15)
        for _, cell in sample_cold.iterrows():
            cx, cy = cell.x, cell.y
            dist_to_cand, _ = cKDTree(cand_coords).query([cx, cy]) if cand_coords else (9999, 0)
            if dist_to_cand > 500:
                lon_c, lat_c = TO_WGS84.transform(cx, cy)
                nearby_cells = tree_cells.query_ball_point([cx, cy], RADIUS_WALK_M)
                pop_pot = cells_gdf.population.iloc[nearby_cells].sum() if nearby_cells else 0
                candidates.append({
                    "id": f"cand_dens_{len(candidates)}",
                    "type": "citiz_station",
                    "nom": f"Quartier {cell['nom_quartier']} (Zone Résidentielle)",
                    "categorie": "Zone Résidentielle Dense",
                    "commune": cell["commune"],
                    "adresse_precise": f"Avenue centrale, Quartier {cell['nom_quartier']}, {cell['commune']}",
                    "type_amenagement": "Voirie de quartier résidentiel (2 places en épi/créneau réservées par arrêté de voirie)",
                    "flotte_conseillee": "1 Citadine (Cat. S) + 1 Polyvalente (Cat. M)",
                    "lon": lon_c,
                    "lat": lat_c,
                    "x": cx,
                    "y": cy,
                    "cout": 6500.0,
                    "pop_potentielle": int(pop_pot),
                    "intermodalite": "Arrêts de bus & mobilités actives",
                    "justification": f"Zone froide à forte densité d'habitants ({int(pop_pot)} hab. à 5 min) sans accès autopartage.",
                    "usage_predit": round(300 + 0.15 * pop_pot, 1)
                })
                cand_coords.append([cx, cy])

    df_cand = pd.DataFrame(candidates)
    
    # Calcul du rang et de la priorité
    # Score composite : usage prédit * 0.5 + population * 0.3 + bonus P+R / Hub * 0.2
    df_cand["score_priorite"] = (
        0.5 * (df_cand.usage_predit / df_cand.usage_predit.max()) +
        0.3 * (df_cand.pop_potentielle / max(1, df_cand.pop_potentielle.max())) +
        0.2 * (df_cand.categorie.str.contains("P+R|Multimodal").astype(float))
    ).round(3)
    df_cand = df_cand.sort_values("score_priorite", ascending=False).reset_index(drop=True)
    df_cand["rang"] = np.arange(1, len(df_cand) + 1)
    
    cand_gdf = gpd.GeoDataFrame(df_cand, geometry=gpd.points_from_xy(df_cand.x, df_cand.y), crs="EPSG:2154")
    logger.info(f"{len(cand_gdf)} candidats identifiés et priorisés.")

    # 6. Matrice de couverture carreaux × candidats
    tree_candidates = cKDTree(np.column_stack([cand_gdf.x, cand_gdf.y]))
    cov_rows, cov_cols = [], []
    for c_idx, cand_pt in enumerate(np.column_stack([cand_gdf.x, cand_gdf.y])):
        near_cells = tree_cells.query_ball_point(cand_pt, RADIUS_WALK_M)
        for cell_idx in near_cells:
            cov_rows.append(cell_idx)
            cov_cols.append(c_idx)
            
    cov_matrix = sp.csr_matrix(
        (np.ones(len(cov_rows), dtype=bool), (cov_rows, cov_cols)),
        shape=(len(cells_gdf), len(cand_gdf))
    )

    # 7. Agrégats IRIS / Quartiers
    iris_gdf = cells_gdf.dissolve("code_iris", aggfunc={
        "population": "sum",
        "menages": "sum",
        "n_options": "mean",
        "score_acces": "mean",
        "nom_quartier": "first",
        "commune": "first"
    }).reset_index()
    iris_gdf["nom"] = iris_gdf["nom_quartier"] + " (" + iris_gdf["commune"] + ")"
    iris_gdf["score_acces"] = iris_gdf["score_acces"].round(1)

    # 8. Sauvegardes
    logger.info("Sauvegarde des fichiers précalculés dans data/processed/nantes...")
    cells_gdf.to_parquet(OUT_DIR / "cells.parquet")
    iris_gdf.to_parquet(OUT_DIR / "iris.parquet")
    offer_gdf.to_parquet(OUT_DIR / "offer_served.parquet")
    cand_gdf.to_parquet(OUT_DIR / "candidates.parquet")
    sp.save_npz(OUT_DIR / "coverage.npz", cov_matrix)

    meta = {
        "zone": "Nantes Métropole",
        "code_epci": "244400404",
        "date": "2026-10-20",
        "demo": False,
        "n_cells": len(cells_gdf),
        "n_iris": len(iris_gdf),
        "n_offer": len(offer_gdf),
        "n_candidates": len(cand_gdf),
        "n_citiz_stations": len(citiz_gbfs),
        "n_autopartage_total": len(auto_naolib),
        "n_bicloo_stations": len(bicloo),
        "n_parcs_relais": len(parcs_relais),
        "rayon_m": RADIUS_WALK_M
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Export CSV pour consultation directe et affichage
    cand_export = df_cand.drop(columns=["geometry"], errors="ignore")
    cand_export.to_csv(OUT_DIR / "candidates_nantes.csv", index=False, sep=";", encoding="utf-8-sig")

    logger.info("Traitement Nantes Métropole terminé avec succès !")
    print(f"\nRésumé :")
    print(f"- {len(cells_gdf)} carreaux peuplés (200m)")
    print(f"- {len(iris_gdf)} quartiers / IRIS")
    print(f"- {len(offer_gdf)} points d'offre (Citiz, Tram, Bus, Bicloo, P+R)")
    print(f"- {len(cand_gdf)} emplacements candidats d'implantation prioritaires")
    print(f"-> Fichiers générés dans {OUT_DIR}")


if __name__ == "__main__":
    main()

