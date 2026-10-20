# Conception : accès par carreau, modèle, Nantes et optimisation sous budget dans Fabric

Date : 20/10/2026 · Branche : `fabric-acces-modele-nantes` · Statut : **à valider avant tout code**

## 1. Pourquoi

Le sujet demande trois choses : une carte de l'accès à 5 minutes à pied par habitant (objectif 1), les arrêts et
stations avec la population que chacun dessert (objectif 2), et surtout une **liste priorisée d'emplacements sous
contrainte de budget**, appuyée sur un **modèle prédictif** et un **coût par type d'équipement** (objectif 3, le cœur).
Le sujet recommande Microsoft Fabric pour le traitement, le ML et la visualisation.

Aujourd'hui, ces briques existent en deux morceaux qui ne se parlent pas :

- **En local** (branche `data-pipeline`) : accessibilité V1 / V2, calage de la population sur le recensement,
  Nantes avec Marguerite, population desservie, optimiseur glouton et ILP. Pas de modèle.
- **Dans Fabric** (PR #9) : Bronze → Silver → Gold sur la France, avec un score Gold à 8 critères dont 4 restent
  inconnus sans fichiers manuels, et des candidats « centres de carreaux » sans optimisation.

Ce document décrit comment réunir les deux **dans Fabric**, jusqu'à un rapport Power BI, en reprenant les formules
déjà écrites et vérifiées en local plutôt qu'en inventer de nouvelles.

### État de l'espace Fabric « Hackathon Citz » (lu le 20/10/2026, API Fabric)

- **Bronze** : run complet `ada2d1f5…` le 20/10 à 08:53 UTC, **France entière** (`DEPARTEMENTS = []`, aucune
  limite GTFS/GBFS). Silver a terminé sur le même run.
- **Gold** : seulement `gold_communes_prioritaires` et `gold_sites_candidats`, écrites par le notebook
  `gold_kpis(1)` (« Gold minimal », 16 cellules), **absent du dépôt**. Le Gold à 8 critères (`gold_notebook`, passé
  au noyau Python) a tourné à 12:30 UTC : 50 communes, 5 000 candidats, complétude 45 % partout, score identique pour
  tous les points d'une commune (critère population saturé à 3 000 habitants). Modèle `rapport_gold_notebook` et
  rapport du même nom créés dessus.
- **Rapport `rapport_national`** (format PBIR, une page) : carte Azure Maps des sites candidats colorée par
  `profil_carte`, et tableau des communes prioritaires, sur le modèle Direct Lake `rapport_national`.
- **Seconde chaîne `*_nantes`** (notebooks `bronze_notebook`, `silver_notebook`) : malgré son nom,
  `bronze_nantes` est un second run **France entière** (`ca5ddc70…`, 10:12 UTC, `DEPARTEMENTS = []`), doublon du
  Bronze national. `silver_nantes` est **inachevé** (4 tables sur 13, pas de `pipeline_run`), `gold_nantes` vide.
  Le modèle `Citiz_Mobilite_Nantes` lit `bronze_nantes` (tables `communes` et `transport_catalogue` seulement).
  Proposition : abandonner cette chaîne et filtrer Nantes dans les notebooks Gold de la chaîne nationale.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**

1. Carte d'accès **par carreau** (indicateur N(i), formule de `docs/methodologie.md`) pour la France (V1) et
   pour Nantes Métropole (V2, marche réelle), agrégée à l'IRIS pour l'affichage.
2. Population **calée sur le recensement 2023 à l'IRIS** (au lieu du total communal).
3. Offre de Nantes complète : GTFS Naolib et autres réseaux retenus, GBFS (Citiz, vélos, trottinettes),
   **stations Marguerite** (open data Nantes Métropole).
4. Population desservie par arrêt / station, et population dont c'est la seule option (objectif 2).
5. Modèle « où Citiz s'installerait » entraîné sur la France, testé à l'aveugle sur Grenoble.
6. Optimisation sous budget à Nantes : glouton et ILP, trois types d'équipement (station Citiz, arrêt de bus,
   station de vélos), coûts de `config/costs.yaml`.
7. Projections Omphale (INSEE, par département, 11 scénarios, table Bronze `projections_omphale_dep`) : facteur
   2023 → 2035 du scénario central, fourchette par les scénarios population haute / basse, affichés par commune
   (valeur du département) et en « population desservie à l'horizon 2035 ». La structure par âge n'est publiée que
   pour 2018 et 2070 : pas d'évolution par âge à 2035. À Nantes, toutes les communes sont dans le même département : le facteur ne change pas le classement des
   emplacements, il ne doit pas être présenté comme un critère de choix.
8. Rapport Power BI sur le Lakehouse Gold : carte, desserte, validation du modèle, liste priorisée avec un
   curseur de budget.

**Non-objectifs**

- Pas de recommandation à Grenoble ni à Nice (Grenoble : exemple et test à l'aveugle ; Nice : contre-exemple
  documenté).
- Pas de V2 (réseau piéton) hors Nantes et Grenoble.
- Pas de prédiction de réservations ou de chiffre d'affaires : la cible est la présence d'une station Citiz.
- Pas de création de ligne de bus (seulement un arrêt ajouté sur une ligne existante, comme dans `costs.yaml`).
- Pas de remplacement du score Gold à 8 critères : il reste tel quel, à côté.

**Anti-objectifs** (ce qui ferait échouer le projet même si tout « tourne »)

- Afficher un carreau de moins de 11 ménages, ou des effectifs non arrondis dans un export partagé.
- Présenter la V1 comme une vraie distance de marche (elle surestime les options de 80 % à Grenoble).
- Présenter la probabilité du modèle comme une demande mesurée.
- Utiliser un chiffre du livre blanc Citiz 2026 (non vérifié).
- Un pipeline qui ne tourne que sur le portable d'un membre : tout doit se relancer depuis Fabric.

## 3. Contraintes

- **Runtime Python Fabric** (pas Spark), comme les trois notebooks existants : pandas, `deltalake`, `scipy`,
  `geopandas`/`pyogrio`/`shapely`. Mêmes conventions : `RUN_ID`, table `pipeline_run`, `read_table` /
  `write_table`, table `gold_qualite`, une source absente reste inconnue (jamais zéro).
- Les notebooks restent au format JSON compact de Fabric, réimportables tels quels.
- **Secret statistique** (décisions du 19/10, toujours valables) : aucun carreau de moins de 11 ménages affiché,
  agrégation à l'IRIS, effectifs arrondis à 5 dans les exports partagés, taux de vols par commune seulement à partir
  de 10 000 habitants.
- Rayon : 400 m (5 min à 4,8 km/h). Poids des offres et facteur de fréquence : ceux de `config/settings.yaml`
  (bus 1, tram 2, train 3, Citiz 1,5, autopartage 1,5, free-floating 0,5 par mode et par zone, fréquence
  × clip(passages/jour / 100 ; 0,25 ; 2)).
- Jour type GTFS figé au mardi 17/11/2026 ; exclusion covoiturage, Flixbus, BlaBlaCar.
- Coûts et CO2 : `config/costs.yaml` (ADEME et sources publiques), horizon 3 ans, scénario « moyenne ».
- Getaround : aucune donnée ouverte, limite documentée.

## 4. Ce qui est décidé

### 4.1 Où vit le code

Nouveaux notebooks Fabric, à la suite des trois existants, dans l'espace « Hackathon Citz » :

| Notebook | Rôle | Lit | Écrit |
|---|---|---|---|
| Bronze (existant, complété) | + contours IRIS, + population RP 2023 à l'IRIS, + stations Marguerite, + projections Omphale 2021-2070, + extrait OSM Pays de la Loire et Rhône-Alpes (piétons) | sources | Bronze |
| Silver (existant, complété) | + `dim_iris`, rattachement carreau → IRIS, calage IRIS, offre Marguerite dans `dim_station` | Bronze | Silver |
| `4_acces` (nouveau) | couverture V1 France, V2 Nantes et Grenoble, N(i), 2SFCA Citiz, population desservie | Silver | Gold |
| `5_modele` (nouveau) | variables, LightGBM, validations, SHAP, probabilité par carreau | Gold | Gold |
| `6_optimisation` (nouveau) | candidats Nantes, matrice de couverture, coûts, glouton + ILP par palier de budget | Gold | Gold |

**Ne pas relancer Bronze à chaque modification.** Silver et Gold relisent déjà le dernier run Bronze complet
(`pipeline_run` + filtre `_run_id`) : après une modification, on relance à partir du premier notebook modifié.
Deux ajouts à Bronze pour que ce soit vrai aussi pour les nouvelles sources :

- paramètre `SECTIONS = []` : vide = run complet comme aujourd'hui ; sinon (ex. `["iris", "marguerite"]`) Bronze
  reprend le `run_id` du dernier run complet et n'écrit que ces tables, sans retélécharger le reste ;
- fichiers lourds et stables (Filosofi, logement, historique, flux, SSMSI) mis en cache hors du dossier daté
  `Files/raw/<source>/<date>/`, pour que `skip_existing` serve aussi d'un jour à l'autre.

Le Gold actuel (`gold_kpis`) n'est pas modifié. Les formules sont **portées** depuis le code local
(`src/features/accessibility.py`, `network.py`, `served.py`, `src/optim/optimize.py`, `costs.py`), pas réécrites.

Cela remplace la décision du 20/10 « Fabric : paragraphe de justification seulement » ; `docs/decisions.md`
sera mis à jour en conséquence.

### 4.2 Population calée à l'IRIS

    pop_calee(carreau) = ind(carreau) × pop_RP2023(IRIS) / Σ ind(carreaux de l'IRIS)

- Rattachement carreau → IRIS par le **centroïde** (comme pour les communes : un carreau compté une fois).
- Repli sur le calage communal pour un IRIS sans carreau Filosofi ou une commune non découpée en IRIS.
- `ind` (Filosofi brut) conservé ; table de contrôle des ratios de calage par IRIS (comme
  `population_calage_communes.csv`).

### 4.3 Carte d'accès par carreau

- **N(i) = Σ_j C(i, j) × w(j)** : options pondérées atteintes en 5 minutes par un habitant du carreau i.
- **V1** (vol d'oiseau, KD-tree 400 m) pour tous les carreaux habités de France ; **V2** (marche sur le réseau
  piéton OSM, Dijkstra 400 m) pour Nantes Métropole + 800 m et Grenoble.
- Affichage : **moyenne à l'IRIS pondérée par la population calée**. Le carreau ne sert qu'au calcul et au modèle.
- 2SFCA Citiz (véhicules pour 1 000 habitants), même formule et même contrôle de conservation que la méthodologie.
- Population desservie par arrêt / station et population dont c'est la seule option, synthèse par type.
- Sorties Gold : `gold_acces_carreau` (carreau, version V1/V2, N, A_citiz, couvert_<type>), `gold_acces_iris`,
  `gold_desserte_offre`.

### 4.4 Modèle

- **Cible** : pour chaque carreau habité de métropole, présence d'une station Citiz à 400 m (classification). Le
  modèle apprend où Citiz s'est installé, pas la demande pure.
- **Algorithme** : LightGBM.
- **Variables** autour du carreau : population calée et densité, ménages sans voiture (IRIS, repli commune),
  niveau de vie, N(i) hors Citiz, offre TC et fréquence, 2SFCA « toutes options ». Jamais de variable construite
  à partir des stations Citiz elles-mêmes (fuite).
- **Validation** : spatiale par réseau régional Citiz (on retire un réseau entier, on le prédit) ; **test à l'aveugle
  Grenoble** (réseau Citiz Alpes exclu de l'entraînement) ; comparaison à une baseline « densité seule » ;
  importance des variables par SHAP.
- Sorties Gold : `gold_proba_carreau`, `gold_modele_validation` (métriques par pli et baseline),
  `gold_modele_shap`.

### 4.5 Optimisation à Nantes

- **Candidats, par type** (*mon choix*) :
  - *Station Citiz* : centroïdes des carreaux habités et arrêts de TC de Nantes Métropole, sauf ceux à moins de
    400 m d'une station Citiz ou Marguerite.
  - *Arrêt de bus* : centroïdes des carreaux habités à moins de 100 m du tracé d'une ligne de bus existante
    (GTFS `shapes`, sinon segments entre arrêts consécutifs) et à plus de 400 m de tout arrêt de TC.
  - *Station de vélos* : centroïdes des carreaux habités à plus de 400 m de toute station de vélos GBFS.
- **Couverture existante par type** (*mon choix*) : `couvert_citiz` = Citiz ou Marguerite à 400 m ;
  `couvert_bus_stop` = tout arrêt de TC ; `couvert_bike_station` = station de vélos GBFS (les zones de
  free-floating ne comptent pas comme une station).
- **Gain** d'un carreau i couvert par un candidat retenu j de type t, si i n'est pas déjà couvert par le type t :

      gain_i = pop_calee_i × (1 + equite × priorite_equite_i) × usage_rel_j

  Un carreau compte au plus une fois par type (fonction objectif de `src/optim/optimize.py`, reprise telle quelle).
- **usage_rel_j** (*mon choix*) : pour une station Citiz, probabilité du modèle au candidat / moyenne de cette
  probabilité sur les candidats Citiz ; **1 pour les arrêts de bus et les stations de vélos** (pas de modèle pour
  ces types, on ne fait pas passer la probabilité Citiz pour une demande de bus).
- **Équité** (*mon choix*, formule de l'appli de démo appliquée aux données réelles) :
  `priorite_equite_i = 0,5 × (1 − min(N(i), 6) / 6) + 0,5 × (1 − rang-percentile du niveau de vie du carreau)`,
  donc dans [0, 1]. Deux scénarios calculés : `equite = 0` (population seule) et `equite = 1`.
- **Coût** : `investissement + 3 × exploitation_annuelle`, scénario « moyenne ».
- **Surcoût de risque de vol** (*mon choix*, aucun montant inventé) : pour une station Citiz dans une commune
  d'au moins 10 000 habitants dont le taux SSMSI `vol_vehicule` dépasse 10 pour 1 000 habitants
  (`THEFT_ALERT_PER_1000` du Gold), on passe `assurance_entretien` et `gestion_nettoyage_telematique` au
  scénario « haute » de `costs.yaml`. Sous 10 000 habitants, le taux n'est pas publié : pas de surcoût, et la
  ligne est marquée « risque inconnu ».
- **Paliers de budget** : de 50 000 € à 1 000 000 € par pas de 50 000 €, chaque palier × chaque scénario
  d'équité × glouton et ILP (80 résolutions, toutes petites à l'échelle de Nantes).
- **Méthodes** : glouton (meilleur ratio gain marginal / coût) et ILP de couverture maximale (PuLP + HiGHS).
- **Sorties Gold** : `gold_selection` (rang, candidat, type, coût, population nouvellement desservie, usage prédit,
  coût par habitant, budget cumulé, méthode, palier de budget), `gold_resume_optim` (glouton vs ILP par palier),
  `gold_couts` (hypothèses et sources).

### 4.6 Power BI

Modèle sémantique Direct Lake sur le Lakehouse Gold. Le rapport est montré en soutenance, donc il compte comme
un export partagé (*mon choix*) : les tables Gold gardent les valeurs exactes (Lakehouse interne), le rapport ne lit
que des tables `*_publie` où les effectifs sont arrondis à 5, où un carreau de moins de 11 ménages n'apparaît
jamais seul, et où une population desservie (par arrêt, station ou candidat) est masquée si elle repose sur moins
de 11 ménages. Le curseur de budget sélectionne un palier précalculé. Pages :

1. **France** : accès V1 par IRIS (borne haute, avertissement « V1 surestime »), classement des EPCI.
2. **Nantes, accès** : N(i) V2 par IRIS, couche 2SFCA Citiz, arrêts et stations avec population desservie.
3. **Modèle** : test à l'aveugle Grenoble, comparaison à la baseline, SHAP.
4. **Recommandations Nantes** : curseur de budget (paramètre de simulation) → liste priorisée et carte des
   emplacements, glouton ou ILP, population nouvellement desservie, CO2 évité (borne basse).

## 5. Laissé au constructeur

- Découpage exact des cellules, noms de colonnes non cités ici, ordre des contrôles qualité.
- Hyperparamètres LightGBM (valeurs par défaut raisonnables, early stopping sur la validation).
- Représentation du réseau piéton dans Fabric (graphe `scipy.sparse` comme en local).
- Visuel de carte Power BI (Azure Maps ou carte de formes) et mise en page.

## 6. Risques connus

- **Volume V1 France** dans le runtime Python : 2,3 M carreaux × ~600 000 points ; en local le pic était de 1,5 Go,
  à vérifier sur la taille de nœud Fabric.
- **Réseau piéton dans Fabric** : lecture d'un extrait OSM `.pbf` par `pyogrio` (pilote OSM de GDAL) à vérifier
  dans l'environnement Fabric.
- **Dépendances** : `lightgbm`, `shap`, `pulp` (+ HiGHS) à ajouter à l'environnement Fabric publié.
- **RP 2023 à l'IRIS** : à confirmer que le fichier est publié par l'INSEE à ce millésime, sinon RP 2022.
- **Marguerite** : jeu de Nantes Métropole mis à jour le 03/09/2024, peut-être incomplet.
