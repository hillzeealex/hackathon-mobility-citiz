# Récupérer les données (Grenoble)

Ce guide permet à chaque membre de l'équipe d'avoir **exactement les mêmes données** que le reste de l'équipe.

> **Vous voulez seulement regarder les données ?** Inutile de tout retélécharger : demandez le zip
> `hackathon_grenoble_donnees_propres_AAAAMMJJ.zip` (≈ 2,3 Mo). Il s'ouvre avec Excel (`.csv`),
> QGIS (`.gpkg`) ou un navigateur (`carte_apercu.html`, en double-cliquant). Chaque colonne est expliquée
> dans `DICTIONNAIRE_DONNEES.md`.

## 1. Tout retélécharger (≈ 20 min, ≈ 4,5 Go sur le disque)

Prérequis : Python 3.12 ou plus récent, et le dépôt Git cloné.
Toutes les commandes se lancent dans **PowerShell, depuis le dossier du dépôt**.

```powershell
# a) Environnement Python (une seule fois, ≈ 5 min)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# b) Téléchargement : mêmes sources, même région OSM, mêmes filtres GTFS (≈ 15 min, ≈ 2 Go)
python src/ingest/download_all.py --osm region --osm-region rhone-alpes --gtfs-filter grenoble reseau-interurbain-cars-region-isere cars-region-express horaires-sncf

# c) Vérification : doit afficher "0 à corriger"
python src/ingest/check_data.py --deep

# d) Reconstruction de data/processed (≈ 2 min)
python -m src.ingest.zone          # 49 communes de la métropole
python -m src.ingest.population    # carreaux de 200 m, population calée, motorisation
python -m src.ingest.offer         # arrêts, stations Citiz, zones Voi, dédoublonnés

# e) Export partageable (zip, CSV, carte HTML) dans data/share/
python scripts/export_share.py
```

À savoir :

- **Reprise automatique.** Si le téléchargement est coupé, relancez la même commande : les fichiers déjà
  présents ne sont pas retéléchargés.
- **Avertissement attendu.** `check_data` signale 1 « à surveiller » : deux flux de vélos hors zone
  (Pony Marseille, protégé par une clé ; GraouLib Metz, serveur en panne). Ce n'est pas bloquant.
- **Extraction automatique.** Les archives IGN (`.7z`) et Filosofi (`.zip`) sont décompressées par les
  scripts à la première utilisation, ce qui ajoute ≈ 2,4 Go.
- **Données mouvantes.** Les GTFS et GBFS évoluent chaque jour. Un téléchargement fait un autre jour donne
  des chiffres légèrement différents (horaires, vélos disponibles). Les données de référence de l'équipe
  datent du **19/10/2026**.
- **Région OSM.** Geofabrik découpe la France selon les régions d'avant 2016 : Grenoble se trouve dans
  `rhone-alpes`, pas dans `auvergne-rhone-alpes`.
- **Phase 3 (accessibilité) en cours.** La commande de reconstruction sera ajoutée ici dès qu'elle sera prête.

### Historique d'usage Citiz (ne se retélécharge pas)

`data/raw/gbfs_history/station_status_*.csv` est **collecté en continu** sur un seul poste depuis le
19/10/2026 (un relevé toutes les 5 min). Il ne peut pas être retéléchargé : demandez une copie du fichier.

## 2. Liste des fichiers bruts (téléchargement du 19/10/2026)

| Fichier | Taille | Contenu |
|---|---:|---|
| `ign/admin_express/ADMIN-EXPRESS-COG_4-0__GPKG_WGS84G_FRA_2026-01-01.7z` | 579 Mo | Limites administratives France (communes, EPCI…) |
| `osm/rhone-alpes-latest.osm.pbf` | 507 Mo | OpenStreetMap Rhône-Alpes (réseau piéton) |
| `stops_national/arrets_transport_france.csv` | 417 Mo | Agrégat national des arrêts (non utilisé pour Grenoble) |
| `insee/filosofi2021_carreaux_200m_gpkg.zip` | 295 Mo | Population et revenus au carreau de 200 m (France) |
| `insee/bpe25.parquet` | 164 Mo | Base permanente des équipements 2025 (France) |
| `ign/iris/CONTOURS-IRIS_3-0__GPKG_WGS84G_FRA_2026-01-01.7z` | 84 Mo | Contours IRIS (France) |
| `insee/base_ic_logement_2023_iris.zip` | 32 Mo | Logement par IRIS 2023 (dont motorisation) |
| `gtfs/reseau-interurbain-cars-region-isere-38-1__40287.zip` | 27 Mo | Cars Région Isère |
| `gtfs/horaires-sncf__83582.zip` | 5,2 Mo | SNCF TER, TGV, Intercités (France) |
| `gtfs/horaires-theoriques-du-reseau-tag__83459.zip` | 5,0 Mo | Réseau TAG (bus, tram) |
| `gtfs/reseau-interurbain-cars-region-express__83112.zip` | 2,8 Mo | Cars Région Express |
| `gtfs/horaires-theoriques-des-lignes-m-covoit-ligne-plus__81617.zip` | 0,4 Mo | Lignes de covoiturage (exclues de l'analyse) |
| `gtfs/horaires-theoriques-du-telepherique-de-la-bastille__81618.zip` | 4 Ko | Téléphérique de la Bastille |
| `insee/projections_omphale_2021_2070.zip` | 0,8 Mo | Projections de population (Omphale) |
| `insee/logement_dom_iris_2023.parquet` | 0,1 Mo | Logement par IRIS, DOM (non utilisé) |
| `gbfs_all/` (1 214 fichiers) | 76 Mo | Vélos, trottinettes, autopartage de toute la France (dont Voi Grenoble, 2 Mo) |
| `transport_data_gouv/catalogue_datasets.json` | 3,1 Mo | Catalogue des jeux de transport.data.gouv.fr |
| `gbfs_citiz/` (136 fichiers) | 2,7 Mo | Citiz : 15 réseaux, 1 617 stations |
| `gbfs_history/` | 2,1 Mo et + | Historique Citiz collecté (voir ci-dessus) |
| `gbfs_catalog/systems.csv` | 0,2 Mo | Catalogue mondial GBFS (MobilityData) |
| `manifest.csv`, `check_report.md` | 0,6 Mo | Liste de tout ce qui a été téléchargé, rapport de vérification |
| **Total téléchargé** | **≈ 2,1 Go** | + ≈ 2,4 Go une fois les archives décompressées |

Liste exhaustive avec les URL et la date de chaque fichier : `data/raw/manifest.csv`.

## 3. Option : zip des données brutes limitées à la zone (pour un drive partagé)

Pour un coéquipier qui ne peut pas tout retélécharger, on peut préparer un zip des données **brutes**
réduites à la métropole, sans l'OSM régional complet ni les fichiers nationaux :

| Contenu | Taille estimée |
|---|---:|
| GTFS des 6 réseaux utilisés, tels quels | 42 Mo |
| GBFS Citiz, Voi Grenoble, historique Citiz, catalogue | ≈ 10 Mo |
| Filosofi, ADMIN EXPRESS, IRIS, BPE, logement : découpés sur la zone | ≈ 6 Mo |
| OSM : voies de la zone (GeoPackage) | 96 à 191 Mo |
| **Zip** | **≈ 81 à 113 Mo** |

Estimation : `python scripts/export_share.py --estimate-raw-zone`.
Ce zip **n'est pas encore créé**. L'OSM représente l'essentiel du volume et de l'incertitude.
Remarques :

- Le GTFS SNCF couvre toute la France et celui des Cars Région Isère tout le département. Ils sont gardés
  entiers, car c'est le format attendu par les scripts.
- Les scripts du dépôt attendent les fichiers nationaux. Avec ce zip, il faudra lancer les scripts de
  reconstruction en mode « zone » (à adapter si l'option est retenue).
