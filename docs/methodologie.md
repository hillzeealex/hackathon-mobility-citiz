# Méthodologie

Document vivant : chaque phase du pipeline y documente ses choix, ses formules et ses limites.
Paramètres : `config/settings.yaml` ; coûts et impact : `config/costs.yaml` ; sources : `docs/sources.md`.

## 1. Périmètre d'étude

**Grenoble-Alpes-Métropole** (EPCI 200040715) : 49 communes, 450 608 habitants (recensement 2023), 543 km²,
d'après ADMIN EXPRESS COG 2026 (IGN). Choix motivé en phase 1 :

- forte densité Citiz (188 stations, 41,7 pour 100 000 hab., la plus élevée des grandes agglomérations) ;
- GTFS urbain TAG sans anomalie au validateur transport.data.gouv.fr ;
- les quatre types d'offre présents (TC, vélo, trottinette, Citiz) ;
- relief marqué : la différence entre distance à vol d'oiseau et distance de marche y est un enjeu réel.

## 2. Population au carreau de 200 m

### Source et rattachement

Carreaux **Filosofi 2021** (INSEE, 200 m). Un carreau est rattaché à la zone et à une commune selon la
position de son **centroïde** : un carreau à cheval sur une limite n'est compté qu'une fois.

### Calage sur le recensement

Filosofi ne compte que les **ménages fiscaux ordinaires**. Les personnes en logement collectif n'y figurent
pas : résidences étudiantes, internats, foyers, EHPAD, casernes, établissements pénitentiaires. Sur la
métropole, Filosofi totalise 406 039 individus contre 450 608 au recensement 2023, soit −10 %.

Or ces publics, en particulier les **étudiants**, sont une cible directe de l'autopartage. On cale donc la
population de chaque carreau sur le total communal du recensement :

    pop_calee(carreau) = ind(carreau) × population_recensement(commune) / Σ ind(carreaux de la commune)

- `pop_calee` sert à **toutes** les couvertures et à tous les indicateurs.
- `ind` (Filosofi brut) est conservé pour comparaison.
- La répartition intra-communale reste celle de Filosofi. Limite : à l'intérieur d'une commune, les
  résidents en logement collectif sont répartis comme les ménages ordinaires, et non localisés sur les
  résidences.

Ratio de calage (recensement / Filosofi) par commune. Médiane 1,04 ; global 1,11.

| Commune | Recensement 2023 | Filosofi 2021 | Ratio |
|---|---:|---:|---:|
| Mont-Saint-Martin | 93 | 68 | 1,38 |
| Varces-Allières-et-Risset | 8 542 | 6 768 | 1,26 |
| **Saint-Martin-d'Hères** | 37 695 | 30 106 | **1,25** |
| Saint-Martin-le-Vinoux | 6 078 | 5 128 | 1,19 |
| Vaulnaveys-le-Bas | 1 398 | 1 186 | 1,18 |
| Sarcenas | 261 | 224 | 1,16 |
| **Grenoble** | 156 140 | 135 064 | **1,16** |
| La Tronche | 6 424 | 5 564 | 1,15 |
| … | | | |
| Saint-Paul-de-Varces | 2 218 | 2 446 | 0,91 |
| Saint-Pierre-de-Mésage | 784 | 917 | 0,85 |
| Bresson | 663 | 802 | 0,83 |

Lecture :

- **Saint-Martin-d'Hères (1,25)** : le campus universitaire et ses résidences étudiantes.
- **Grenoble (1,16)** : étudiants, foyers et résidences.
- **La Tronche (1,15)** : CHU et résidences étudiantes.
- **Varces (1,26)** : vraisemblablement la maison d'arrêt et le quartier militaire, des logements
  collectifs hors Filosofi. Ces résidents ne sont pas une cible d'autopartage : le calage les répartit à
  tort sur la commune (limite assumée, effet local).
- Les **ratios inférieurs à 1** concernent de petites communes. Ils viennent du rattachement par centroïde
  (des carreaux de bordure sont attribués à la commune voisine) et de l'écart de date (2021 / 2023).
- Table complète : `data/processed/population_calage_communes.csv`.

### Secret statistique

- 2 006 carreaux comptent moins de 11 ménages. Leurs valeurs sont des estimations INSEE (`i_est_200 = 1`),
  qui ne sont pas forcément entières.
- Ils sont **utilisés dans les calculs**, mais **jamais affichés isolément**. L'affichage public se fait à
  l'IRIS.

### Motorisation

Part des ménages sans voiture = 1 − (ménages avec au moins une voiture / ménages), d'après le recensement 2023,
logement par IRIS. Le centroïde du carreau est rattaché à l'IRIS (contours IGN 2026), puis à la valeur IRIS 2023.

| Cas | Carreaux |
|---|---:|
| Jointure IRIS réussie | 2 544 / 2 552 carreaux de communes irisées (**99,7 %**) |
| Repli sur la commune (IRIS sans ménage, ex. « Polygone ») | 8 |
| Commune non découpée en IRIS : valeur communale (feuille « COM non irisées ») | 1 733 |
| Sans valeur | 0 |

Aucun écart de découpage IRIS 2023 / 2026 n'a été observé sur la métropole.

## 3. Offre de mobilité

Table unifiée `offer.parquet` : un point par (arrêt ou station, mode). L'offre est chargée sur la
**zone + 800 m**, pour que les carreaux en limite voient les arrêts situés juste de l'autre côté. Les
candidats et l'affichage restent limités à la zone.

### Transports en commun (GTFS)

- **Réseaux :** TAG (bus et tram), téléphérique de la Bastille, Cars Région Isère, SNCF (TER et TGV).
- **Lignes exclues :** les lignes de covoiturage M covoit' (offre non collective).
- **Passages par jour :** comptés pour un **mardi type**, celui des 8 prochaines semaines couvertes qui a
  le plus de courses. Cela évite les vacances scolaires : le 3/11/2026 est retenu, après la Toussaint.
  Les courses décrites par fréquence (`frequencies.txt`, ex. téléphérique toutes les 5 min) sont
  converties en départs réels.
- **Corrections de typage :**
  - `route_type = 5` (tram à câble), utilisé par erreur pour le téléphérique, est classé en téléphérique ;
  - les arrêts SNCF « OCECar » (autocars de substitution sur des lignes typées train) sont classés en bus.
- **Limite liée au jour type :** le 3/11/2026, la section sud de la ligne Grenoble-Gap (Pont-de-Claix,
  Vif, Jarrie, Saint-Georges-de-Commiers) n'est desservie que par des autocars de substitution. Ces gares
  y apparaissent comme arrêts de bus.

### Mobilités partagées (GBFS)

- **Citiz :** 169 points (stations publiques). L'emplacement interne « DEMOBOX (Réservé Citiz) » est exclu.
- **Voi :** 685 zones de stationnement obligatoire, communes aux vélos et aux trottinettes. Chaque zone
  donne un point « vélo » et un point « trottinette ».
- **Pas de vélo en libre-service à stations fixes à Grenoble.** Métrovélo est un service de location en
  agence. La « station vélo » est donc exclue des candidats par défaut.
- **Flux exclu :** « Dott France », qui duplique les flux Dott locaux.

### Dédoublonnage

Les points d'un **même mode** distants de moins de 40 m sont fusionnés (150 m pour le train : dans les
grandes gares, les quais TER et TGV sont éloignés). Méthode : composantes connexes du graphe « distance
< seuil ». Les passages et les capacités sont additionnés.

| Mode | Avant | Après |
|---|---:|---:|
| Bus | 1 659 | 1 022 |
| Tram | 168 | 124 |
| Train | 5 | 4 |
| Citiz | 188 | 169 |

Statistiques complètes : `data/processed/offer_dedup_stats.csv`.

## 4. Accessibilité à 5 minutes à pied

### Couverture : qui atteint quoi en 5 minutes ?

On construit une seule **matrice de couverture creuse** C, avec une ligne par carreau habité et une colonne
par point d'offre. C(i, j) = 1 si le point d'offre j est à 5 minutes à pied du centroïde du carreau i,
soit **400 m** à 4,8 km/h. Elle est réutilisée par tous les indicateurs, le modèle et l'optimiseur.

- **V1 « buffer »** : distance à vol d'oiseau ≤ 400 m. Rapide, mais elle ignore les détours (rivières,
  voies ferrées, relief, îlots fermés).
- **V2 « réseau »** : distance de marche ≤ 400 m sur le réseau piéton OpenStreetMap. Le réseau est
  construit à partir de l'extrait Geofabrik local et découpé sur la zone + 800 m. La distance compte le
  rabattement du centroïde et du point d'offre sur la voie la plus proche.

**Réseau piéton** (`python -m src.features.network`, 98 s) : extrait `rhone-alpes-latest.osm.pbf` du
19/10/2026, filtre piéton d'osmnx (`network_type="walk"`) ; une autorisation piétonne explicite
(`foot=yes/designated/permissive`) l'emporte sur `access=no/private` et sur `highway=cycleway`. Voies découpées
aux intersections, plus grande composante connexe : 75 221 voies, 141 360 arêtes, 7 472 km.
Rabattement médian : 18 m pour les centroïdes de carreaux, 2 m pour les points d'offre.

**Comparaison V1 / V2 à Grenoble** (4 285 carreaux habités, 2 691 points d'offre, `data/processed/access_comparaison.json`) :

| Indicateur (population calée) | V1 vol d'oiseau | V2 marche réelle | Écart |
|---|---:|---:|---:|
| Au moins une option à 5 min | 96,4 % | 89,2 % | −7,2 pts |
| Au moins un arrêt de TC | 95,5 % | 83,5 % | −12,0 pts |
| Une station Citiz à 5 min | 53,0 % | 39,7 % | −13,3 pts |
| Options pondérées par habitant | 16,9 | 9,4 | V1 surestime de 80 % |
| Paires carreau × point couvertes | 27 823 | 13 670 | V1 surestime de 104 % |

- 32 400 habitants sont « couverts » en V1 mais n'ont aucune option à 5 min de marche réelle.
- Toutes les paires V2 sont incluses dans la V1 (contrôle de cohérence). La V2 ne retrouve le nombre de paires de la V1
  qu'avec un rayon de **560 m** : sinuosité effective ≈ 1,4, rabattements compris, cohérente avec les facteurs
  de détour urbains habituels (1,2 à 1,4). À 600 m, 13 % des paires V1 restent hors d'atteinte : coupures
  (Isère, Drac, voies ferrées, rocade, îlots fermés).
- La surestimation se concentre dans le centre dense (cartes `docs/figures/acces_v1_buffer.png`,
  `acces_v2_reseau.png`, `acces_v1_moins_v2.png`) : l'écart **en options** est le plus fort là où l'offre est dense ;
  l'écart **en couverture** (au moins une option) touche surtout les franges.
- **Conséquence pour le niveau 1** : les chiffres France (V1) sont des bornes hautes. À Grenoble, la part de
  population sans option passe de 3,6 % à 10,8 % (×3) ; l'extrapolation nationale du biais attend les deux
  autres agglomérations zoomées (formes urbaines différentes).

### Indicateur principal : options accessibles

Pour chaque carreau i :

    N(i) = Σ_j C(i, j) × w(j)

w(j) est le **poids du point d'offre j** (paramètres de `config/settings.yaml`) :

| Offre | Poids |
|---|---|
| Bus | 1 |
| Tram | 2 |
| Train | 3 |
| Citiz | 1,5 |
| Vélo, trottinette en **free-floating** (zone Voi) | **0,5 par mode et par zone** (`free_floating_weight`) : sans ce poids réduit, les ~700 zones Voi écrasent le reste de la carte |
| Facteur de fréquence (TC uniquement) | × clip(passages par jour / 100 ; 0,25 ; 2). Un bus toutes les 10 min sur 16 h vaut ×1 ; un bus 5 fois par jour vaut ×0,25 |

N(i) est le nombre d'options (pondérées) qu'**un habitant du carreau i** atteint en 5 minutes à pied.
C'est la **carte d'accueil** de l'application.

**Agrégation à l'IRIS, rapportée à l'habitant :** moyenne pondérée par la population calée P(i).

    N(IRIS) = Σ_i P(i) × N(i) / Σ_i P(i)

C'est le nombre moyen d'options accessibles **par habitant** de l'IRIS.

**Exemple.** Un IRIS compte deux carreaux.

- **Carreau A** : 300 habitants. À 5 minutes : un arrêt de tram (300 passages par jour, facteur plafonné
  à 2, soit w = 2 × 2 = 4) et deux zones Voi (2 zones × 2 modes × 0,5 = 2). N(A) = **6**.
- **Carreau B** : 100 habitants. Un arrêt de bus peu fréquent (50 passages par jour, facteur 0,5,
  soit w = 0,5). N(B) = **0,5**.
- **IRIS** : (300 × 6 + 100 × 0,5) / 400 = **4,6** options par habitant. Le carreau B, moins peuplé,
  pèse moins dans la moyenne.

### Indicateur secondaire : 2SFCA (offre rapportée à la demande)

Le 2SFCA (*two-step floating catchment area*) mesure la **concurrence** entre habitants pour une offre
limitée. Il est calculé **spécifiquement pour les véhicules Citiz** :

1. Pour chaque station j : R(j) = V(j) / Σ_i C(i, j) × P(i), soit les véhicules disponibles par habitant
   desservi. V(j) est le nombre de véhicules de la station (capacité GBFS déclarée ; moyenne observée par
   l'historique si celui-ci devient exploitable).
2. Pour chaque carreau i : A(i) = 1 000 × Σ_j C(i, j) × R(j), en véhicules Citiz accessibles pour 1 000
   habitants.

Un A(i) faible alors qu'une station est proche signale une **saturation** : la station dessert beaucoup
d'habitants pour peu de véhicules. A(i) servira de **variable du modèle** et de **critère de
l'optimiseur** (renforcer une zone saturée, ou en desservir une nouvelle). Dans l'application, c'est une
**couche optionnelle**.

**Exemple.** Trois carreaux et deux stations.

| | Carreau A (300 hab.) | Carreau B (100 hab.) | Carreau C (500 hab.) |
|---|---|---|---|
| Station S1, 3 véhicules | ✓ | ✓ | |
| Station S2, 2 véhicules | | ✓ | ✓ |

- R(S1) = 3 / (300 + 100) = 0,0075 véhicule par habitant.
- R(S2) = 2 / (100 + 500) ≈ 0,0033 véhicule par habitant. S2 est plus saturée.
- A(A) = 1 000 × 0,0075 = **7,5** véhicules pour 1 000 habitants.
- A(B) = 1 000 × (0,0075 + 0,0033) = **10,8**. B profite des deux stations.
- A(C) = 1 000 × 0,0033 = **3,3**. C a une station, mais saturée.
- **Contrôle (conservation)** : 300 × 7,5 + 100 × 10,8 + 500 × 3,3 ≈ 5 000 = 1 000 × 5 véhicules.
  Chaque véhicule est réparti exactement une fois entre les habitants qu'il dessert.

La même formule appliquée à toute l'offre pondérée, w(j) au lieu de V(j), donne un 2SFCA « toutes options »
en options pour 1 000 habitants, calculé pour comparaison.

Limite : seule la demande des habitants de la zone est comptée. Un point d'offre de la bande tampon de
800 m, qui dessert aussi des habitants hors métropole, voit sa demande sous-estimée et son R(j) surestimé.

## 5. Niveau 1 : France entière (accessibilité V1)

Chaîne complète : `python -m src.national.build_all`. Elle s'exécute en ≈ 5 min, avec un pic mémoire de
1,6 Go sur un portable de 8 Go. Les mesures détaillées sont dans `data/processed/national/mesures.json`.

### Méthode

1. **Carreaux.** 2 324 577 carreaux Filosofi (métropole, Martinique, Réunion). Le centroïde se déduit de
   l'identifiant INSEE (coin sud-ouest + 100 m) : on ne lit pas les polygones. Commune, IRIS et calage sur
   le recensement suivent les mêmes règles qu'à Grenoble, département par département. Population calée :
   67,42 millions d'habitants, égale au recensement des départements couverts.
2. **Offre.** 547 GTFS (12 en erreur, 51 expirés) et tous les GBFS :
   - **dédoublonnage** par territoire et par mode, à 40 m (150 m pour le train) ;
   - **passages** sommés au sein d'une même source, puis **maximum entre sources**, car les flux
     régionaux agrégés (OÙRA, Nouvelle-Aquitaine, Destineo, Korrigo…) reprennent les réseaux locaux ;
   - **flux expiré** : mardi type pris dans sa propre période de validité ;
   - **volume** : 577 107 points bruts, 235 855 après fusion ;
   - **cohérence** : au moins autant d'arrêts que l'agrégat national data.gouv.fr (418 jeux), sauf en
     Guyane.
3. **Couverture V1** : KD-tree, rayon de 400 m.
   - La demande D(j) d'un point d'offre est calculée sur tout le territoire, ce qui rend le 2SFCA exact
     aux limites de départements.
   - La couverture et les indicateurs sont calculés département par département.
4. **Agrégats** : IRIS (48 891), commune, EPCI (1 239) et département, moyennes pondérées par la
   population.

### Résultats France (V1)

| Indicateur | Valeur |
|---|---:|
| Population sans aucune option à 400 m | 24,9 % |
| Population à 400 m d'un arrêt de transport en commun | 74,9 % |
| Population à 400 m d'une station Citiz | 5,6 % |
| Options pondérées accessibles (moyenne par habitant) | 7,2 |

Ces valeurs sont des **bornes hautes**. La V1 mesure à vol d'oiseau ; le biais par rapport à la marche
réelle est mesuré sur les agglomérations zoomées (niveau 2) puis extrapolé.

### Classement des EPCI : potentiel Citiz

Le classement porte sur les 276 EPCI de plus de 50 000 habitants. Score = moyenne de trois
rangs-percentiles :

- **densité vécue** : moyenne des densités des carreaux, pondérée par la population, plutôt que
  population / surface, qui pénalise les EPCI comprenant forêts et montagnes ;
- **part de ménages sans voiture** ;
- **autopartage existant pour 10 000 habitants** : moins il y en a, meilleur est le score.

Le risque de vol de véhicules (SSMSI, 2023-2025) est affiché à côté et dans une variante pénalisée
(`score_avec_risque` = score − 0,25 × rang du risque). **Il n'entre pas dans le score principal.**

**Limite majeure : l'autopartage existant est mal connu en open data.** Hors Citiz, seuls Clem, Rémi,
Optymo et Leo&Go publient un GBFS exploitable. Getaround, Zity, Free2Move, Communauto, Ubeeqo, Marcel…
sont absents. Le critère mesure donc « peu d'autopartage *visible* » ; il avantage à tort les grandes
villes.

### Couverture des DROM

| Territoire | Population au carreau (Filosofi) | Offre de transport (GTFS) | GBFS | Indicateurs par habitant |
|---|---|---|---|---|
| Martinique (972) | ✅ 11 222 carreaux | ✅ 3 719 arrêts de bus | 4 stations d'autopartage | ✅ |
| La Réunion (974) | ✅ 14 773 carreaux | ✅ 5 620 arrêts de bus, téléphérique ; 49 points « tram » (erreur de type chez le producteur : pas de tram à la Réunion) | 36 zones de trottinettes | ✅ |
| Guadeloupe (971) | ❌ absent de Filosofi | ✅ 1 282 arrêts de bus | 17 zones de trottinettes | ❌ offre seule |
| Guyane (973) | ❌ absent de Filosofi | ⚠️ 267 arrêts (l'agrégat national en compte 557) | aucun | ❌ offre seule |
| Mayotte (976) | ❌ absent de Filosofi | ⚠️ 50 arrêts (absent de l'agrégat national) | aucun | ❌ offre seule |

Il n'y a aucune station Citiz dans les DROM. Le classement des EPCI ne couvre donc, pour les DROM, que la
Martinique et la Réunion.

### Secret statistique (niveau national)

77 % des carreaux (1,8 million, surtout ruraux) comptent moins de 11 ménages : ils ne sont pas affichés.
Les carreaux affichés regroupent **82 % de la population**. Les autres restent comptés dans les agrégats
IRIS.
