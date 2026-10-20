"""
Script d'extraction et d'intégration des données d'emploi (Sirene géolocalisée)
et des zones d'activités économiques (ZAE Open Data Nantes Métropole)
pour le scénario professionnel de Citiz.
"""
import json
import urllib.request
from pathlib import Path
import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

BASE_DIR = Path(__file__).resolve().parent.parent
NANTES_DIR = BASE_DIR / "data" / "processed" / "nantes"
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SIRENE_URL = "https://static.data.gouv.fr/resources/sirene-geolocalise-parquet/20240107-143656/sirene2024-geo.parquet"
ZAE_URL = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_zones-activite-economique-zae-nantes-metropole/exports/geojson"

COMMUNES_METROPOLE = [
    '44109', '44018', '44020', '44026', '44035', '44047', '44070', '44074',
    '44084', '44094', '44101', '44114', '44120', '44143', '44150', '44162',
    '44166', '44171', '44172', '44190', '44194', '44198', '44204', '44215'
]

POLE_NAMES = {
    15: "Pôle Commercial & Tertiaire Atlantis - ZAC d'Armor (Saint-Herblain)",
    55: "Pôle Tertiaire Nantes Nord - Santos Dumont / Pont du Cens (Nantes)",
    22: "Pôle Commercial & d'Activités Ragon / Océane (Rezé)",
    33: "Parc Tertiaire Ar Mor (Saint-Herblain Nord)",
    10: "Pôle Aéronautique & Logistique Aéroport - D2A (Bouguenais)",
    17: "Zone Industrielle & Artisanale de la Lorie (Saint-Herblain)",
    57: "Pôle Économique Jules Verne - Beaujoire Est (Nantes Erdre)",
    65: "Zone Industrielle de la Belle-Étoile (Carquefou)",
    59: "Technopole Atlanpole - Campus La Chantrerie (Nantes)",
    47: "Pôle Tertiaire Île de Nantes Sud / Beaulieu"
}

def main():
    print("=== 1. TÉLÉCHARGEMENT DES ZAE OPEN DATA NANTES MÉTROPOLE ===")
    zae_geojson_path = RAW_DIR / "zae_nantes_metropole.geojson"
    if not zae_geojson_path.exists():
        print(f"Téléchargement des ZAE depuis {ZAE_URL}...")
        req = urllib.request.Request(ZAE_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            zae_geojson_path.write_bytes(resp.read())
        print("ZAE sauvegardées.")

    zae_gdf = gpd.read_file(zae_geojson_path)
    zae_gdf.to_crs(4326).to_file(NANTES_DIR / "zae.geojson", driver="GeoJSON")

    print("\n=== 2. EXTRACTION SIRENE 44 VIA DUCKDB ===")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    
    communes_str = ", ".join(f"'{c}'" for c in COMMUNES_METROPOLE)
    query = f"""
    SELECT 
        siret,
        codeCommuneEtablissement as code_commune,
        trancheEffectifsEtablissement as tranche,
        ST_X(geometry) as lon,
        ST_Y(geometry) as lat,
        CASE trancheEffectifsEtablissement
            WHEN '01' THEN 1.5
            WHEN '02' THEN 4.0
            WHEN '03' THEN 7.5
            WHEN '11' THEN 14.5
            WHEN '12' THEN 34.5
            WHEN '21' THEN 74.5
            WHEN '22' THEN 149.5
            WHEN '31' THEN 224.5
            WHEN '32' THEN 374.5
            WHEN '41' THEN 749.5
            WHEN '42' THEN 1499.5
            WHEN '51' THEN 3499.5
            WHEN '52' THEN 7499.5
            WHEN '53' THEN 10000.0
            ELSE 0.0
        END as emplois_estimes
    FROM '{SIRENE_URL}'
    WHERE etatAdministratifEtablissement = 'A'
      AND codeCommuneEtablissement IN ({communes_str})
      AND geometry IS NOT NULL
    """
    etabs_df = con.execute(query).df()
    tot_emplois_sirene = etabs_df["emplois_estimes"].sum()
    print(f"Établissements actifs extraits : {len(etabs_df):,} (total emplois bruts : {tot_emplois_sirene:,.1f})")

    print("\n=== 3. PROJECTION ET AGRÉGATION PAR CARREAU 200 M ===")
    cells_path = NANTES_DIR / "cells.parquet"
    cells_gdf = gpd.read_parquet(cells_path)

    to_lambert = Transformer.from_crs(4326, 2154, always_xy=True)
    xs, ys = to_lambert.transform(etabs_df["lon"].to_numpy(), etabs_df["lat"].to_numpy())
    etabs_df["x"] = xs
    etabs_df["y"] = ys

    cell_coords = np.column_stack([cells_gdf["x"].to_numpy(), cells_gdf["y"].to_numpy()])
    tree = cKDTree(cell_coords)
    etab_coords = np.column_stack([xs, ys])
    
    dists, idxs = tree.query(etab_coords, distance_upper_bound=150.0)
    valid_mask = dists <= 150.0

    etabs_assigned = etabs_df.iloc[valid_mask].copy()
    etabs_assigned["cell_idx"] = idxs[valid_mask]

    emplois_per_cell = etabs_assigned.groupby("cell_idx")["emplois_estimes"].sum()
    cells_gdf["emplois"] = cells_gdf.index.map(emplois_per_cell).fillna(0.0).round(1)
    tot_emplois_grid = cells_gdf["emplois"].sum()
    print(f"Total emplois agrégés sur la grille 200 m : {tot_emplois_grid:,.1f}")

    insee_ref = 357000.0
    ecart = (tot_emplois_grid - insee_ref) / insee_ref * 100
    print(f"Contrôle INSEE : Référence = {insee_ref:,.0f} | Sirene = {tot_emplois_grid:,.0f} | Écart = {ecart:+.2f}%")

    print("\n=== 4. ANALYSE COUVERTURE AUTOPARTAGE EXISTANT (V2, Citiz + Marguerite) ===")
    offer_path = NANTES_DIR / "offer_served.parquet"
    offer_gdf = gpd.read_parquet(offer_path)
    carsharing = offer_gdf[offer_gdf["type"].isin(["citiz", "autopartage"])].copy()

    buffer_400m = carsharing.geometry.buffer(400).union_all()
    cell_pts = cells_gdf.geometry.centroid
    is_covered = cell_pts.intersects(buffer_400m)
    cells_gdf["couvert_autopartage_v2"] = is_covered

    emp_couverts = cells_gdf.loc[is_covered, "emplois"].sum()
    part_emp_couverts = emp_couverts / tot_emplois_grid * 100
    pop_couverte = cells_gdf.loc[is_covered, "population"].sum()
    part_pop_couverte = pop_couverte / cells_gdf["population"].sum() * 100

    print(f"Emplois à 5 min à pied d'un autopartage : {emp_couverts:,.0f} ({part_emp_couverts:.1f}% des emplois)")
    print(f"Population à 5 min à pied d'un autopartage : {pop_couverte:,.0f} ({part_pop_couverte:.1f}%)")

    print("\n=== 5. TOP 10 DES PÔLES D'EMPLOI SANS AUTOPARTAGE À 5 MIN ===")
    zae_2154 = zae_gdf.to_crs(2154).copy()
    dissolved = zae_2154.dissolve().explode(index_parts=False).reset_index(drop=True)
    dissolved["pole_id"] = np.arange(len(dissolved))
    dissolved["nom_pole"] = [POLE_NAMES.get(pid, f"Pôle d'Activité #{pid}") for pid in dissolved["pole_id"]]

    cells_pts_gdf = gpd.GeoDataFrame(
        cells_gdf[["id", "emplois", "couvert_autopartage_v2"]],
        geometry=cells_gdf.geometry.centroid,
        crs=2154
    )
    joined = gpd.sjoin(cells_pts_gdf, dissolved[["pole_id", "nom_pole", "geometry"]], how="inner", predicate="within")

    poles_agg = joined.groupby(["pole_id", "nom_pole"]).agg(
        emplois_totaux=("emplois", "sum"),
        emplois_non_couverts=("emplois", lambda s: s[~joined.loc[s.index, "couvert_autopartage_v2"]].sum()),
        part_non_couverte=("couvert_autopartage_v2", lambda s: (~s).mean() * 100)
    ).reset_index()

    top10_unserved = poles_agg.sort_values("emplois_non_couverts", ascending=False).head(10).copy()
    top10_unserved["rang"] = np.arange(1, len(top10_unserved) + 1)
    top10_unserved["part_non_couverte_pct"] = top10_unserved["part_non_couverte"].round(1)
    top10_unserved["emplois_non_couverts"] = top10_unserved["emplois_non_couverts"].round(0).astype(int)
    top10_unserved["emplois_totaux"] = top10_unserved["emplois_totaux"].round(0).astype(int)

    cols = ["rang", "nom_pole", "emplois_non_couverts", "emplois_totaux", "part_non_couverte_pct"]
    top10_clean = top10_unserved[cols]
    print("\nTop 10 final :")
    print(top10_clean.to_string(index=False))

    cells_gdf.to_parquet(cells_path)
    dissolved.to_crs(4326).to_file(NANTES_DIR / "poles_emploi.geojson", driver="GeoJSON")
    top10_clean.to_csv(NANTES_DIR / "top10_poles_emploi_sans_autopartage.csv", index=False, sep=";", decimal=",")
    print("\nFichiers sauvegardés avec succès !")

if __name__ == "__main__":
    main()
