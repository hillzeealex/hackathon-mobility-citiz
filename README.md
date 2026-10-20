# Hackathon Mobility Citiz (Epitech × Citiz × Microsoft)

**Qui a réellement accès à une option de mobilité à 5 minutes à pied, et où faut-il en ajouter ?**

1. **Carte d'accès** : nombre d'options de mobilité (bus, tram, train, vélo, trottinette, Citiz) à 5 min
   à pied (400 m) par habitant, du plus froid au plus chaud.
2. **Offre par type** et population desservie.
3. **Modèle prédictif + optimiseur sous budget** : liste priorisée de nouvelles stations.

Deux niveaux d'analyse :

- **France entière (niveau 1, fait)** : 2,3 M carreaux de 200 m, 547 GTFS + tous les GBFS, agrégats
  IRIS / commune / EPCI / département, classement des EPCI à fort potentiel Citiz. Accessibilité « V1 »
  à vol d'oiseau (borne haute).
- **Zoom agglomération (niveau 2, en cours)** : Grenoble-Alpes-Métropole (+ 2 agglomérations à choisir) avec
  la marche réelle sur le réseau OpenStreetMap (V2), le modèle et l'optimiseur.

## Livrables

| Livrable | Où |
|---|---|
| Code | `src/`, `app/`, `scripts/`, `tests/` |
| Slides | `slides/` (en préparation) |
| Sources | [`docs/sources.md`](docs/sources.md) (généré par le téléchargement) + [`SOURCES.md`](SOURCES.md) |
| Méthode, éthique | [`docs/methodologie.md`](docs/methodologie.md), [`docs/ethique.md`](docs/ethique.md) |

## Structure du dépôt

```
config/          settings.yaml (zone d'étude, CRS, rayon de marche, poids des modes), costs.yaml (coûts sourcés)
src/ingest/      téléchargement, collecte de l'historique Citiz, contrôles, zone, population, offre (par ville)
src/national/    niveau 1 France entière (carreaux, offre, accessibilité, agrégats, classement, fichiers appli)
src/features/    accessibilité V1 / V2 (réseau piéton OSM)
src/model/       modèle LightGBM « où Citiz s'installe » (docs/modele.md)
src/optim/       coûts, optimiseur (glouton + ILP HiGHS), recommandations par ville
src/common/      configuration, outils géographiques
app/             application Streamlit (France entière, Nantes, Grenoble, validation)
scripts/         build_all (commande unique par ville), exports partagés, données de démo, comparatif des villes
fabric/          notebook Microsoft Fabric (ingestion)
docs/            méthodologie, éthique, sources, guide de récupération des données
slides/          présentation
tests/           pytest
data/            NON versionné : raw/ (brut), processed/<ville>/ et processed/national/ (nettoyé), share/ (exports)
```

## Installation

Python 3.12 ou plus (testé sous 3.14.2, Windows).

```bash
git clone https://github.com/hillzeealex/hackathon-mobility-citiz.git
cd hackathon-mobility-citiz
python -m venv .venv
.venv\Scripts\activate             # Windows   (Linux / Mac : source .venv/bin/activate)
pip install -r requirements.txt    # versions exactes testées : requirements-lock.txt
pytest -q                          # vérifie l'installation
```

## Données

Le dossier `data/` n'est **jamais** versionné. Guide complet (commandes, tailles, durées) :
[`docs/RECUPERER_LES_DONNEES.md`](docs/RECUPERER_LES_DONNEES.md).

```bash
# 1. Télécharger (≈ 7 Go ; reprend là où il s'est arrêté) ; OSM des régions des villes zoomées
python src/ingest/download_all.py --osm region --osm-region rhone-alpes pays-de-la-loire
python src/ingest/check_data.py --deep        # rapport : data/raw/check_report.md

# 2. France entière (≈ 5 à 8 min, pic mémoire ≈ 1,5 Go), puis le modèle (≈ 2,5 min)
python -m src.national.build_all
python -m src.model.features
python -m src.model.train

# 3. Villes zoomées (villes dans config/settings.yaml, section cities) : Grenoble ≈ 15 s, Nantes ≈ 35 s
python -m scripts.build_all --ville grenoble     # V1 + V2, fichiers de l'appli
python -m scripts.build_all --ville nantes       # V1, population desservie, recommandations (modèle requis)

# 4. Exports partageables (CSV Excel, GPKG QGIS, cartes HTML, zips) -> data/share/
python scripts/export_share.py
```

Pour collecter l'historique d'usage des stations Citiz (à laisser tourner) :
`python src/ingest/collect_gbfs_status.py --interval 5`.

### Données partagées (sans rien installer)

- **Zips de données nettoyées** : Release GitHub `donnees-v1` (Grenoble ≈ 2 Mo, France entière ≈ 20 Mo,
  agrégats seulement), ou `data/share/` après l'export.
- **Dictionnaire des données** : [`data/share/DICTIONNAIRE_DONNEES.md`](data/share/DICTIONNAIRE_DONNEES.md).
- **Cartes HTML** (double-clic) : `data/share/carte_apercu.html` (Grenoble),
  `data/share/france/carte_france_departements.html` (France).

## Lancer l'application

```bash
streamlit run app/app.py
```

Barre latérale « Vue » : **France entière** (carte par département / EPCI, classement, zoom département),
**Nantes Métropole** (carte d'accès, population desservie par arrêt et station, recommandations Citiz sous budget),
**Grenoble** (ville exemple). Onglet **Validation** : test à l'aveugle du modèle à Grenoble et comparaison
vol d'oiseau / marche réelle. L'appli ne lit que des données réelles précalculées (`scripts.build_all`,
`src.national.build_all`, `src.model.train`).

## Notebook Fabric

`fabric/01_ingestion.ipynb` tourne dans Microsoft Fabric : les écritures Spark/Delta et les chemins
`/lakehouse/...` ne marchent pas en local.

## Règles du dépôt

- Ne jamais commiter `data/` (sauf le dictionnaire et les cartes HTML de moins de 5 Mo), ni `.venv/`, ni de secret.
- Un commit par étape logique ; `pytest` doit passer avant chaque push.
- Travail par branche + Pull Request vers `main`.
