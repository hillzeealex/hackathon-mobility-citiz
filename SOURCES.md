# Sources de données

Téléchargées le 19/10/2026. Dossier local : `data/`.

| Dossier | Contenu | Source | Licence |
|---|---|---|---|
| `data/arrets/` | Arrêts de transport en France (agrégat national des `stops.txt` GTFS, non dédupliqué, export du 13/01/2026) | https://www.data.gouv.fr/datasets/arrets-de-transport-en-france | Licence Ouverte 2.0 |
| `data/gbfs/` | Instantané de tous les flux GBFS référencés (vélos, trottinettes, autopartage dont Citiz) : `station_information`, `station_status`, `vehicle_status`/`free_bike_status`, `vehicle_types`, `system_information`. `index.json` liste chaque flux et ses erreurs | https://transport.data.gouv.fr/datasets?type=vehicles-sharing | ODbL / LO selon producteur |
| `data/gbfs/systems.csv` | Catalogue mondial des flux GBFS | https://github.com/MobilityData/gbfs/blob/master/systems.csv | CC-BY |
| `data/population/` | Filosofi 2021, carreaux de 200 m (métropole, Martinique, La Réunion), GeoPackage | https://www.insee.fr/fr/statistiques/8735162 | Licence Ouverte |
| `data/projections/` | Omphale, projections de population 2021-2070 par département et région | https://www.insee.fr/fr/statistiques/6652134 | Licence Ouverte |
| `data/admin/` | IGN ADMIN-EXPRESS-COG 4.0 (01/01/2026) et CONTOURS-IRIS 3.0 (01/01/2026), GeoPackage WGS84 | https://geoservices.ign.fr/adminexpress | Licence Ouverte 2.0 |

Non téléchargés :
- Réseau piéton OSM (https://download.geofabrik.de/europe/france.html) : à prendre par région une fois le territoire choisi.
- GTFS complets (lignes, horaires) : à prendre par réseau sur https://transport.data.gouv.fr/datasets?type=public-transit pour le territoire retenu.
