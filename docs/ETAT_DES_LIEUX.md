# État des lieux — branche `data-pipeline`

Audit du 20/10/2026, commit `d40a2c1`. **Tout ce qui suit a été vérifié dans le code ou par une commande lancée
le 20/10** (pytest, reconstruction complète, démarrage de Streamlit, lecture des fichiers produits).
« Non vérifié » signale ce qui n'a pas pu l'être. Aucun code n'a été modifié pendant l'audit.

Légende : ✅ fait et testé · 🟡 écrit mais non testé, partiel ou avec un défaut connu · ❌ prévu mais absent.

---

## 1. Inventaire du code

### `src/common/`

| Fichier | Rôle | Entrées → sorties | Statut |
|---|---|---|---|
| `config.py` | Lecture de `config/settings.yaml`, chemins ancrés à la racine | yaml → dict, `raw()`, `processed()` | ✅ `test_config.py` (3) |
| `geo.py` | Dédoublonnage spatial par mode (composantes connexes), filtre des coordonnées aberrantes | points → points fusionnés | ✅ `test_geo.py` (8) |

### `src/ingest/` (téléchargement et zoom Grenoble)

| Fichier | Rôle | Entrées → sorties | Statut |
|---|---|---|---|
| `download_all.py` | Télécharge GTFS, GBFS, INSEE, IGN, OSM, SSMSI ; génère `docs/sources.md` (clés masquées) | internet → `data/raw/`, `manifest.csv`, `docs/sources.md` | ✅ exécuté le 19/10 ; `test_ingest.py` (CLI, chemins, masquage) |
| `check_data.py` | Rapport ✅/⚠️/❌ sur les données brutes, option `--deep` | `data/raw/` → `check_report.md` | ✅ test sur arborescence factice |
| `collect_gbfs_status.py` | Photo des stations Citiz toutes les 5 min | GBFS → `gbfs_history/station_status_*.csv` | ✅ tourne (PID 20920 depuis le 19/10 14:04) ; test CLI seulement. ⚠️ trou de 16,5 h (veille du PC) |
| `citiz_overview.py` | Stations Citiz rattachées à leur commune / EPCI | GBFS Citiz + geo.api → `citiz_stations.csv`, `citiz_by_epci.csv` | 🟡 exécuté le 19/10, aucun test |
| `archives.py` | Localise / extrait les GeoPackages IGN (.7z) et Filosofi (.zip) | archives → chemins `.gpkg` | 🟡 utilisé partout, pas de test direct |
| `zone.py` | Périmètre d'étude (communes de l'EPCI) | ADMIN EXPRESS → `zone.gpkg` | ✅ `select_communes` testé ; reconstruit le 20/10 (13 s) |
| `population.py` | Carreaux 200 m, calage sur le recensement, motorisation IRIS / commune | Filosofi, RP logement → `population.parquet` + rapports | ✅ `test_population.py` (4) ; reconstruit (2 s) |
| `offer.py` | Offre unifiée de la zone (GTFS mardi type, GBFS, dédoublonnage) | `data/raw/gtfs`, GBFS → `offer.parquet` + rapports | 🟡 fonctions testées (`test_offer.py`, 7) ; **bug de périmètre GTFS** (§5) ; reconstruit (23 s) |

### `src/features/` (accessibilité Grenoble)

| Fichier | Rôle | Entrées → sorties | Statut |
|---|---|---|---|
| `network.py` | Réseau piéton depuis le PBF local, découpé sur zone + 800 m | `rhone-alpes-latest.osm.pbf` → `cache/walk_edges.parquet` | ✅ filtre, découpage, graphe testés ; construit le 19/10 (cache réutilisé le 20/10) |
| `accessibility.py` | Couverture V1 (vol d'oiseau) et V2 (Dijkstra borné + rabattements), poids, 2SFCA | carreaux, offre, réseau → matrices creuses, indicateurs | ✅ `test_accessibility.py` (6) |
| `build_access.py` | Chaîne V1/V2 Grenoble, agrégat IRIS, comparaison, 6 cartes PNG | population, offre, réseau → `access_cells/iris.parquet`, `coverage_v1/v2.npz`, `access_comparaison.json`, `docs/figures/` | 🟡 exécuté le 20/10 (9 s) ; pas de test de bout en bout ; **réécrit `population.parquet`** (§5) |

### `src/national/` (niveau 1 France entière)

| Fichier | Rôle | Entrées → sorties | Statut |
|---|---|---|---|
| `common.py` | Territoires, CRS, mesure du temps et de la mémoire | — | ✅ `bbox_territory` testé |
| `cells.py` | 2,3 M carreaux Filosofi, rattachement département / commune / IRIS | Filosofi, ADMIN EXPRESS, IRIS → `national/cells/<dep>.parquet` | ✅ partiel : `centroids_from_id` testé ; exécuté le 20/10 |
| `offer.py` | 547 GTFS + GBFS, dédoublonnage par territoire | `data/raw/gtfs`, GBFS → `national/offer.parquet` | 🟡 aucun test unitaire ; exécuté le 20/10 (GTFS lus depuis le cache du 19/10) |
| `access.py` | Couverture V1, 2SFCA (dont Citiz), agrégats IRIS / commune / EPCI / département | cellules + offre → `national/access/`, `agg_*.parquet` | ✅ couverture et agrégation testées |
| `ranking.py` | Classement des EPCI (potentiel Citiz, risque de vol SSMSI) | agrégats, offre, SSMSI → `classement_epci.parquet/csv` | 🟡 `security_rates` testé ; `build_ranking` non testé |
| `app_files.py` | Fichiers légers WGS84 pour l'appli | agrégats → `national/app/` | 🟡 pas de test (la vue nationale, elle, est testée) |
| `build_all.py` | Chaîne complète du niveau 1 | — | 🟡 exécuté le 20/10 : 315 s, pic 1,5 Go ; pas de test |

### `src/optim/` et `src/model/`

| Fichier | Rôle | Entrées → sorties | Statut |
|---|---|---|---|
| `optim/costs.py` | Coût total par équipement (capex + opex sur l'horizon), CO2 évité | `config/costs.yaml` → €, t CO2/an | ✅ `test_costs.py` (8) |
| `optim/optimize.py` | Glouton et ILP (PuLP + HiGHS) de couverture maximale sous budget, équité, usage | `Problem` → liste priorisée | ✅ `test_optimize.py` (8), **sur instance synthétique seulement** |
| `model/` | Modèle prédictif | — | ❌ **dossier vide** (`__init__.py` seul) |

### `app/`

| Fichier | Rôle | Entrées | Statut |
|---|---|---|---|
| `app.py` | Appli Streamlit : sélecteur France / zoom, 4 onglets de zoom, optimiseur interactif | contrat `app/data.py` | ✅ sur données **factices** (`test_app.py`) ; ❌ zoom sur données réelles |
| `national.py` | Vue France : carte département / EPCI, classement, zoom département | `national/app/` | ✅ sur données **réelles** (`test_app.py`) |
| `data.py` | Contrat de données du zoom (6 fichiers) | — | ✅ |
| `ui.py` | Couleurs, vue carte, formats | — | ✅ (via `test_app.py`) |

### `scripts/`

| Fichier | Rôle | Sorties | Statut |
|---|---|---|---|
| `export_share.py` | Exports partageables Grenoble + France, dictionnaire, cartes HTML, zips | `data/share/` | ✅ `test_export_share.py` (9) ; exécuté le 19/10 |
| `make_demo_data.py` | Données factices au format du contrat | `data/processed/demo/` | ✅ (utilisé par `test_app.py`) |
| `compare_cities.py` | Comparatif sécurité des villes candidates | `comparatif_villes_securite.csv` | 🟡 exécuté le 19/10, pas de test ; sa docstring cite `docs/choix_ville.md`, **absent** |
| `build_all.py` | Chaîne complète zoom → fichiers de l'appli | — | ❌ **absent** (mais cité par le message d'erreur de `app/app.py`) |

### `tests/` (12 fichiers, 68 tests)

`test_accessibility` 6 · `test_app` 3 · `test_config` 3 · `test_costs` 8 · `test_env` 2 · `test_export_share` 9 ·
`test_geo` 8 · `test_ingest` 4 · `test_national` 6 · `test_offer` 7 · `test_optimize` 8 · `test_population` 4.
Non couverts : `build_access`, `national/offer`, `build_ranking`, `app_files`, `citiz_overview`, `compare_cities`,
`collect_gbfs_status` (au-delà de la CLI), lecture du PBF.

### Hors de notre code

- `fabric/01_ingestion.ipynb` (équipe) : téléchargement dans un Lakehouse Fabric, tables Delta (arrêts, GBFS,
  Filosofi, communes / IRIS). **Indépendant de notre pipeline** ; non exécuté (non vérifié : nécessite Fabric).
- `SOURCES.md` (équipe), `hackathon_mobility-project.pdf` (sujet).

---

## 2. Couverture du sujet

| Exigence | Code | Statut |
|---|---|---|
| **Obj. 1** · V1 buffer 400 m | `features/accessibility.py::coverage_buffer` ; `national/access.py::coverage` | ✅ Grenoble + France |
| **Obj. 1** · V2 réseau piéton | `features/network.py::load_walk_edges`, `accessibility.py::coverage_network` | ✅ Grenoble seulement |
| **Obj. 1** · indicateur par habitant (options pondérées) | `accessibility.py::indicators`, `offer_weights` ; agrégat IRIS dans `build_access.py` | ✅ |
| **Obj. 1** · 2SFCA | `indicators` (`acces_1000`) ; Citiz : `national/access.py` (`citiz_1000`) | 🟡 générique ✅ ; **2SFCA Citiz absente à Grenoble** et absente de l'appli |
| **Obj. 1** · carte du plus froid au plus chaud dans l'appli | `app/national.py` (réel), `app/app.py` onglet 1 | 🟡 France réelle ✅ ; zoom **factice** |
| **Obj. 2** · offre par type | `access_comparaison.json` (`part_pop_couverte_par_type`), `options_by_type` | 🟡 calculé, pas dans l'appli (réel) |
| **Obj. 2** · population desservie par arrêt / station | contrat `offer_served.parquet` (`pop_desservie`, `pop_seule_option`) | ❌ **calculé seulement dans `make_demo_data.py`** (factice) |
| **Obj. 3** · modèle prédictif (variables, cible) | `src/model/` | ❌ absent. Cible décidée : véhicules par station. Historique Citiz inexploitable (12 changements en 34 photos) |
| **Obj. 3** · validation spatiale | — | ❌ |
| **Obj. 3** · test à l'aveugle Grenoble | — | ❌ |
| **Obj. 3** · coûts | `config/costs.yaml`, `optim/costs.py` | ✅ fourchettes sourcées (ADEME, etc.) |
| **Obj. 3** · optimiseur glouton et ILP | `optim/optimize.py::greedy`, `ilp`, `optimize` | ✅ sur instance synthétique ; ❌ sur données réelles |
| **Obj. 3** · candidats | — | ❌ **aucun générateur** (seulement factices) |
| **Obj. 3** · liste priorisée | `optimize.py` (`OUTPUT_COLUMNS`), export CSV dans `app.py` | 🟡 fonctionne sur données factices |
| **Éthique** · CO2 | `costs.py::co2_avoided_t_per_year`, affiché dans l'appli ; `docs/ethique.md` §4 | ✅ (affiché sur données factices) |
| **Éthique** · équité | `optimize.py` (`priorite_equite`, curseur dans l'appli) ; `docs/ethique.md` §3 | 🟡 mécanisme ✅ ; **`priorite_equite` jamais calculé sur données réelles** |
| **Éthique** · secret statistique | seuil 11 ménages (`settings.privacy`), arrondi à 5 (`export_share.py::round_counts`), masquage appli | ✅ testé |
| **Éthique** · risque de vol en surcoût | taux SSMSI dans `ranking.py` (`score_avec_risque`) | 🟡 **critère de classement seulement** ; aucun surcoût dans `costs.yaml` / l'optimiseur |
| **Éthique** · non-stigmatisation | `docs/ethique.md` §2 ; taux de vols par commune masqués < 10 000 hab. | ✅ |
| **Livrable** · code | dépôt, PR #3 | ✅ |
| **Livrable** · slides | `slides/README.md` (plan) | ❌ deck absent |
| **Livrable** · sources | `docs/sources.md` (généré), `SOURCES.md`, `docs/sources_hypotheses.md` | ✅ |
| **Ville** · Grenoble (validation) | zone, population, offre, V1/V2 | 🟡 accessibilité ✅ ; appli, modèle, optimiseur réels ❌ |
| **Ville** · Nantes (densification) | — | ❌ rien de spécifique (seulement dans le classement : rang 58, 23 stations Citiz) ; extrait OSM `pays-de-la-loire` non téléchargé |
| **Ville** · Nice (implantation) | — | ❌ rien de spécifique (rang 1, 0 station Citiz) ; extrait OSM PACA non téléchargé |
| **Niveau France** | `src/national/`, vue appli, exports, Release `donnees-v1` | ✅ V1 seulement (bornes hautes) |
| **Multi-villes** | `config/settings.yaml` ne décrit qu'**une** `study_area` ; sorties non suffixées par ville | ❌ à prévoir avant Nantes / Nice |

---

## 3. Vérifications concrètes (20/10/2026)

### Tests

`pytest` : **68 tests, 68 réussis, 0 échec, 0 ignoré** (28 s).

### Reconstruction complète

| Étape | Commande | Durée | Résultat |
|---|---|---:|---|
| Zone Grenoble | `python -m src.ingest.zone` | 13 s | ✅ 49 communes |
| Population | `python -m src.ingest.population` | 2 s | ✅ 4 285 carreaux, 450 608 hab. |
| Offre | `python -m src.ingest.offer` | 23 s | ✅ mais **2 716 points (2 691 le 19/10)**, voir §5 |
| Accessibilité V1/V2 | `python -m src.features.build_access` | 9 s | ✅ (réseau lu en cache) |
| France entière | `python -m src.national.build_all` | **315 s** | ✅ pic mémoire 1,5 Go |

Étapes longues du niveau 1 : carreaux (≈ 2 min au total), dédoublonnage de l'offre (45 s), classement (30 s),
IRIS par département (22 s). Les 547 GTFS étaient **en cache** : une première exécution ajoute leur lecture
(86 s mesurées le 19/10, non revérifié aujourd'hui). La construction du réseau piéton (98 s le 19/10) n'a pas été
relancée (cache). Il **n'existe pas** de commande unique qui reconstruit tout (`scripts/build_all.py` absent).

### Démarrage de l'appli

`streamlit run app/app.py` : serveur prêt (`/_stcore/health` → 200), aucune exception (`AppTest`).

| Vue / onglet | Données |
|---|---|
| France entière (carte, classement, zoom département) | **réelles** (`data/processed/national/app/`) |
| Zoom · 1 Carte d'accès | **factices** — bandeau « Données FACTICES » |
| Zoom · 2 Offre et population desservie | **factices** |
| Zoom · 3 Où investir ? (optimiseur) | **factices** (calcul réel de l'optimiseur sur candidats factices) |
| Zoom · 4 Méthode et limites | texte statique |

Raison : aucun des 6 fichiers du contrat (`cells`, `iris`, `offer_served`, `candidates`, `coverage.npz`, `meta.json`)
n'existe dans `data/processed/` ; aucun code ne les produit à partir des données réelles.

### Fichiers de `data/processed/` (date = dernière écriture)

| Fichier / dossier | Taille | Date |
|---|---:|---|
| `zone.gpkg` | 516 Ko | 20/10 09:53 |
| `population.parquet` | 440 Ko | 20/10 09:53 |
| `population_rapport.json`, `population_calage_communes.csv` | 5 Ko | 20/10 09:53 |
| `offer.parquet` | 212 Ko | 20/10 09:53 |
| `offer_gtfs_report.csv`, `offer_dedup_stats.csv` | 37 Ko | 20/10 09:53 |
| `access_cells.parquet` | 396 Ko | 20/10 09:53 |
| `access_iris.parquet` | 144 Ko | 20/10 09:53 |
| `coverage_v1.npz`, `coverage_v2.npz` | 32 + 24 Ko | 20/10 09:53 |
| `access_comparaison.json` | 4 Ko | 20/10 09:53 |
| `cache/` (réseau piéton, tables logement) | 33 Mo | 19/10 14:41 – 16:50 |
| `citiz_stations.csv`, `citiz_by_epci.csv` | 336 Ko | 19/10 14:07 |
| `comparatif_villes_securite.csv` | 4 Ko | 19/10 15:05 |
| `demo/` (6 fichiers factices) | 225 Ko | 19/10 14:31 |
| `national/` (959 fichiers : `cells/`, `access/`, `app/`, `gtfs_stops/`, agrégats, classement) | 497 Mo | fichiers réécrits le 20/10 09:56 – 09:59 |
| journaux `rebuild_*.log`, `access.log` | < 120 Ko | 20/10 |

---

## 4. Chiffres clés

**R** = recalculé le 20/10 par la reconstruction ; **A** = ancien rapport, non recalculé aujourd'hui.

| Chiffre | Valeur | Source | |
|---|---|---|---|
| Population Grenoble-Alpes-Métropole (calée) | 450 608 hab. (Filosofi brut 406 039) | `population_rapport.json` | R |
| Carreaux habités Grenoble | 4 285 (2 006 < 11 ménages) | `population_rapport.json` | R |
| Jointure IRIS motorisation | 99,7 % | `population_rapport.json` | R |
| Points d'offre Grenoble | **2 716** (2 691 le 19/10) | `offer.parquet`, `rebuild_src.ingest.offer.log` | R |
| Au moins une option à 5 min, V1 → V2 | 96,4 % → **89,2 %** | `access_comparaison.json` | R |
| Au moins un arrêt de TC, V1 → V2 | 95,5 % → 83,5 % | `access_comparaison.json` | R |
| Station Citiz à 5 min, V1 → V2 | 53,0 % → **39,7 %** | `access_comparaison.json` | R |
| Options pondérées / habitant, V1 → V2 | 17,02 → 9,45 (V1 surestime de 80 %) | `access_comparaison.json` | R |
| Habitants couverts en V1 mais pas en V2 | 32 137 | `access_comparaison.json` | R |
| Part du free-floating dans les options (poids 0,5 / 1) | 32,7 % / 42,2 % | `access_comparaison.json` | R |
| Réseau piéton | 75 221 voies, 141 360 arêtes, 7 472 km | `cache/walk_edges_meta.json` (19/10) | A |
| Population France (carreaux Filosofi) | 67 416 412 | `national/agg_rapport.json` | R |
| France : sans aucune option à 5 min (V1) | 24,9 % | `national/agg_rapport.json` | R |
| France : arrêt de TC à 5 min (V1) | 74,9 % | `national/agg_rapport.json` | R |
| France : station Citiz à 5 min (V1) | 5,6 % | `national/agg_rapport.json` | R |
| France : options moyennes (V1) | 7,21 | `national/agg_rapport.json` | R |
| Offre nationale | 577 107 → 235 855 points ; 547 GTFS (12 illisibles, 51 expirés) | `national/offer_rapport.json` | R (GTFS lus en cache du 19/10) |
| Classement : Nice Côte d'Azur | rang 1/276, score 0,878, 0 station Citiz, vols 6,6 ‰ | `national/classement_epci.parquet` | R |
| Classement : Nantes Métropole | rang 58, score 0,641, 23 stations / 37 véhicules Citiz, 11,8 % de la population à 5 min de Citiz, vols 13,6 ‰ | idem | R |
| Classement : Grenoble-Alpes-Métropole | rang 61, score 0,636, 168 stations / 444 véhicules, vols 19,1 ‰ | idem | R |
| Historique Citiz collecté | 54 942 lignes, 34 photos, 1 617 stations, **12 changements** de disponibilité | `data/raw/gbfs_history/` (lu le 20/10) | R |
| Taille des zips de la Release `donnees-v1` | Grenoble 2,3 Mo, France 20,2 Mo | GitHub Release | A (19/10) |
| Données brutes | 6,5 Go | `du data/raw` (19/10) | A |

`docs/methodologie.md` cite encore les chiffres du 19/10 (2 691 points, 9,4 options en V2) : écart de moins de 1 %,
à remettre à jour après correction du périmètre GTFS.

---

## 5. Écarts, dette technique, bugs connus

**`docs/decisions.md` n'existe pas** (ni dans le dépôt, ni sur aucune branche distante), pas plus que
`docs/choix_ville.md`. Les décisions ont été prises en conversation ; celles qui ne sont pas (ou pas entièrement)
dans le code :

| Décision / annonce | État réel |
|---|---|
| Cible du modèle = véhicules par station | ❌ aucun modèle |
| 2SFCA Citiz : couche optionnelle, variable du modèle, critère de l'optimiseur | ❌ à Grenoble (seulement au niveau national) |
| Candidats par défaut : station Citiz, arrêt de bus, zone free-floating ; pas de station vélo | 🟡 dans `settings.yaml`, mais aucun générateur de candidats |
| Comparaison des cartes avec / sans poids free-floating | ✅ (`acces_v2_sans_poids_ff.png`) |
| Estimer le biais national de la V1 à partir des zooms | ❌ une seule ville zoomée |
| Risque de vol (dégradation) en surcoût | ❌ seulement un critère de classement |
| `scripts/build_all.py` (chaîne unique) | ❌ absent, pourtant cité par l'appli |
| Slides Marp, paragraphe Fabric | ❌ |
| `docs/choix_ville.md` (comparatif des villes avec risque de vol) | ❌ (données dans `comparatif_villes_securite.csv` et le classement) |

**Bugs et dette**

1. **Périmètre GTFS de Grenoble non maîtrisé** (`src/ingest/offer.py`, boucle sur `raw("gtfs").glob("*.zip")`) :
   les mots-clés `study_area.gtfs_keywords` ne servent qu'au téléchargement. Depuis le téléchargement national,
   12 flux contribuent au lieu de 6, dont **Flixbus et BlaBlaCar (longue distance)**, Zou! PACA, la desserte des
   stations de ski et l'agrégat OURA (doublon des cars Isère, absorbé par le dédoublonnage). Résultat : +25 points,
   chiffres dépendants du contenu de `data/raw/gtfs/`.
2. **Jour type glissant** : « mardi le plus chargé des 8 prochaines semaines » à partir de la date du jour → les
   fréquences changent d'un jour à l'autre (ex. téléphérique : jour type 20/10 aujourd'hui). Pas de date figée.
3. **`build_access.py` réécrit `population.parquet`** (filtre `pop_calee > 0`) : effet de bord sur une entrée.
4. **Multi-villes impossible en l'état** : une seule `study_area`, sorties `data/processed/*.parquet` non suffixées.
5. **Historique Citiz** : trou de 16,5 h (PC en veille) et 12 changements seulement → inutilisable comme cible ;
   confirme la cible « véhicules par station ».
6. **Autopartage hors Citiz quasi absent de l'open data** (Getaround, Zity, Free2Move…) → critère du classement biaisé.
7. **DROM** : pas de population au carreau en Guadeloupe, Guyane, Mayotte ; offre guyanaise incomplète
   (267 arrêts) ; 49 points « tram » erronés à La Réunion.
8. **V1 nationale = borne haute** : à Grenoble elle surestime les options de 80 % ; pas encore de correction.
9. **Couverture de tests** : chaînes de bout en bout (`build_access`, `build_all`, `build_ranking`, `app_files`) non testées.
10. **Dépendances inutilisées** : `osmnx` et `pandana` sont dans `requirements.txt` mais non importés (le réseau passe par pyogrio).
11. **Fabric** : le notebook de l'équipe n'est pas relié au pipeline Python ; aucune décision documentée.

---

## 6. Reste à faire (priorisé)

Estimations pour une personne, données déjà téléchargées.

### Indispensable pour la démo

| # | Tâche | Estimation |
|---|---|---:|
| 1 | Corriger le périmètre GTFS (filtre par mots-clés / exclusion longue distance) et figer la date du jour type ; relancer Grenoble | 1 h |
| 2 | `scripts/build_all.py` : produire les 6 fichiers réels du contrat de l'appli pour Grenoble (cellules V2, IRIS, `offer_served` avec population desservie / seule option, `priorite_equite`) | 2 h 30 |
| 3 | Générateur de candidats (stations Citiz, arrêts de bus, zones free-floating) + matrice de couverture V2 candidats | 2 h |
| 4 | Modèle prédictif : véhicules par station Citiz (≈ 1 600 stations France), variables autour de la station (population, densité, ménages sans voiture, revenus, offre TC, équipements BPE), validation spatiale par EPCI, test à l'aveugle Grenoble, SHAP | 4 h |
| 5 | Optimiseur sur données réelles (usage prédit, équité, CO2), liste priorisée exportable | 1 h 30 |
| 6 | Slides (Marp) : problème, carte, V1/V2, recommandations, éthique | 3 h |

### Important

| # | Tâche | Estimation |
|---|---|---:|
| 7 | Multi-villes : config par ville, sorties suffixées | 1 h 30 |
| 8 | Nantes (densification) et Nice (implantation) : extraits OSM (pays-de-la-loire, PACA), zone, population, offre, V2 | 2 h + téléchargement |
| 9 | Biais V1/V2 sur 3 villes → facteur de correction indicatif pour la France | 1 h |
| 10 | 2SFCA Citiz à Grenoble : couche de l'appli + variable du modèle + critère de l'optimiseur | 1 h |
| 11 | Risque de vol en surcoût (scénario de coût par zone) | 1 h |
| 12 | `docs/decisions.md` et `docs/choix_ville.md` ; mise à jour de la méthodologie | 1 h |
| 13 | Décision Fabric + paragraphe (ou branchement du notebook sur nos sorties) | 1 à 2 h |

### Bonus

| # | Tâche | Estimation |
|---|---|---:|
| 14 | Tests de bout en bout des chaînes (`build_access`, `build_all`, `build_ranking`) | 2 h |
| 15 | Afficher dans la vue France un avertissement chiffré « V1 surestime » | 30 min |
| 16 | Nettoyer les DROM (tram Réunion, Guyane) | 30 min |
| 17 | Retirer `osmnx` / `pandana` de `requirements.txt` | 10 min |
| 18 | Exploiter l'historique Citiz si le signal devient suffisant (≥ 24 h continues) | 1 h |

**Total indispensable ≈ 14 h ; important ≈ 9 h ; bonus ≈ 4 h.**
