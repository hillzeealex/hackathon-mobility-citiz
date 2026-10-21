# Hackathon Mobility Citiz (Epitech × Citiz × Microsoft)

**Qui a réellement accès à une option de mobilité à 5 minutes à pied, et où faut-il en ajouter ?**

1. **Carte d'accès** : nombre d'options de mobilité (bus, tram, train, vélo, trottinette, Citiz) à 5 min
   à pied (400 m) par habitant, du plus froid au plus chaud.
2. **Offre par type** et population desservie par chaque arrêt et station.
3. **Modèle prédictif + optimiseur sous budget** : liste priorisée de nouveaux équipements à Nantes Métropole.

Le projet s'est construit en trois temps :

| Étape | Où | Ce qu'on a fait |
|---|---|---|
| 1. Prototype | En local (Python, `src/`) | Méthode mise au point et vérifiée : accès V1 / V2, modèle, optimiseur, appli Streamlit |
| 2. Industrialisation | Microsoft Fabric (`fabric/`) | Même méthode portée en notebooks, architecture médaillon, pipeline orchestré |
| 3. Restitution | Power BI (`fabric/powerbi/`) | Rapport de 7 pages en Direct Lake sur le lakehouse `gold` |

Villes : **Nantes Métropole** porte toutes les recommandations ; **Grenoble** sert d'exemple de méthode (V1 / V2)
et de test à l'aveugle du modèle ; **Nice** est un contre-exemple documenté. Détail : [`docs/decisions.md`](docs/decisions.md).

---

## 1. En local : le prototype

On a d'abord tout développé et vérifié en Python sur un portable (≈ 7 Go de données brutes, 2,3 M carreaux de
200 m, moins de 10 minutes pour la France entière, pic mémoire 1,5 Go).

| Brique | Code | En bref |
|---|---|---|
| Ingestion | `src/ingest/` | 547 flux GTFS, tous les GBFS, Filosofi 200 m, recensement, IRIS, OSM ; contrôles (`check_data.py`) |
| France entière | `src/national/` | Accès **V1** (vol d'oiseau, borne haute) par carreau, agrégats IRIS / commune / EPCI / département |
| Accès par ville | `src/features/` | Accès **V2** : marche réelle sur le réseau piéton OSM (Dijkstra 400 m), population desservie |
| Modèle | `src/model/` | LightGBM « présence Citiz à 400 m », validation par région, test à l'aveugle Grenoble, SHAP ([`docs/modele.md`](docs/modele.md)) |
| Optimisation | `src/optim/` | Glouton + ILP (HiGHS), 3 types d'équipement, coûts sourcés (`config/costs.yaml`), poids d'équité |
| Appli | `app/` | Streamlit : France, Nantes, Grenoble, onglet Validation |

Méthode complète : [`docs/methodologie.md`](docs/methodologie.md). Chiffres du pipeline local :
[`docs/chiffres_cles.md`](docs/chiffres_cles.md). **Chiffres officiels de la soutenance : ceux de Fabric**,
[`docs/chiffres_officiels.md`](docs/chiffres_officiels.md).

Pourquoi V1 et V2 : le vol d'oiseau surestime fortement l'accès (+80 % d'options à Grenoble). Les chiffres
officiels de Nantes sont donc en V2 (marche réelle).

---

## 2. Dans Microsoft Fabric : le pipeline

Le code local a ensuite été **porté** (pas réécrit) dans l'espace Fabric « Hackathon Citz », pour que tout se
relance depuis Fabric et plus depuis le portable d'un membre. Runtime **Python** (pas Spark) : le volume ne justifie
pas un cluster, et les traitements clés (Dijkstra, ILP, LightGBM) sont des bibliothèques Python.

### Architecture médaillon : bronze → silver → gold

```
 Sources ouvertes          BRONZE                  SILVER                       GOLD                     POWER BI
 (GTFS, GBFS, INSEE,  ──▶  données brutes     ──▶  données propres        ──▶  tables métier       ──▶  Direct Lake
  IGN, OSM, SSMSI,         telles que reçues        normalisées, contrôlées      prêtes à afficher        (aucun import)
  Omphale)
```

- **Bronze** : les fichiers tels que téléchargés, plus un manifeste d'ingestion. On ne les modifie jamais.
- **Silver** : données nettoyées et normalisées (codes INSEE en texte, rattachement aux communes par contour,
  dimensions `dim_arret`, `dim_station`, `dim_commune`, faits population / motorisation / délinquance) et tables
  de contrôle qualité.
- **Gold** : les résultats directement utilisables : accès par carreau, population desservie, probabilités du
  modèle, liste priorisée sous budget, coûts, projections de population.

### Les étapes

| Ordre | Activité du pipeline | Notebook | Lit | Écrit | Rôle | Durée |
|---|---|---|---|---|---|---|
| 1 | `data_retrieval` | `bronze_notebook` | sources ouvertes | `bronze` | Téléchargement de toutes les sources, France entière | ≈ 1 h |
| 2 | `data_preparation_1` | `silver_notebook` | `bronze` | `silver` | Codes INSEE normalisés, carreaux et arrêts rattachés aux communes, contrôles | 2 à 3 min |
| 3 | `data_preparation_2` | `acces_notebook` | `silver`, `bronze` | `gold` | Objectifs 1 et 2 : accès V1 France, **V2 Nantes**, population desservie | 1 à 2 min |
| 4 | `data_preparation_3` | `modele_notebook` | `gold`, `silver` | `gold` | Modèle LightGBM, validation par région et à l'aveugle sur Grenoble, importance des variables | 2 à 3 min |
| 5 | `data_preparation_4` | `optimisation_notebook` | `gold`, `silver` | `gold` | Objectif 3 : liste priorisée sous budget à Nantes, projections de population, tables de rentabilité | 6 à 7 min |
| 6 | `data_refinement` | `gold_notebook` | `silver` | `gold` | Indicateurs par commune et score de présélection à 8 critères | 4 à 5 min |

### Le pipeline `citiz_pipeline`

Le pipeline de données Fabric enchaîne ces six activités. Un clic sur **Exécuter** relance toute la chaîne depuis
Silver en **15 à 20 minutes**.

- **Bronze désactivé par défaut** : `data_retrieval` est compté comme réussi sans tourner. On ne le réactive que
  pour rafraîchir les sources (≈ 1 h).
- **Nouvelles tentatives automatiques** : chaque activité réessaie 2 fois, à 2 minutes d'intervalle, si Fabric
  refuse d'ouvrir la session parce que la capacité est saturée (`TooManyRequestsForCapacity`).
- **Paramètres** : les noms de lakehouses (`BRONZE`, `SILVER`, `GOLD`) passés par le pipeline remplacent ceux des
  notebooks. Après une modification dans l'éditeur, cliquer sur **Enregistrer**, sinon l'ancienne version tourne.
- **Suivi** : chaque exécution est visible dans l'onglet Surveiller (étapes, durées, statut, cellule en erreur).
- Une capacité chargée ralentit aussi les notebooks : le 20/10, l'optimisation a pris 28 min au lieu de 7.
  Ne pas relancer juste avant une démo.

La définition du pipeline vit dans l'espace Fabric, pas dans le dépôt. Guide complet de l'espace (tables Gold,
dépannage, limites) : [document « Microsoft Fabric : la chaîne de données Citiz »](https://claude.ai/artifact/D5SvzVHSMucpERt1UgLB4J).

**Traçabilité des runs** : chaque notebook écrit l'identifiant de son run (`_run_id`) dans ses tables et dans la
table `pipeline_run`. L'étape suivante relit le **dernier run complet** de l'étape précédente : après une
modification, on relance seulement à partir du premier notebook modifié. Ne jamais relancer une partie de
`bronze_notebook` seule (voir [`fabric/README.md`](fabric/README.md)).

**Fabric est la source des chiffres officiels** ([`docs/chiffres_officiels.md`](docs/chiffres_officiels.md)).
Nantes y est calculée en **marche réelle** : le réseau piéton OpenStreetMap est lu et découpé dans `acces_notebook`, et
l'optimisation couvre les candidats à pied. Le diagnostic retrouve celui du pipeline local (80,7 % des habitants avec
au moins une option à 5 min, contre 80,6 % ; 19,0 % à 5 min d'un autopartage dans les deux cas).

**Aucune donnée de délinquance n'entre dans les calculs** (choix de l'équipe : ne pas pénaliser un territoire sur ses
statistiques de vols). Pour Nantes, le modèle donne une probabilité prédite sans avoir vu la région, afin de ne pas
dévaloriser les zones que Citiz ne couvre pas encore.

**Le modèle de prédiction reste à vol d'oiseau (V1), même pour Nantes.** Il apprend sur les 2,3 M carreaux de toute
la France, où le réseau piéton n'est pas calculé : ses variables (population, transports, vélos à 400 m et 1 km) et
sa cible (station Citiz à 400 m) sont donc mesurées en ligne droite. Lui donner des variables de Nantes en marche
réelle fausserait ses prédictions : sur les 6 739 carreaux de Nantes, le vol d'oiseau compte en moyenne 1,9 fois plus
d'options que la marche réelle. Ce choix pèse peu sur les recommandations : le modèle ne sert qu'à **départager** les
emplacements (sa probabilité est rapportée à la moyenne des candidats), et l'ordre des carreaux reste proche entre
V1 et V2 (corrélation de rang de 0,82). Les **habitants gagnés et la couverture sont comptés en marche réelle**. Un
modèle entièrement en V2 demanderait le réseau piéton des 12 régions Citiz (voir Prochaines étapes).

Import des notebooks, dépendances et détails : [`fabric/README.md`](fabric/README.md).

---

## 3. Le rapport Power BI

`fabric/powerbi/citiz_acces_investissement/` est versionné au format texte (PBIP) :

- **Modèle sémantique** (`semantic_model/`, format TMDL) : 21 tables `gold_*` en mode **Direct Lake**. Les données
  sont lues directement dans OneLake, sans import ni rafraîchissement planifié : dès que le pipeline réécrit `gold`,
  le rapport est à jour.
- **Rapport** (`report/`, format PBIR) : 8 pages, cartes Azure Maps, segments, tableaux et cartes de chiffres.
- **Simulation de rentabilité** : les tables `gold_saisie_*` (investissement, véhicules, recettes, charges, durée
  d'amortissement…) servent de paramètres de saisie libre ; le calcul se fait dans les mesures DAX, rien n'est
  enregistré.

| Page | Contenu |
|---|---|
| 1 · France : accès à 5 min | Carte des communes par options par habitant (V1, borne haute) |
| 2 · Nantes : diagnostic | Carte d'accès V2, chiffres clés |
| 3 · Nantes : qui est desservi | Population desservie par arrêt et station, seule option |
| 4 · Nantes : potentiel prédit | Probabilité du modèle par carreau, validation Grenoble, importance des variables |
| 5 · Nantes : où investir | Curseur de budget, liste priorisée, équipements, glouton / ILP, équité, horizon de population |
| 6 · Rentabilité d'une station | Simulation à partir des valeurs saisies |
| 7 · Méthode et limites | Hypothèses, V1 / V2, secret statistique |
| 8 · Limites | Limites du modèle de prédiction, des données, des hypothèses et des choix |

Pour un autre espace Fabric : remplacer l'identifiant du lakehouse dans
`semantic_model/definition/expressions.tmdl` (expression `DirectLake - Gold`), puis ouvrir le `.pbir` dans
Power BI Desktop ou synchroniser l'espace avec Git.

---

## 4. Prochaines étapes

- **Modèle en marche réelle** : calculer le réseau piéton OpenStreetMap des 12 régions Citiz pour apprendre le modèle
  en V2 (plusieurs Go à télécharger, plusieurs heures de calcul).
- **MLflow** dans Fabric : enregistrer chaque entraînement du modèle (métriques, version) dans une expérience.
- **Planification** de `citiz_pipeline` (par exemple chaque semaine) pour une chaîne qui tourne seule.
- Collecte GBFS planifiée chez Citiz pour constituer un historique d'usage (cible plus fine que la présence).

---

## Lancer le projet en local

### Installation

Python 3.12 ou plus (testé sous 3.14.2, Windows).

```bash
git clone https://github.com/hillzeealex/hackathon-mobility-citiz.git
cd hackathon-mobility-citiz
python -m venv .venv
.venv\Scripts\activate             # Windows   (Linux / Mac : source .venv/bin/activate)
pip install -r requirements.txt    # versions exactes testées : requirements-lock.txt
pytest -q                          # vérifie l'installation
```

### Données

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

**Données partagées sans rien installer** : Release GitHub `donnees-v2` (Grenoble ≈ 3,3 Mo, Nantes ≈ 2,6 Mo,
France ≈ 20 Mo), dictionnaire [`data/share/DICTIONNAIRE_DONNEES.md`](data/share/DICTIONNAIRE_DONNEES.md), cartes
HTML `data/share/carte_apercu.html` (Grenoble) et `data/share/france/carte_france_departements.html` (France).

### Application

```bash
streamlit run app/app.py
```

Barre latérale « Vue » : **France entière**, **Nantes Métropole** (carte d'accès, population desservie,
recommandations sous budget), **Grenoble** (ville exemple), onglet **Validation** (test à l'aveugle du modèle,
vol d'oiseau / marche réelle). L'appli ne lit que des données réelles précalculées. Scénario de démo :
[`docs/DEMO.md`](docs/DEMO.md).

## Structure du dépôt

```
config/          settings.yaml (zone d'étude, CRS, rayon de marche, poids des modes), costs.yaml (coûts sourcés)
src/ingest/      téléchargement, collecte de l'historique Citiz, contrôles, zone, population, offre (par ville)
src/national/    niveau France entière (carreaux, offre, accessibilité, agrégats, classement, fichiers appli)
src/features/    accessibilité V1 / V2 (réseau piéton OSM), population desservie
src/model/       modèle LightGBM « où Citiz s'installe »
src/optim/       coûts, optimiseur (glouton + ILP HiGHS), recommandations par ville
src/common/      configuration, outils géographiques
app/             application Streamlit
scripts/         build_all (commande unique par ville), exports partagés, chiffres clés, comparatif des villes
fabric/          notebooks Fabric (bronze, silver, accès, modèle, optimisation, gold) et rapport Power BI (powerbi/)
docs/            méthodologie, modèle, éthique, décisions, sources, chiffres clés, démo
slides/          présentation et images
tests/           pytest
data/            NON versionné : raw/, processed/<ville>/, processed/national/, share/
```

## Documentation

| Sujet | Fichier |
|---|---|
| Méthode (indicateurs, V1 / V2, 2SFCA, calage) | [`docs/methodologie.md`](docs/methodologie.md) |
| Modèle | [`docs/modele.md`](docs/modele.md) |
| Chiffres officiels (Fabric) | [`docs/chiffres_officiels.md`](docs/chiffres_officiels.md) |
| Chiffres du pipeline local | [`docs/chiffres_cles.md`](docs/chiffres_cles.md) |
| Décisions | [`docs/decisions.md`](docs/decisions.md) |
| Éthique, secret statistique | [`docs/ethique.md`](docs/ethique.md) |
| Sources | [`docs/sources.md`](docs/sources.md), [`SOURCES.md`](SOURCES.md) |
| Conception Fabric | [`docs/superpowers/specs/2026-10-20-fabric-acces-modele-nantes-design.md`](docs/superpowers/specs/2026-10-20-fabric-acces-modele-nantes-design.md) |

## Règles du dépôt

- Ne jamais commiter `data/` (sauf le dictionnaire et les cartes HTML de moins de 5 Mo), ni `.venv/`, ni de secret.
- Un commit par étape logique ; `pytest` doit passer avant chaque push.
- Travail par branche + Pull Request vers `main`.
