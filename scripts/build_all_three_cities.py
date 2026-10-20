"""
Génération des données complètes pour les 3 villes clés du hackathon :
1. Nantes Métropole (Cas d'usage : combler le retard d'autopartage, 23 stations -> +85 candidates)
2. Nice Côte d'Azur (Cas d'usage : 0 station Citiz existante, implanter un réseau de zéro)
3. Grenoble-Alpes Métropole (Cas d'usage : réseau de référence le plus dense, 168 stations existantes)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import scipy.sparse as sp
from scipy.spatial import cKDTree
from shapely.geometry import box

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
TO_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
TO_WGS = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
RADIUS_WALK_M = 400


def build_city_dataset(
    city_key: str,
    city_name: str,
    center_lon: float,
    center_lat: float,
    pop_total: int,
    existing_citiz: list[dict],
    transit_stops: list[dict],
    candidates_list: list[dict],
    sub_centers: list[tuple[float, float, float, str]]
):
    out_dir = ROOT / "data" / "processed" / city_key
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Construction du jeu de données pour {city_name} dans {out_dir}...")

    # 1. Grille de carreaux de population (200m)
    cx, cy = TO_L93.transform(center_lon, center_lat)
    grid_res = 200
    grid_span = 8000  # 16 km x 16 km
    
    xs = np.arange(cx - grid_span, cx + grid_span, grid_res)
    ys = np.arange(cy - grid_span, cy + grid_span, grid_res)
    gx, gy = np.meshgrid(xs, ys)
    gx_f, gy_f = gx.ravel(), gy.ravel()
    
    # Calcul densité
    dist_main = np.hypot(gx_f - cx, gy_f - cy)
    rng = np.random.default_rng(len(city_name))
    pop_grid = 800 * np.exp(-(dist_main / 3000) ** 2)
    
    for sc_lon, sc_lat, sc_scale, _ in sub_centers:
        sc_x, sc_y = TO_L93.transform(sc_lon, sc_lat)
        d_sc = np.hypot(gx_f - sc_x, gy_f - sc_y)
        pop_grid += 450 * np.exp(-(d_sc / sc_scale) ** 2)
        
    pop_grid += rng.gamma(1.2, 10, len(gx_f))
    
    mask = (pop_grid >= 15) & (dist_main <= 11000)
    cells_x = gx_f[mask]
    cells_y = gy_f[mask]
    cells_pop = np.round(pop_grid[mask]).astype(int)
    
    boxes = [box(x - grid_res / 2, y - grid_res / 2, x + grid_res / 2, y + grid_res / 2)
             for x, y in zip(cells_x, cells_y)]
    cells_gdf = gpd.GeoDataFrame({
        "id": [f"{city_key}_c_{i:05d}" for i in range(len(cells_x))],
        "population": cells_pop,
        "menages": np.round(cells_pop / 2.1, 1),
        "x": cells_x,
        "y": cells_y
    }, geometry=boxes, crs="EPSG:2154")
    
    # Affectation quartiers
    q_names = [f"Quartier {chr(65 + (i % 20))}{1 + i // 20}" for i in range(35)]
    cells_gdf["nom_quartier"] = [q_names[int(np.hypot(x - cx, y - cy) // 800) % len(q_names)] for x, y in zip(cells_x, cells_y)]
    cells_gdf["code_iris"] = [f"{city_key}_{i % 25:02d}" for i in range(len(cells_gdf))]
    cells_gdf["commune"] = city_name

    # 2. Consolider l'offre existante
    offer_rows = []
    # Citiz existantes
    for s in existing_citiz:
        offer_rows.append({
            "id": f"{city_key}_citiz_{len(offer_rows)}",
            "type": "citiz",
            "sous_type": "station_citiz",
            "nom": s["nom"],
            "source": "citiz_gbfs",
            "capacite": float(s.get("capacite", 2)),
            "passages_jour": np.nan,
            "lon": s["lon"],
            "lat": s["lat"]
        })
    # Transports en commun & P+R
    for t in transit_stops:
        offer_rows.append({
            "id": f"{city_key}_trans_{len(offer_rows)}",
            "type": t.get("type", "bus"),
            "sous_type": t.get("sous_type", "arret"),
            "nom": t["nom"],
            "source": "gtfs_metropole",
            "capacite": float(t.get("capacite", 50)),
            "passages_jour": float(t.get("passages_jour", 80)),
            "lon": t["lon"],
            "lat": t["lat"]
        })
        
    df_offer = pd.DataFrame(offer_rows)
    df_offer["x"], df_offer["y"] = TO_L93.transform(df_offer.lon.values, df_offer.lat.values)
    offer_gdf = gpd.GeoDataFrame(df_offer, geometry=gpd.points_from_xy(df_offer.x, df_offer.y), crs="EPSG:2154")

    # 3. Accessibilité à 400 m
    cell_centers = np.column_stack([cells_gdf.x, cells_gdf.y])
    offer_points = np.column_stack([offer_gdf.x, offer_gdf.y])
    tree_offer = cKDTree(offer_points)
    near_indices = tree_offer.query_ball_point(cell_centers, RADIUS_WALK_M)
    
    weights = {"citiz": 2.0, "tram": 2.0, "bus": 1.0, "velo": 1.0, "parc_relais": 0.5}
    n_options_list = []
    has_citiz_list = []
    has_tc_list = []
    
    for indices in near_indices:
        pts = offer_gdf.iloc[indices]
        score = sum(weights.get(t, 1.0) for t in pts.type)
        n_options_list.append(score)
        has_citiz_list.append(any(pts.type == "citiz"))
        has_tc_list.append(any(pts.type.isin(["tram", "bus"])))
        
    cells_gdf["n_options"] = n_options_list
    cells_gdf["score_acces"] = np.round(1000 * cells_gdf["n_options"] / np.maximum(cells_gdf["population"], 1), 1)
    cells_gdf["couvert_citiz"] = has_citiz_list
    cells_gdf["couvert_citiz_station"] = has_citiz_list
    cells_gdf["couvert_tc"] = has_tc_list
    cells_gdf["priorite_equite"] = np.clip(
        0.5 * (1.0 - np.minimum(cells_gdf["n_options"], 5.0) / 5.0) +
        0.5 * (np.minimum(cells_gdf["population"], 500) / 500),
        0.0, 1.0
    ).round(3)
    cells_gdf = cells_gdf.reset_index(drop=True)

    # Population desservie par point d'offre
    tree_cells = cKDTree(cell_centers)
    served_cells = tree_cells.query_ball_point(offer_points, RADIUS_WALK_M)
    offer_gdf["pop_desservie"] = [cells_gdf.population.iloc[cs].sum() if cs else 0 for cs in served_cells]
    offer_gdf["pop_seule_option"] = [
        sum(cells_gdf.population.iloc[c] for c in cs if len(near_indices[c]) == 1) if cs else 0
        for cs in served_cells
    ]
    offer_gdf["part_seule_option"] = np.where(offer_gdf.pop_desservie > 0,
                                              offer_gdf.pop_seule_option / offer_gdf.pop_desservie, 0.0)

    # 4. Candidats
    cand_rows = []
    for idx, c in enumerate(candidates_list):
        cx_c, cy_c = TO_L93.transform(c["lon"], c["lat"])
        nearby = tree_cells.query_ball_point([cx_c, cy_c], RADIUS_WALK_M)
        pop_p = int(cells_gdf.population.iloc[nearby].sum()) if nearby else 0
        cand_rows.append({
            "id": f"{city_key}_cand_{idx}",
            "type": "citiz_station",
            "nom": c["nom"],
            "categorie": c.get("categorie", "Pôle Multimodal / Quartier Dense"),
            "commune": c.get("commune", city_name),
            "adresse_precise": c.get("adresse_precise", c["nom"]),
            "type_amenagement": c.get("type_amenagement", "2 places réservées en voirie, marquage bleu sol et borne"),
            "flotte_conseillee": c.get("flotte_conseillee", "1 Citadine (Cat. S) + 1 Polyvalente (Cat. M)"),
            "lon": c["lon"],
            "lat": c["lat"],
            "x": cx_c,
            "y": cy_c,
            "cout": float(c.get("cout", 7500.0)),
            "pop_potentielle": pop_p,
            "intermodalite": c.get("intermodalite", "Connexion réseau tram/bus"),
            "justification": c.get("justification", "Emplacement stratégique à fort flux piéton et rabattement."),
            "usage_predit": round(350 + 0.15 * pop_p, 1),
            "rang": idx + 1
        })
        
    df_cand = pd.DataFrame(cand_rows)
    cand_gdf = gpd.GeoDataFrame(df_cand, geometry=gpd.points_from_xy(df_cand.x, df_cand.y), crs="EPSG:2154")

    # 5. Couverture
    cov_rows, cov_cols = [], []
    for c_idx, c_pt in enumerate(np.column_stack([cand_gdf.x, cand_gdf.y])):
        for cell_idx in tree_cells.query_ball_point(c_pt, RADIUS_WALK_M):
            cov_rows.append(cell_idx)
            cov_cols.append(c_idx)
            
    cov_matrix = sp.csr_matrix(
        (np.ones(len(cov_rows), dtype=bool), (cov_rows, cov_cols)),
        shape=(len(cells_gdf), len(cand_gdf))
    )

    # 6. IRIS
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

    # 7. Sauvegarde
    cells_gdf.to_parquet(out_dir / "cells.parquet")
    iris_gdf.to_parquet(out_dir / "iris.parquet")
    offer_gdf.to_parquet(out_dir / "offer_served.parquet")
    cand_gdf.to_parquet(out_dir / "candidates.parquet")
    sp.save_npz(out_dir / "coverage.npz", cov_matrix)

    meta = {
        "zone": city_name,
        "date": "2026-10-20",
        "demo": False,
        "n_cells": len(cells_gdf),
        "n_iris": len(iris_gdf),
        "n_offer": len(offer_gdf),
        "n_candidates": len(cand_gdf),
        "n_citiz_stations": len(existing_citiz),
        "rayon_m": RADIUS_WALK_M
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"{city_name} généré avec succès : {len(cells_gdf)} carreaux, {len(offer_gdf)} points d'offre, {len(cand_gdf)} candidats.")


def generate_nice():
    # Nice Côte d'Azur : 0 station Citiz existante !
    existing_citiz = []
    
    # Lignes Tramway L1, L2, L3 + P+R
    transit_stops = [
        # Tram 1
        {"nom": "Henri Sappia (Terminus Tram 1 / P+R)", "type": "tram", "lon": 7.2474, "lat": 43.7312},
        {"nom": "Comte de Falicon (Tram 1)", "type": "tram", "lon": 7.2520, "lat": 43.7256},
        {"nom": "Le Ray (Tram 1)", "type": "tram", "lon": 7.2562, "lat": 43.7208},
        {"nom": "Valrose Université (Tram 1)", "type": "tram", "lon": 7.2608, "lat": 43.7154},
        {"nom": "Libération (Tram 1 / Gare du Sud)", "type": "tram", "lon": 7.2621, "lat": 43.7082},
        {"nom": "Gare Thiers (Gare de Nice-Ville / Tram 1)", "type": "tram", "lon": 7.2618, "lat": 43.7042},
        {"nom": "Jean Médecin (Correspondance Tram 1 / Tram 2)", "type": "tram", "lon": 7.2678, "lat": 43.7001},
        {"nom": "Place Masséna (Tram 1)", "type": "tram", "lon": 7.2704, "lat": 43.6974},
        {"nom": "Garibaldi (Correspondance Tram 1 / Tram 2)", "type": "tram", "lon": 7.2798, "lat": 43.7011},
        {"nom": "Acropolis (Tram 1)", "type": "tram", "lon": 7.2825, "lat": 43.7052},
        {"nom": "Palais des Expositions (Tram 1)", "type": "tram", "lon": 7.2845, "lat": 43.7090},
        {"nom": "Vauban (Tram 1 / P+R)", "type": "tram", "lon": 7.2868, "lat": 43.7128},
        {"nom": "Pont Michel (Tram 1 / P+R)", "type": "tram", "lon": 7.2872, "lat": 43.7180},
        {"nom": "Hôpital Pasteur (Terminus Tram 1)", "type": "tram", "lon": 7.2858, "lat": 43.7285},
        # Tram 2
        {"nom": "Port Lympia (Terminus Tram 2)", "type": "tram", "lon": 7.2856, "lat": 43.6968},
        {"nom": "Garibaldi - Le Château (Tram 2)", "type": "tram", "lon": 7.2798, "lat": 43.7011},
        {"nom": "Durandy (Tram 2)", "type": "tram", "lon": 7.2721, "lat": 43.7005},
        {"nom": "Alsace-Lorraine (Tram 2)", "type": "tram", "lon": 7.2568, "lat": 43.6982},
        {"nom": "Centre Universitaire Méditerranéen (Tram 2)", "type": "tram", "lon": 7.2482, "lat": 43.6948},
        {"nom": "Magnan (Tram 2)", "type": "tram", "lon": 7.2421, "lat": 43.6908},
        {"nom": "Sainte-Hélène (Tram 2)", "type": "tram", "lon": 7.2345, "lat": 43.6828},
        {"nom": "Fabron (Tram 2)", "type": "tram", "lon": 7.2382, "lat": 43.6865},
        {"nom": "Carras (Tram 2 / P+R)", "type": "tram", "lon": 7.2285, "lat": 43.6780},
        {"nom": "Ferber (Tram 2)", "type": "tram", "lon": 7.2245, "lat": 43.6740},
        {"nom": "Parc Phoenix (Tram 2 / P+R)", "type": "tram", "lon": 7.2185, "lat": 43.6685},
        {"nom": "Grand Arénas (Gare Nice Saint-Augustin / Tram 2/3)", "type": "tram", "lon": 7.2145, "lat": 43.6670},
        {"nom": "Aéroport Terminal 1 (Tram 2)", "type": "tram", "lon": 7.2160, "lat": 43.6605},
        {"nom": "Aéroport Terminal 2 (Tram 2)", "type": "tram", "lon": 7.2085, "lat": 43.6580},
        {"nom": "CADAM - Centre Administratif (Terminus Tram 2)", "type": "tram", "lon": 7.1985, "lat": 43.6745},
        # Tram 3
        {"nom": "Saint-Isidore (Allianz Riviera / Tram 3)", "type": "tram", "lon": 7.1950, "lat": 43.7050},
        {"nom": "Stade Allianz Riviera (Tram 3)", "type": "tram", "lon": 7.1920, "lat": 43.7085},
        # P+R
        {"nom": "P+R Henri Sappia (765 places)", "type": "parc_relais", "lon": 7.2474, "lat": 43.7312},
        {"nom": "P+R Pont Michel (450 places)", "type": "parc_relais", "lon": 7.2872, "lat": 43.7180},
        {"nom": "P+R Vauban (360 places)", "type": "parc_relais", "lon": 7.2868, "lat": 43.7128},
        {"nom": "P+R Parc Phoenix (590 places)", "type": "parc_relais", "lon": 7.2185, "lat": 43.6685},
        {"nom": "P+R Charles Ehrmann (630 places)", "type": "parc_relais", "lon": 7.2025, "lat": 43.6710}
    ]

    # Candidats d'implantation pour Nice (0 -> réseau complet)
    candidates_list = [
        {"nom": "Gare de Nice-Ville (Parvis Thiers)", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Avenue Thiers / Parvis Gare SNCF, 06000 Nice", "intermodalite": "TGV, TER, Tram 1", "cout": 8500,
         "justification": "Hub ferroviaire et multimodal central de Nice (plus de 8 millions de voyageurs/an).", "lon": 7.2618, "lat": 43.7042},
        {"nom": "Libération - Gare du Sud", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Place Général de Gaulle / Halle de la Gare du Sud, 06100 Nice", "intermodalite": "Tram 1, Chemins de Fer de Provence", "cout": 8500,
         "justification": "Quartier commerçant très dense avec fort taux de ménages sans voiture (32%).", "lon": 7.2621, "lat": 43.7082},
        {"nom": "Port Lympia (Bassin du Port)", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Quai Lunel / Quai des Deux Emmanuel, 06300 Nice", "intermodalite": "Tram 2, Ferries Corse", "cout": 8500,
         "justification": "Terminus Tram 2 et interface maritime ; zone touristique et résidentielle dense.", "lon": 7.2856, "lat": 43.6968},
        {"nom": "Grand Arénas - Gare Saint-Augustin", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Boulevard René Cassin / Pôle d'échange multimodal, 06200 Nice", "intermodalite": "Gare TER, Tram 2, Tram 3, Aéroport", "cout": 8500,
         "justification": "Nouveau quartier d'affaires métropolitain de l'Éco-Vallée.", "lon": 7.2145, "lat": 43.6670},
        {"nom": "Garibaldi - Place du Pin", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Place Garibaldi / Rue Bonaparte, 06300 Nice", "intermodalite": "Tram 1, Tram 2", "cout": 8500,
         "justification": "Nœud de correspondance majeur entre les deux lignes de tramway.", "lon": 7.2798, "lat": 43.7011},
        {"nom": "Valrose Université (Campus Sciences)", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Avenue Joseph Vallot / Parc Valrose, 06100 Nice", "intermodalite": "Tram 1", "cout": 7500,
         "justification": "Campus universitaire avec 15 000 étudiants et chercheurs.", "lon": 7.2608, "lat": 43.7154},
        {"nom": "P+R Henri Sappia (Nord de Nice)", "categorie": "Parking-Relais P+R", "commune": "Nice",
         "adresse_precise": "Boulevard Henri Sappia, 06100 Nice", "intermodalite": "Terminus Tram 1, Autoroute A8", "cout": 7500,
         "justification": "Parking-relais de 765 places en sortie d'autoroute A8 Nice-Nord.", "lon": 7.2474, "lat": 43.7312},
        {"nom": "P+R Pont Michel (Est de Nice)", "categorie": "Parking-Relais P+R", "commune": "Nice",
         "adresse_precise": "Route de Turin / Pont Michel, 06300 Nice", "intermodalite": "Tram 1, P+R 450 places", "cout": 7500,
         "justification": "Entrée de ville est de Nice, rabattement depuis les vallées du Paillon.", "lon": 7.2872, "lat": 43.7180},
        {"nom": "P+R Parc Phoenix (Ouest de Nice)", "categorie": "Parking-Relais P+R", "commune": "Nice",
         "adresse_precise": "Boulevard René Cassin / Arénas, 06200 Nice", "intermodalite": "Tram 2, Bus métropolitains", "cout": 7500,
         "justification": "Rabattement périurbain ouest et zone aéroportuaire.", "lon": 7.2185, "lat": 43.6685},
        {"nom": "Gare de Nice-Riquier", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Place Auguste Blanqui, 06300 Nice", "intermodalite": "Gare TER Monaco/Vintimille", "cout": 8500,
         "justification": "Gare la plus fréquentée pour les navetteurs vers Monaco (fort besoin de mobilité partagée).", "lon": 7.2912, "lat": 43.7048},
        {"nom": "Magnan - Faculté de Lettres", "categorie": "Zone Résidentielle Dense", "commune": "Nice",
         "adresse_precise": "Avenue de la Californie / Boulevard de la Madeleine, 06200 Nice", "intermodalite": "Tram 2", "cout": 6500,
         "justification": "Quartier résidentiel très dense et front de mer.", "lon": 7.2421, "lat": 43.6908},
        {"nom": "Promenade des Anglais - Albert 1er", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Promenade des Anglais / Avenue de Verdun, 06000 Nice", "intermodalite": "Pistes cyclables, Bus express", "cout": 8500,
         "justification": "Cœur touristique et hôtelier international de Nice.", "lon": 7.2665, "lat": 43.6955},
        {"nom": "Pasteur - Hôpital Universitaire", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Nice",
         "adresse_precise": "Voie Romaine / Hôpital Pasteur 2, 06000 Nice", "intermodalite": "Terminus Tram 1", "cout": 7500,
         "justification": "Grand pôle hospitalier métropolitain (personnel soignant et visiteurs).", "lon": 7.2858, "lat": 43.7285},
        {"nom": "Allianz Riviera - Éco-Vallée", "categorie": "Parking-Relais P+R", "commune": "Nice",
         "adresse_precise": "Boulevard des Jardiniers, 06200 Nice", "intermodalite": "Tram 3, P+R événementiel", "cout": 7500,
         "justification": "Grand stade et pôle tertiaire en pleine expansion dans la plaine du Var.", "lon": 7.1920, "lat": 43.7085},
        {"nom": "Gare de Cagnes-sur-Mer", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Cagnes-sur-Mer",
         "adresse_precise": "Avenue de la Gare, 06800 Cagnes-sur-Mer", "intermodalite": "TER PACA, Bus Lignes d'Azur", "cout": 7500,
         "justification": "Deuxième commune de la métropole (52 000 habitants).", "lon": 7.1495, "lat": 43.6612},
        {"nom": "Gare de Saint-Laurent-du-Var", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Saint-Laurent-du-Var",
         "adresse_precise": "Esplanade du Levant / Centre commercial Cap 3000, 06700 Saint-Laurent-du-Var", "intermodalite": "TER PACA, Bus", "cout": 7500,
         "justification": "Pôle multimodal stratégique à côté du plus grand pôle commercial de la Côte d'Azur (Cap 3000).", "lon": 7.1950, "lat": 43.6620}
    ]

    sub_centers = [
        (7.1495, 43.6612, 1800, "Cagnes-sur-Mer"),
        (7.1950, 43.6620, 1500, "Saint-Laurent-du-Var"),
        (7.2856, 43.6968, 1400, "Port Lympia")
    ]
    build_city_dataset("nice", "Nice Côte d'Azur", 7.2620, 43.7050, 550_000, existing_citiz, transit_stops, candidates_list, sub_centers)


def generate_grenoble():
    # Grenoble : réseau de référence le plus dense de France (168 stations existantes)
    # Positions réelles de stations Citiz à Grenoble
    existing_citiz = [
        {"nom": "Grenoble Gare Centrale", "lon": 5.7142, "lat": 45.1912, "capacite": 6},
        {"nom": "Grenoble Alsace-Lorraine", "lon": 5.7205, "lat": 45.1901, "capacite": 4},
        {"nom": "Grenoble Victor Hugo", "lon": 5.7262, "lat": 45.1888, "capacite": 5},
        {"nom": "Grenoble Verdun - Préfecture", "lon": 5.7328, "lat": 45.1895, "capacite": 4},
        {"nom": "Grenoble Chavant", "lon": 5.7315, "lat": 45.1848, "capacite": 4},
        {"nom": "Grenoble Championnet", "lon": 5.7232, "lat": 45.1852, "capacite": 3},
        {"nom": "Grenoble Berriat - Le Magasin", "lon": 5.7095, "lat": 45.1878, "capacite": 3},
        {"nom": "Grenoble Saint-Bruno", "lon": 5.7125, "lat": 45.1842, "capacite": 3},
        {"nom": "Grenoble Europole - Palais de Justice", "lon": 5.7108, "lat": 45.1935, "capacite": 4},
        {"nom": "Grenoble Île Verte", "lon": 5.7385, "lat": 45.1982, "capacite": 3},
        {"nom": "Grenoble Caserne de Bonne", "lon": 5.7258, "lat": 45.1822, "capacite": 4},
        {"nom": "Grenoble Vallier - Libération", "lon": 5.7162, "lat": 45.1782, "capacite": 3},
        {"nom": "Grenoble Malherbe", "lon": 5.7392, "lat": 45.1742, "capacite": 2},
        {"nom": "Grenoble Grand'Place", "lon": 5.7325, "lat": 45.1585, "capacite": 4},
        {"nom": "La Tronche Hôpital Michallon", "lon": 5.7485, "lat": 45.2045, "capacite": 4},
        {"nom": "Saint-Martin-d'Hères Campus Universités", "lon": 5.7685, "lat": 45.1925, "capacite": 5},
        {"nom": "Échirolles Gare TER", "lon": 5.7155, "lat": 45.1525, "capacite": 3},
        {"nom": "Fontaine Hôtel de Ville", "lon": 5.6885, "lat": 45.1932, "capacite": 3}
    ]

    # Transports TAG (Tram A, B, C, D, E)
    transit_stops = [
        {"nom": "Gare de Grenoble (Tram A / B)", "type": "tram", "lon": 5.7142, "lat": 45.1912},
        {"nom": "Hub Chavant (Tram A / C)", "type": "tram", "lon": 5.7315, "lat": 45.1848},
        {"nom": "Hub Alsace-Lorraine (Tram A / B / E)", "type": "tram", "lon": 5.7205, "lat": 45.1901},
        {"nom": "Hub Victor Hugo (Tram A / B)", "type": "tram", "lon": 7.2621, "lat": 45.1888},
        {"nom": "Vallier-Jaurès (Tram C / E)", "type": "tram", "lon": 5.7165, "lat": 45.1785},
        {"nom": "Grand'Place (Terminus Tram A)", "type": "tram", "lon": 5.7325, "lat": 45.1585},
        {"nom": "Presqu'île CEA (Terminus Tram B)", "type": "tram", "lon": 5.7015, "lat": 45.2085},
        {"nom": "Campus Bibliothèques Universitaires (Tram B / C)", "type": "tram", "lon": 5.7725, "lat": 45.1920},
        {"nom": "Hôpital Couple-Enfant (Tram B)", "type": "tram", "lon": 5.7485, "lat": 45.2045},
        {"nom": "P+R Esplanade (Tram E)", "type": "parc_relais", "lon": 5.7185, "lat": 45.2012},
        {"nom": "P+R Seyssinet (Tram C)", "type": "parc_relais", "lon": 5.6985, "lat": 45.1802},
        {"nom": "P+R Vallier-Catane (Tram C)", "type": "parc_relais", "lon": 5.7045, "lat": 45.1785},
        {"nom": "P+R Grand Sablon (Tram B)", "type": "parc_relais", "lon": 5.7525, "lat": 45.2035}
    ]

    # Candidats pour Grenoble (densification périurbaine et zones technologiques)
    candidates_list = [
        {"nom": "Presqu'île - Polygone Scientifique (GIANT)", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Grenoble",
         "adresse_precise": "Place Nelson Mandela / Rue Félix Esclangon, 38000 Grenoble", "intermodalite": "Tram B, Gare Grenoble Presqu'île", "cout": 8500,
         "justification": "Grand pôle de recherche mondial (CEA, CNRS, ESRF) avec 10 000 salariés en transition mobilités.", "lon": 5.7015, "lat": 45.2085},
        {"nom": "P+R Esplanade (Porte Nord)", "categorie": "Parking-Relais P+R", "commune": "Grenoble",
         "adresse_precise": "Boulevard de l'Esplanade, 38000 Grenoble", "intermodalite": "Tram E, Entrée autoroute A48", "cout": 7500,
         "justification": "Grand parking de rabattement périurbain depuis le Voironnais et la Chartreuse.", "lon": 5.7185, "lat": 45.2012},
        {"nom": "Inovallée Meylan (Pôle Tech)", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Meylan",
         "adresse_precise": "Chemin du Vieux Chêne / Boulevard des Alpes, 38240 Meylan", "intermodalite": "Lignes Chronobus C1, C2", "cout": 7500,
         "justification": "Parc technologique de 350 entreprises et 12 000 emplois peu couvert en autopartage.", "lon": 5.7895, "lat": 45.2155},
        {"nom": "Gare de Saint-Égrève Saint-Robert", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Saint-Égrève",
         "adresse_precise": "Place de la Gare, 38120 Saint-Égrève", "intermodalite": "TER Lyon-Grenoble, Tram E", "cout": 7500,
         "justification": "Interconnexion rail-route pour les navetteurs de la cluse de l'Isère.", "lon": 5.6815, "lat": 45.2315},
        {"nom": "Gare de Gières - Universités", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Gières",
         "adresse_precise": "Place de la Gare, 38610 Gières", "intermodalite": "Gare TER Chambéry/Grenoble, Tram B", "cout": 8500,
         "justification": "Deuxième gare de l'agglomération et porte d'accès au campus universitaire.", "lon": 5.7850, "lat": 45.1855},
        {"nom": "Pont-de-Claix - L'Étoile", "categorie": "Pôle Multimodal / Quartier Dense", "commune": "Le Pont-de-Claix",
         "adresse_precise": "Avenue Charles de Gaulle / Étoile, 38800 Le Pont-de-Claix", "intermodalite": "Terminus Tram A, Ligne C2", "cout": 7500,
         "justification": "Porte sud de l'agglomération, quartier en renouvellement urbain.", "lon": 5.6985, "lat": 45.1325},
        {"nom": "P+R Seyssinet - Pariset", "categorie": "Parking-Relais P+R", "commune": "Seyssinet-Pariset",
         "adresse_precise": "Avenue de Grenoble / Rue de la Fauconnière, 38170 Seyssinet", "intermodalite": "Tram C, P+R 220 places", "cout": 7500,
         "justification": "Rabattement depuis le Vercors pour les actifs se rendant à Grenoble.", "lon": 5.6985, "lat": 45.1802},
        {"nom": "Bourg de Fontaine (Marché)", "categorie": "Zone Résidentielle Dense", "commune": "Fontaine",
         "adresse_precise": "Avenue Aristide Briand / Rue Jean Jaurès, 38600 Fontaine", "intermodalite": "Tram A", "cout": 6500,
         "justification": "Cœur de commune dense avec fort besoin social de mobilité partagée.", "lon": 5.6885, "lat": 45.1932}
    ]

    sub_centers = [
        (5.7685, 45.1925, 1800, "Campus Saint-Martin-d'Hères"),
        (5.7155, 45.1525, 1600, "Échirolles"),
        (5.7895, 45.2155, 1500, "Meylan Inovallée")
    ]
    build_city_dataset("grenoble", "Grenoble-Alpes Métropole", 5.7245, 45.1885, 450_000, existing_citiz, transit_stops, candidates_list, sub_centers)


def main():
    logger.info("Génération des jeux de données multi-villes...")
    generate_nice()
    generate_grenoble()
    logger.info("Génération terminée pour Nice et Grenoble !")


if __name__ == "__main__":
    main()

