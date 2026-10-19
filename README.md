# Hackathon Mobility (Epitech × Citiz)

Qui a réellement accès à une option de mobilité à 5 minutes à pied, et où Citiz doit-il ouvrir
de nouvelles stations sous contrainte de budget ?

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac : source .venv/bin/activate)
pip install -r requirements.txt   # versions exactes testées : requirements-lock.txt
pytest                            # vérifie l'installation
```

Testé sous Python 3.14.2 (Windows) ; Python 3.12+ requis pour l'analyse.

## Arborescence

```
config/       settings.yaml (zone d'étude, CRS, rayon de marche, poids, coûts)
data/raw/     données brutes (jamais commitées)
data/processed/  sorties GeoParquet du pipeline (jamais commitées)
src/ingest/   téléchargement, collecte de l'historique, vérification
src/features/ accessibilité, couverture   src/model/ modèle prédictif   src/optim/ optimisation
app/          démo Streamlit              docs/  méthodologie, éthique, sources
slides/       présentation                tests/ pytest              scripts/ build_all
```

# Récupération des données

Les trois scripts de `src/ingest/` n'utilisent que la bibliothèque standard (Python 3.9+) : ils
tournent même sans le venv, depuis n'importe quel dossier (les chemins sont relatifs à la racine du dépôt).

## 1. Tout télécharger

```bash
python src/ingest/download_all.py
```

Ce que ça récupère :

| Catégorie | Contenu | Taille approx. |
|---|---|---|
| `citiz` | Tous les flux GBFS Citiz (15 réseaux régionaux) : stations, disponibilités, véhicules | quelques Mo |
| `gbfs` | Tous les autres GBFS de France : vélos, trottinettes, autres autopartages | ~100 Mo |
| `gtfs` | Tous les GTFS de transports en commun de France (bus, tram, métro, train, DROM inclus) | 2 à 4 Go |
| `stops_national` | Agrégat national des arrêts (data.gouv.fr, non dédoublonné) | 417 Mo |
| `gbfs_catalog` | Catalogue mondial GBFS (MobilityData) | < 1 Mo |
| `insee` | Filosofi carreaux 200 m (population + revenus), projections Omphale, recensement logement par IRIS (motorisation), BPE 2025 (équipements) | ~650 Mo |
| `ign` | ADMIN EXPRESS (communes, départements) + contours IRIS, dernière édition | ~1 Go |
| `osm` | Réseau OpenStreetMap France (Geofabrik) | ~4,5 Go |

**Total : environ 8 à 10 Go.** Le script reprend là où il s'est arrêté : si ça coupe, relance la même commande.

### Versions plus légères

```bash
# Tout sauf OSM France, avec OSM d'une seule région
python src/ingest/download_all.py --osm region --osm-region rhone-alpes

# Seulement Citiz + INSEE + IGN (le minimum pour démarrer)
python src/ingest/download_all.py --only citiz insee ign

# GTFS seulement pour certaines villes
python src/ingest/download_all.py --only gtfs --gtfs-filter strasbourg grenoble
```

Noms de régions OSM : voir https://download.geofabrik.de/europe/france.html
(ex : `ile-de-france`, `rhone-alpes`, `alsace`, `bretagne`...). Geofabrik utilise les régions d'avant 2016 ;
le script traduit les noms actuels (`grand-est` → alsace + lorraine + champagne-ardenne).

### Ce que le script produit

```
data/raw/
  gbfs_citiz/<réseau>/  gbfs.json, station_information.json, station_status.json, ...
  gbfs_citiz/index.json
  gbfs_all/...
  gtfs/*.zip
  stops_national/arrets_transport_france.csv
  insee/  filosofi (gpkg zip), omphale (zip), logement IRIS, bpe25.parquet
  ign/admin_express/*.7z   ign/iris/*.7z
  osm/*.osm.pbf
  transport_data_gouv/catalogue_datasets.json
  manifest.csv          <- liste de tout ce qui a été téléchargé (url, taille, statut)
docs/sources.md         <- liste des sources, livrable demandé par le sujet
```

Les fichiers IGN sont en `.7z` : extraire avec 7-Zip (Windows) ou `7z x fichier.7z` (Linux/Mac).

## 2. Vérifier les données

```bash
python src/ingest/check_data.py          # présence, tailles, JSON, comptages Citiz
python src/ingest/check_data.py --deep   # + intégrité zip / 7z / parquet / pbf et contenu GTFS
```

Écrit `data/raw/check_report.md` (✅ OK, ⚠️ à surveiller, ❌ à corriger ; code retour 1 si ❌).

## 3. Collecter l'historique d'usage Citiz (à lancer dès le début du hackathon)

```bash
python src/ingest/collect_gbfs_status.py --interval 5
```

Une photo de l'état de chaque station Citiz toutes les 5 minutes, dans
`data/raw/gbfs_history/`. Les variations du nombre de véhicules disponibles donnent un
proxy de l'usage réel par station : c'est une cible pour le modèle prédictif.
Laisse-le tourner dans un terminal à part pendant les 2,5 jours.

## Notes

- `data/` est dans le `.gitignore` : on ne commite jamais les données, seulement le code.
- Les erreurs éventuelles sont listées dans `manifest.csv` (souvent un flux protégé par clé
  API ou un serveur indisponible) ; relancer le script les retente.
- Les liens INSEE sont ceux des éditions les plus récentes au 19/10/2026. Les jeux
  transport.data.gouv.fr et IGN sont découverts automatiquement, donc toujours à jour.
