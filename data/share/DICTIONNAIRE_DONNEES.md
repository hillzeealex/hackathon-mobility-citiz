# Dictionnaire des données — Hackathon Mobility (Epitech × Citiz) : Grenoble, Nantes et France entière

Généré par `scripts/export_share.py` le 2026-10-20. Méthode détaillée : `docs/methodologie.md` ; sources : `docs/sources.md` ; éthique : `docs/ethique.md`.

## Contenu

| Dossier / fichier | Contenu |
|---|---|
| `data/share/` | Grenoble-Alpes-Métropole : carreaux, IRIS, communes, offre (+ accessibilité quand elle est calculée) |
| `data/share/nantes/` | Nantes Métropole : mêmes tables préfixées `nantes_`, offre avec population desservie, recommandations Citiz |
| `data/share/france/` | France entière : **agrégats** par département, EPCI et commune, classement des EPCI |
| `hackathon_grenoble_donnees_propres_AAAAMMJJ.zip` | tout `data/share/` (hors `france/`) + ce dictionnaire + méthodologie |
| `hackathon_nantes_donnees_propres_AAAAMMJJ.zip` | tout `data/share/nantes/` + ce dictionnaire + méthodologie, modèle, décisions, chiffres clés |
| `hackathon_france_donnees_propres_AAAAMMJJ.zip` | tout `data/share/france/` + ce dictionnaire + méthodologie, éthique |

## Formats

| Format | Pour qui | Détails |
|---|---|---|
| `.csv` | Excel | séparateur `;`, UTF-8 avec BOM, virgule décimale ; colonnes `latitude`/`longitude` en WGS84 (centroïde pour les surfaces), pas de géométrie |
| `.gpkg` | QGIS | géométries complètes : Lambert-93 (EPSG:2154) pour Grenoble, WGS84 (EPSG:4326) pour la France |
| `.geojson` | web, outils en ligne | WGS84 (EPSG:4326), produit si < 50 Mo (Grenoble seulement) |
| `carte_apercu.html` | tout le monde | double-clic : carte interactive de Grenoble (connexion internet requise pour le fond de carte) |
| `france/carte_france_departements.html` | tout le monde | double-clic : carte nationale par département, un indicateur à la fois |

# Grenoble-Alpes-Métropole (ville exemple)

## Choix de nettoyage

- **Population calée** : Filosofi 2021 ne compte que les ménages fiscaux ordinaires (406 039 individus) ; chaque carreau est recalé sur la population communale du recensement 2023 (450 608) : `pop_calee = ind × ratio_calage`. Ratios par commune : `data/processed/population_calage_communes.csv` (ex. Saint-Martin-d'Hères 1,25 : campus).
- **Rattachement des carreaux** : par centroïde (un carreau en bordure n'est compté que dans une commune).
- **Secret statistique** : 2 006 carreaux de moins de 11 ménages sont utilisés dans les calculs et dans les agrégats IRIS, mais **ne figurent pas** dans population_carreaux (ni les IRIS de moins de 11 ménages dans population_iris). Pour empêcher de retrouver un carreau masqué par différence (total IRIS − carreaux affichés), les **effectifs des tables IRIS sont arrondis à 5 près** dans les exports partagés (`pop_calee`, `ind`, `men`, `men_pauv`, `population`, `menages`) ; les ratios et tous les calculs du projet utilisent les valeurs exactes. Voir `docs/ethique.md`.
- **Motorisation** : jointure IRIS réussie pour 99,7 % des carreaux des communes découpées en IRIS ; 8 replis sur la valeur communale ; 1 733 carreaux de communes non découpées en IRIS (valeur communale).
- **Dédoublonnage de l'offre** : points d'un même mode à moins de 40 m fusionnés (train : 150 m) ; bus 1706→1045, citiz 188→169, telepherique 2→2, train 9→8, tram 168→124, trottinette 697→685, velo 697→685.
- **Jour type GTFS** : mardi le plus chargé des 8 prochaines semaines couvertes par chaque réseau (2026-11-17, 2026-12-29) : évite les vacances scolaires. `frequencies.txt` converti en départs réels.
- **Zone tampon** : l'offre est chargée sur la métropole + 800 m (colonne `dans_zone`).
- **GTFS retenus** (`config/settings.yaml`, cities.grenoble.gtfs_feeds) : `horaires-theoriques-du-reseau-tag`, `reseau-interurbain-cars-region-isere-38`, `horaires-sncf`, `horaires-theoriques-du-reseau-tougo`, `horaires-theoriques-du-reseau-transport-du-pays-voironnais`, `horaires-theoriques-du-telepherique-de-la-bastille` ; exclus partout : covoiturage, Flixbus, BlaBlaCar ; jour type figé au mardi 2026-11-17.
- **Exclusions** : flux GBFS « Dott France » (doublon) ; emplacement interne « DEMOBOX (Réservé Citiz) ».
- **Corrections de typage GTFS** : `route_type = 5` du téléphérique -> téléphérique ; arrêts SNCF « OCECar » (autocars de substitution) -> bus.
- **Zones free-floating** : chaque zone de stationnement donne un point `velo` et un point `trottinette`.
- **Coordonnées** : filtrage des points (0,0) ou hors de France métropolitaine.

## zone_communes

Les communes de la métropole (périmètre d'étude).

**49 lignes** — fichiers : `zone_communes.gpkg` 0,5 Mo, `zone_communes.csv` 0,0 Mo, `zone_communes.geojson` 0,9 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom` | Nom | - | selon la table |
| `population` | Population municipale de la commune | habitants | INSEE, recensement 2023 (via ADMIN EXPRESS) |
| `date_du_recensement` | Date de référence du recensement | date | IGN, ADMIN EXPRESS COG 2026 |
| `superficie_km2` | Superficie | km² | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## population_carreaux

Population et caractéristiques socio-économiques par carreau de 200 m.

**2 279 lignes** — fichiers : `population_carreaux.gpkg` 1,0 Mo, `population_carreaux.csv` 0,5 Mo, `population_carreaux.geojson` 2,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `idcar_200m` | Identifiant INSEE du carreau de 200 m | - | INSEE, Filosofi 2021 carreaux 200 m |
| `i_est_200` | 1 = valeurs estimées par l'INSEE (carreau de moins de 11 ménages dans la source) | 0/1 | INSEE, Filosofi 2021 carreaux 200 m |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_pauv` | Ménages sous le seuil de pauvreté | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_prop` | Ménages propriétaires | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_snv` | Somme des niveaux de vie winsorisés des individus | € / an | INSEE, Filosofi 2021 carreaux 200 m |
| `log_soc` | Logements sociaux | logements | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_0_3` | Individus de 0 à 3 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_4_5` | Individus de 4 à 5 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_6_10` | Individus de 6 à 10 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_11_17` | Individus de 11 à 17 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_18_24` | Individus de 18 à 24 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_25_39` | Individus de 25 à 39 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_40_54` | Individus de 40 à 54 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_55_64` | Individus de 55 à 64 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_65_79` | Individus de 65 à 79 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_80p` | Individus de 80 ans et plus | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `ratio_calage` | Ratio population recensement 2023 / Σ Filosofi de la commune | - | calcul du projet |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `motorisation_source` | Origine de part_sans_voiture : iris, commune_non_irisee, repli_commune | - | calcul du projet |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_hab_km2` | Densité de population calée | habitants / km² | calcul du projet |
| `nom_commune` | Nom de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## population_iris

Agrégat par IRIS de TOUS les carreaux (y compris < 11 ménages) : affichage public recommandé. **Effectifs (pop_calee, ind, men, men_pauv) arrondis à 5 près** (secret statistique) ; ratios calculés sur les valeurs exactes.

**198 lignes** — fichiers : `population_iris.gpkg` 0,4 Mo, `population_iris.csv` 0,0 Mo, `population_iris.geojson` 0,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom_commune` | Nom de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `nom_iris` | Nom de l'IRIS | - | IGN, CONTOURS IRIS 2026 |
| `carreaux` | Nombre de carreaux habités agrégés | carreaux | calcul du projet |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_pauv` | Ménages sous le seuil de pauvreté | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `superficie_km2` | Superficie | km² | calcul du projet |
| `densite_hab_km2` | Densité de population calée | habitants / km² | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## offre

Tous les points d'offre de mobilité (arrêts TC, stations d'autopartage, vélos, trottinettes) sur la zone + 800 m, avec la population desservie (objectif 2).

**2 718 lignes** — fichiers : `offre.gpkg` 1,1 Mo, `offre.csv` 0,7 Mo, `offre.geojson` 1,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `id` | Identifiant : source:identifiant_d_origine:mode | - | GTFS / GBFS |
| `type` | Mode : bus, tram, train, telepherique, velo, trottinette, citiz | - | calcul du projet |
| `sous_type` | arret (TC), station (Citiz), zone_free_floating (zone de stationnement Voi) | - | calcul du projet |
| `nom` | Nom | - | selon la table |
| `source` | Jeu de données d'origine (gtfs:<jeu> ou gbfs:<jeu>) | - | transport.data.gouv.fr |
| `capacite` | Capacité déclarée (places) pour les stations GBFS | places | GBFS (transport.data.gouv.fr) |
| `passages_jour` | Passages un mardi type (TC uniquement), après fusion des quais | passages / jour | GTFS (transport.data.gouv.fr) |
| `n_fusionnes` | Nombre de points d'origine fusionnés (dédoublonnage) | points | calcul du projet |
| `ids_fusionnes` | Identifiants des points d'origine fusionnés, séparés par | | - | calcul du projet |
| `dans_zone` | Vrai si le point est dans la métropole (faux : dans la bande tampon de 800 m) | booléen | calcul du projet |
| `pop_desservie` | Habitants (population calée) à 5 min de ce point (V2 marche réelle si disponible, sinon V1) | habitants | calcul du projet |
| `pop_seule_option` | Habitants pour qui ce point est la SEULE option à 5 min | habitants | calcul du projet |
| `part_seule_option` | pop_seule_option / pop_desservie | 0-1 | calcul du projet |
| `version` | Accessibilité utilisée : v1 vol d'oiseau, v2 marche réelle | - | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## acces_carreaux

Indicateurs d'accessibilité à 5 min par carreau (V1 vol d'oiseau et V2 marche réelle).

**2 279 lignes** — fichiers : `acces_carreaux.gpkg` 0,9 Mo, `acces_carreaux.csv` 0,4 Mo, `acces_carreaux.geojson` 1,8 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `idcar_200m` | Identifiant INSEE du carreau de 200 m | - | INSEE, Filosofi 2021 carreaux 200 m |
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `n_options_v1` | Options pondérées accessibles à 400 m à vol d'oiseau | options | calcul du projet |
| `n_points_v1` | Points d'offre à 400 m à vol d'oiseau | points | calcul du projet |
| `acces_1000_v1` | Options pour 1 000 habitants (2SFCA), vol d'oiseau | options / 1 000 hab. | calcul du projet |
| `n_options_v2` | Options pondérées accessibles à 400 m de marche (réseau OSM) | options | calcul du projet |
| `n_points_v2` | Points d'offre à 400 m de marche | points | calcul du projet |
| `acces_1000_v2` | Options pour 1 000 habitants (2SFCA), marche | options / 1 000 hab. | calcul du projet |
| `n_options_v2_sans_poids_ff` | Comme n_options_v2, free-floating au poids normal du mode | options | calcul du projet |
| `n_bus_v2` | Points « bus » à 5 min de marche | points | calcul du projet |
| `n_citiz_v2` | Points « citiz » à 5 min de marche | points | calcul du projet |
| `n_telepherique_v2` | Points « telepherique » à 5 min de marche | points | calcul du projet |
| `n_train_v2` | Points « train » à 5 min de marche | points | calcul du projet |
| `n_tram_v2` | Points « tram » à 5 min de marche | points | calcul du projet |
| `n_trottinette_v2` | Points « trottinette » à 5 min de marche | points | calcul du projet |
| `n_velo_v2` | Points « velo » à 5 min de marche | points | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## acces_iris

Indicateurs d'accessibilité agrégés par IRIS.

**198 lignes** — fichiers : `acces_iris.gpkg` 0,4 Mo, `acces_iris.csv` 0,0 Mo, `acces_iris.geojson` 0,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `nom_iris` | Nom de l'IRIS | - | IGN, CONTOURS IRIS 2026 |
| `population` | Population municipale de la commune | habitants | INSEE, recensement 2023 (via ADMIN EXPRESS) |
| `menages` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `carreaux` | Nombre de carreaux habités agrégés | carreaux | calcul du projet |
| `n_options_v1` | Options pondérées accessibles à 400 m à vol d'oiseau | options | calcul du projet |
| `n_options_v2` | Options pondérées accessibles à 400 m de marche (réseau OSM) | options | calcul du projet |
| `acces_1000_v2` | Options pour 1 000 habitants (2SFCA), marche | options / 1 000 hab. | calcul du projet |
| `part_pop_couverte_v2` | Part de la population avec au moins une option à 5 min de marche | 0-1 | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

# Nantes Métropole (ville des recommandations)

## Choix de nettoyage

- **Population calée** : Filosofi 2021 ne compte que les ménages fiscaux ordinaires (625 546 individus) ; chaque carreau est recalé sur la population communale du recensement 2023 (689 456) : `pop_calee = ind × ratio_calage`. Ratios par commune : `data/processed/population_calage_communes.csv` (ex. Saint-Martin-d'Hères 1,25 : campus).
- **Rattachement des carreaux** : par centroïde (un carreau en bordure n'est compté que dans une commune).
- **Secret statistique** : 2 835 carreaux de moins de 11 ménages sont utilisés dans les calculs et dans les agrégats IRIS, mais **ne figurent pas** dans population_carreaux (ni les IRIS de moins de 11 ménages dans population_iris). Pour empêcher de retrouver un carreau masqué par différence (total IRIS − carreaux affichés), les **effectifs des tables IRIS sont arrondis à 5 près** dans les exports partagés (`pop_calee`, `ind`, `men`, `men_pauv`, `population`, `menages`) ; les ratios et tous les calculs du projet utilisent les valeurs exactes. Voir `docs/ethique.md`.
- **Motorisation** : jointure IRIS réussie pour 99,8 % des carreaux des communes découpées en IRIS ; 11 replis sur la valeur communale ; 755 carreaux de communes non découpées en IRIS (valeur communale).
- **Dédoublonnage de l'offre** : points d'un même mode à moins de 40 m fusionnés (train : 150 m) ; autopartage 62→61, bus 2536→1682, citiz 23→23, train 14→11, tram 175→131, trottinette 17→16, velo 236→118.
- **Jour type GTFS** : mardi le plus chargé des 8 prochaines semaines couvertes par chaque réseau (2026-11-17) : évite les vacances scolaires. `frequencies.txt` converti en départs réels.
- **Zone tampon** : l'offre est chargée sur la métropole + 800 m (colonne `dans_zone`).
- **GTFS retenus** (`config/settings.yaml`, cities.nantes.gtfs_feeds) : `reseau-de-transports-collectifs-naolib`, `arrets-horaires-et-circuits-des-lignes-de-transports-aleop`, `horaires-sncf`, `horaires-des-bacs-de-loire-en-loire-atlantique` ; exclus partout : covoiturage, Flixbus, BlaBlaCar ; jour type figé au mardi 2026-11-17.
- **Exclusions** : flux GBFS « Dott France » (doublon) ; emplacement interne « DEMOBOX (Réservé Citiz) ».
- **Corrections de typage GTFS** : `route_type = 5` du téléphérique -> téléphérique ; arrêts SNCF « OCECar » (autocars de substitution) -> bus.
- **Zones free-floating** : chaque zone de stationnement donne un point `velo` et un point `trottinette`.
- **Marguerite** : 61 stations d'autopartage publiées par Nantes Métropole (open data, Licence Ouverte), type `autopartage` ; les stations Citiz viennent du GBFS Citiz. Getaround : aucune donnée ouverte.
- **Recommandations** : `src/optim/build_reco.py` ; candidats hors des 5 min de marche d'un autopartage ; coût avec surcoût de risque de vol (**hypothèse à valider avec Citiz**) ; voir `docs/chiffres_cles.md`.
- **Coordonnées** : filtrage des points (0,0) ou hors de France métropolitaine.

## nantes_zone_communes

Les communes de la métropole (périmètre d'étude).

**24 lignes** — fichiers : `nantes/nantes_zone_communes.gpkg` 0,4 Mo, `nantes/nantes_zone_communes.csv` 0,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom` | Nom | - | selon la table |
| `population` | Population municipale de la commune | habitants | INSEE, recensement 2023 (via ADMIN EXPRESS) |
| `date_du_recensement` | Date de référence du recensement | date | IGN, ADMIN EXPRESS COG 2026 |
| `superficie_km2` | Superficie | km² | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_population_carreaux

Population et caractéristiques socio-économiques par carreau de 200 m.

**3 904 lignes** — fichiers : `nantes/nantes_population_carreaux.gpkg` 1,6 Mo, `nantes/nantes_population_carreaux.csv` 0,8 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `idcar_200m` | Identifiant INSEE du carreau de 200 m | - | INSEE, Filosofi 2021 carreaux 200 m |
| `i_est_200` | 1 = valeurs estimées par l'INSEE (carreau de moins de 11 ménages dans la source) | 0/1 | INSEE, Filosofi 2021 carreaux 200 m |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_pauv` | Ménages sous le seuil de pauvreté | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_prop` | Ménages propriétaires | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_snv` | Somme des niveaux de vie winsorisés des individus | € / an | INSEE, Filosofi 2021 carreaux 200 m |
| `log_soc` | Logements sociaux | logements | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_0_3` | Individus de 0 à 3 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_4_5` | Individus de 4 à 5 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_6_10` | Individus de 6 à 10 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_11_17` | Individus de 11 à 17 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_18_24` | Individus de 18 à 24 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_25_39` | Individus de 25 à 39 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_40_54` | Individus de 40 à 54 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_55_64` | Individus de 55 à 64 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_65_79` | Individus de 65 à 79 ans | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `ind_80p` | Individus de 80 ans et plus | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `ratio_calage` | Ratio population recensement 2023 / Σ Filosofi de la commune | - | calcul du projet |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `motorisation_source` | Origine de part_sans_voiture : iris, commune_non_irisee, repli_commune | - | calcul du projet |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_hab_km2` | Densité de population calée | habitants / km² | calcul du projet |
| `nom_commune` | Nom de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_population_iris

Agrégat par IRIS de TOUS les carreaux (y compris < 11 ménages) : affichage public recommandé. **Effectifs (pop_calee, ind, men, men_pauv) arrondis à 5 près** (secret statistique) ; ratios calculés sur les valeurs exactes.

**230 lignes** — fichiers : `nantes/nantes_population_iris.gpkg` 0,5 Mo, `nantes/nantes_population_iris.csv` 0,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom_commune` | Nom de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `nom_iris` | Nom de l'IRIS | - | IGN, CONTOURS IRIS 2026 |
| `carreaux` | Nombre de carreaux habités agrégés | carreaux | calcul du projet |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `men_pauv` | Ménages sous le seuil de pauvreté | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `superficie_km2` | Superficie | km² | calcul du projet |
| `densite_hab_km2` | Densité de population calée | habitants / km² | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_offre

Tous les points d'offre de mobilité (arrêts TC, stations d'autopartage, vélos, trottinettes) sur la zone + 800 m, avec la population desservie (objectif 2).

**2 042 lignes** — fichiers : `nantes/nantes_offre.gpkg` 0,9 Mo, `nantes/nantes_offre.csv` 0,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `id` | Identifiant : source:identifiant_d_origine:mode | - | GTFS / GBFS |
| `type` | Mode : bus, tram, train, telepherique, velo, trottinette, citiz | - | calcul du projet |
| `sous_type` | arret (TC), station (Citiz), zone_free_floating (zone de stationnement Voi) | - | calcul du projet |
| `nom` | Nom | - | selon la table |
| `source` | Jeu de données d'origine (gtfs:<jeu> ou gbfs:<jeu>) | - | transport.data.gouv.fr |
| `capacite` | Capacité déclarée (places) pour les stations GBFS | places | GBFS (transport.data.gouv.fr) |
| `passages_jour` | Passages un mardi type (TC uniquement), après fusion des quais | passages / jour | GTFS (transport.data.gouv.fr) |
| `n_fusionnes` | Nombre de points d'origine fusionnés (dédoublonnage) | points | calcul du projet |
| `ids_fusionnes` | Identifiants des points d'origine fusionnés, séparés par | | - | calcul du projet |
| `dans_zone` | Vrai si le point est dans la métropole (faux : dans la bande tampon de 800 m) | booléen | calcul du projet |
| `pop_desservie` | Habitants (population calée) à 5 min de ce point (V2 marche réelle si disponible, sinon V1) | habitants | calcul du projet |
| `pop_seule_option` | Habitants pour qui ce point est la SEULE option à 5 min | habitants | calcul du projet |
| `part_seule_option` | pop_seule_option / pop_desservie | 0-1 | calcul du projet |
| `version` | Accessibilité utilisée : v1 vol d'oiseau, v2 marche réelle | - | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_acces_carreaux

Indicateurs d'accessibilité à 5 min par carreau (V1 vol d'oiseau et V2 marche réelle).

**3 904 lignes** — fichiers : `nantes/nantes_acces_carreaux.gpkg` 1,5 Mo, `nantes/nantes_acces_carreaux.csv` 0,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `idcar_200m` | Identifiant INSEE du carreau de 200 m | - | INSEE, Filosofi 2021 carreaux 200 m |
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `pop_calee` | Population calée sur le recensement (ind × ratio_calage) : à utiliser par défaut | personnes | calcul du projet |
| `ind` | Individus (ménages fiscaux ordinaires), non calé | personnes | INSEE, Filosofi 2021 carreaux 200 m |
| `men` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `part_sans_voiture` | Part des ménages sans voiture (valeur de l'IRIS, ou de la commune) | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `n_options_v1` | Options pondérées accessibles à 400 m à vol d'oiseau | options | calcul du projet |
| `n_points_v1` | Points d'offre à 400 m à vol d'oiseau | points | calcul du projet |
| `acces_1000_v1` | Options pour 1 000 habitants (2SFCA), vol d'oiseau | options / 1 000 hab. | calcul du projet |
| `n_options_v2` | Options pondérées accessibles à 400 m de marche (réseau OSM) | options | calcul du projet |
| `n_points_v2` | Points d'offre à 400 m de marche | points | calcul du projet |
| `acces_1000_v2` | Options pour 1 000 habitants (2SFCA), marche | options / 1 000 hab. | calcul du projet |
| `n_options_v2_sans_poids_ff` | Comme n_options_v2, free-floating au poids normal du mode | options | calcul du projet |
| `n_autopartage_v2` | Stations d'autopartage hors Citiz (Marguerite) à 5 min de marche | points | calcul du projet |
| `n_bus_v2` | Points « bus » à 5 min de marche | points | calcul du projet |
| `n_citiz_v2` | Points « citiz » à 5 min de marche | points | calcul du projet |
| `n_train_v2` | Points « train » à 5 min de marche | points | calcul du projet |
| `n_tram_v2` | Points « tram » à 5 min de marche | points | calcul du projet |
| `n_trottinette_v2` | Points « trottinette » à 5 min de marche | points | calcul du projet |
| `n_velo_v2` | Points « velo » à 5 min de marche | points | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_acces_iris

Indicateurs d'accessibilité agrégés par IRIS.

**230 lignes** — fichiers : `nantes/nantes_acces_iris.gpkg` 0,5 Mo, `nantes/nantes_acces_iris.csv` 0,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `nom_iris` | Nom de l'IRIS | - | IGN, CONTOURS IRIS 2026 |
| `population` | Population municipale de la commune | habitants | INSEE, recensement 2023 (via ADMIN EXPRESS) |
| `menages` | Ménages fiscaux | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `carreaux` | Nombre de carreaux habités agrégés | carreaux | calcul du projet |
| `n_options_v1` | Options pondérées accessibles à 400 m à vol d'oiseau | options | calcul du projet |
| `n_options_v2` | Options pondérées accessibles à 400 m de marche (réseau OSM) | options | calcul du projet |
| `acces_1000_v2` | Options pour 1 000 habitants (2SFCA), marche | options / 1 000 hab. | calcul du projet |
| `part_pop_couverte_v2` | Part de la population avec au moins une option à 5 min de marche | 0-1 | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## nantes_recommandations

Stations Citiz recommandées (500 000 €, ILP, équité 0,5), dans l'ordre de priorité ; accessibilité en marche réelle (V2). Les fichiers recommandations_*.csv donnent tous les budgets et méthodes.

**12 lignes** — fichiers : `nantes/nantes_recommandations.gpkg` 0,1 Mo, `nantes/nantes_recommandations.csv` 0,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `rang` | Rang dans la liste priorisée (1 = première station à installer) | rang | calcul du projet |
| `id` | Identifiant : source:identifiant_d_origine:mode | - | GTFS / GBFS |
| `type` | Mode : bus, tram, train, telepherique, velo, trottinette, citiz | - | calcul du projet |
| `nom` | Nom | - | selon la table |
| `x` | Coordonnée X Lambert-93 | m | calcul du projet |
| `y` | Coordonnée Y Lambert-93 | m | calcul du projet |
| `cout` | Coût total de la station sur l'horizon (3 ans, scénario moyen) + surcoût de risque | € | config/costs.yaml |
| `pop_nouvellement_desservie` | Habitants qui passent à moins de 5 min d'un autopartage grâce à cette station | habitants | calcul du projet |
| `usage_predit` | Probabilité du modèle qu'une station Citiz soit à 400 m (prédite sans le réseau de la ville) | 0-1 | calcul du projet |
| `cout_par_habitant` | cout / pop_nouvellement_desservie | € / habitant | calcul du projet |
| `budget_cumule` | Coût cumulé des stations de rang ≤ celui-ci | € | calcul du projet |
| `gain_objectif` | Gain de la fonction objectif (habitants × équité × usage relatif) | - | calcul du projet |
| `origine` | Type d'emplacement candidat : carreau (centre d'un carreau habité) ou arret_tc | - | calcul du projet |
| `commune` | Commune de l'emplacement | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_iris` | Code IRIS contenant le centroïde (XXXXX0000 = commune non découpée en IRIS) | - | IGN, CONTOURS IRIS 2026 |
| `surcout_risque` | Surcoût de risque de vol inclus dans cout (HYPOTHÈSE À VALIDER AVEC CITIZ) | € | config/costs.yaml |
| `vols_vehicules_1000` | Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

# France entière (niveau 1)

## Choix de nettoyage

- **Couverture** : 67 416 412 habitants calés (carreaux Filosofi 2021 de métropole, Martinique et Réunion). Guadeloupe, Guyane, Mayotte : pas de carreaux Filosofi, donc pas d'indicateur par habitant (lignes vides dans france_departements, absentes de france_communes).
- **Accessibilité V1** : 400 m **à vol d'oiseau** autour du centroïde de chaque carreau de 200 m, puis moyenne pondérée par la population. C'est une **borne haute** : la marche réelle (réseau OSM, V2) est mesurée sur les agglomérations zoomées. Mêmes poids de modes et même dédoublonnage que pour Grenoble (`docs/methodologie.md` §4-5).
- **Offre nationale** : 547 GTFS (12 illisibles ; 74 expirés, lus sur leur dernier mardi valide) + tous les GBFS de transport.data.gouv.fr, fusionnés puis dédoublonnés par mode (40 m ; trains 150 m) : 533 613 → 231 092 points.
- **Autopartage existant** : seuls Citiz, Clem, Rémi, Optymo et Leo&Go publient un GBFS ; Getaround, Zity, Free2Move… sont absents. `autopartage_10k_hab` et donc le potentiel sont **biaisés** dans les grandes villes.
- **Risque de vol** (SSMSI) : faits enregistrés par la police et la gendarmerie, rapportés à la population ; commune : publié seulement à partir de 10 000 habitants (au-dessous, quelques faits font varier fortement le taux et désigneraient injustement de petites communes). C'est un **critère d'exploitation** (coût, assurance) et non un jugement sur les habitants : voir `docs/ethique.md`.
- **Secret statistique** : communes de moins de 11 ménages fiscaux exclues ; effectifs (`population`, `menages`) de toutes les tables France arrondis à 5 près. Aucun carreau n'est exporté au niveau national.
- **Géométries** : WGS84 (EPSG:4326) pour tout le territoire (DROM compris), simplifiées : départements ≈ 200 m, EPCI ≈ 300 m, communes ≈ 100 m. À utiliser pour des cartes, pas pour des calculs de surface fins.

## france_departements

France entière (DROM inclus) : un indicateur par département. Guadeloupe, Guyane et Mayotte : pas de population au carreau (Filosofi), indicateurs vides. Dossier `france/`.

**101 lignes** — fichiers : `france/france_departements.gpkg` 1,3 Mo, `france/france_departements.csv` 0,0 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `nom` | Nom officiel (departements) | - | IGN, ADMIN EXPRESS COG 2026 |
| `dep` | Code du département | - | IGN, ADMIN EXPRESS COG 2026 |
| `carreaux` | Carreaux habités de 200 m | carreaux | INSEE, Filosofi 2021 carreaux 200 m |
| `population` | Population calée (Σ des carreaux Filosofi recalés sur le recensement 2023), arrondie à 5 | habitants | calcul du projet |
| `menages` | Ménages fiscaux (Σ des carreaux), arrondis à 5 | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `n_options_moyen` | Options de mobilité pondérées accessibles à 5 min, moyenne par habitant | options | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_sans_option` | Part de la population sans aucun point d'offre à 5 min | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_avec_tc` | Part de la population à 5 min d'un arrêt de transport en commun | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_citiz_5min` | Part de la population à 5 min d'une station Citiz | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `acces_1000_moyen` | Options pour 1 000 habitants (2SFCA, tient compte de la demande concurrente), moyenne par habitant | options / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `citiz_1000_moyen` | Véhicules Citiz pour 1 000 habitants (2SFCA), moyenne par habitant | véhicules / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_menages_sans_voiture` | Part des ménages sans voiture | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_vecue_hab_km2` | Densité vécue : densité moyenne des carreaux où vivent les habitants (pondérée par la population ; insensible aux espaces vides) | habitants / km² | calcul du projet |
| `stations_citiz` | Stations Citiz (GBFS) | stations | GBFS (transport.data.gouv.fr) |
| `vehicules_citiz` | Véhicules Citiz déclarés (capacité des stations) | véhicules | GBFS (transport.data.gouv.fr) |
| `vols_vehicules_1000` | Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `degradations_1000` | Destructions et dégradations volontaires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `score_potentiel_moyen` | Moyenne, pondérée par la population, du score de potentiel des EPCI classés du département | 0-1 | calcul du projet |
| `part_pop_epci_classes` | Part de la population du département vivant dans un EPCI classé (≥ 50 000 hab.) | 0-1 | calcul du projet |
| `meilleur_epci` | EPCI du département le mieux classé (potentiel Citiz) | - | calcul du projet |
| `meilleur_rang` | Rang national de cet EPCI | rang | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## france_epci

France entière : toutes les intercommunalités, indicateurs + classement du potentiel Citiz (rang et score seulement pour les EPCI ≥ 50 000 hab.). Dossier `france/`.

**1 238 lignes** — fichiers : `france/france_epci.gpkg` 3,1 Mo, `france/france_epci.csv` 0,3 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `rang_potentiel` | Rang national du potentiel Citiz (1 = plus fort), EPCI ≥ 50 000 hab. | rang | calcul du projet |
| `code_epci` | Numéro SIREN de l'EPCI (intercommunalité) | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom` | Nom officiel (epci) | - | IGN, ADMIN EXPRESS COG 2026 |
| `nature` | Nature de l'EPCI : ME métropole, CU, CA, CC | - | IGN, ADMIN EXPRESS COG 2026 |
| `superficie_km2` | Superficie (projection équivalente) | km² | calcul du projet |
| `carreaux` | Carreaux habités de 200 m | carreaux | INSEE, Filosofi 2021 carreaux 200 m |
| `population` | Population calée (Σ des carreaux Filosofi recalés sur le recensement 2023), arrondie à 5 | habitants | calcul du projet |
| `menages` | Ménages fiscaux (Σ des carreaux), arrondis à 5 | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `n_options_moyen` | Options de mobilité pondérées accessibles à 5 min, moyenne par habitant | options | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_sans_option` | Part de la population sans aucun point d'offre à 5 min | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_avec_tc` | Part de la population à 5 min d'un arrêt de transport en commun | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_citiz_5min` | Part de la population à 5 min d'une station Citiz | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `acces_1000_moyen` | Options pour 1 000 habitants (2SFCA, tient compte de la demande concurrente), moyenne par habitant | options / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `citiz_1000_moyen` | Véhicules Citiz pour 1 000 habitants (2SFCA), moyenne par habitant | véhicules / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_menages_sans_voiture` | Part des ménages sans voiture | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_vecue_hab_km2` | Densité vécue : densité moyenne des carreaux où vivent les habitants (pondérée par la population ; insensible aux espaces vides) | habitants / km² | calcul du projet |
| `stations_citiz` | Stations Citiz (GBFS) | stations | GBFS (transport.data.gouv.fr) |
| `vehicules_citiz` | Véhicules Citiz déclarés (capacité des stations) | véhicules | GBFS (transport.data.gouv.fr) |
| `stations_autres_autopartage` | Stations d'autres opérateurs d'autopartage publiant un GBFS (Clem, Rémi, Optymo, Leo&Go) | stations | GBFS (transport.data.gouv.fr) |
| `voitures_free_floating` | Voitures d'autopartage sans station visibles en GBFS (photo du téléchargement) | voitures | GBFS (transport.data.gouv.fr) |
| `autopartage_10k_hab` | Autopartage existant connu (stations + voitures free-floating) pour 10 000 hab. — sous-estimé : la plupart des opérateurs ne publient rien | pour 10 000 hab. | calcul du projet |
| `citiz_stations_100k_hab` | Stations Citiz pour 100 000 habitants | pour 100 000 hab. | calcul du projet |
| `vols_vehicules_1000` | Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `degradations_1000` | Destructions et dégradations volontaires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `score_potentiel_citiz` | Potentiel Citiz : moyenne des rangs-percentiles (densité vécue ↑, ménages sans voiture ↑, autopartage existant ↓) parmi les EPCI ≥ 50 000 hab. | 0-1 | calcul du projet |
| `score_avec_risque` | Score de potentiel − 0,25 × rang-percentile des vols liés aux véhicules (variante prudente) | ≈ 0-1 | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## france_communes

France entière : une ligne par commune habitée d'au moins 11 ménages fiscaux ; contours simplifiés (≈ 100 m). Taux de vols seulement pour les communes ≥ 10 000 hab. Dossier `france/`.

**34 622 lignes** — fichiers : `france/france_communes.gpkg` 31,2 Mo, `france/france_communes.csv` 5,6 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `code_insee` | Code officiel géographique de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom` | Nom officiel (communes) | - | IGN, ADMIN EXPRESS COG 2026 |
| `dep` | Code du département | - | IGN, ADMIN EXPRESS COG 2026 |
| `code_epci` | Numéro SIREN de l'EPCI (intercommunalité) | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom_epci` | Nom de l'EPCI de la commune | - | IGN, ADMIN EXPRESS COG 2026 |
| `carreaux` | Carreaux habités de 200 m | carreaux | INSEE, Filosofi 2021 carreaux 200 m |
| `population` | Population calée (Σ des carreaux Filosofi recalés sur le recensement 2023), arrondie à 5 | habitants | calcul du projet |
| `menages` | Ménages fiscaux (Σ des carreaux), arrondis à 5 | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `n_options_moyen` | Options de mobilité pondérées accessibles à 5 min, moyenne par habitant | options | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_sans_option` | Part de la population sans aucun point d'offre à 5 min | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_avec_tc` | Part de la population à 5 min d'un arrêt de transport en commun | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_citiz_5min` | Part de la population à 5 min d'une station Citiz | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `acces_1000_moyen` | Options pour 1 000 habitants (2SFCA, tient compte de la demande concurrente), moyenne par habitant | options / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `citiz_1000_moyen` | Véhicules Citiz pour 1 000 habitants (2SFCA), moyenne par habitant | véhicules / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_menages_sans_voiture` | Part des ménages sans voiture | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_vecue_hab_km2` | Densité vécue : densité moyenne des carreaux où vivent les habitants (pondérée par la population ; insensible aux espaces vides) | habitants / km² | calcul du projet |
| `stations_citiz` | Stations Citiz (GBFS) | stations | GBFS (transport.data.gouv.fr) |
| `vehicules_citiz` | Véhicules Citiz déclarés (capacité des stations) | véhicules | GBFS (transport.data.gouv.fr) |
| `vols_vehicules_1000` | Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab. — publié seulement pour les communes d'au moins 10 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `degradations_1000` | Destructions et dégradations volontaires, moyenne annuelle 2023-2025 pour 1 000 hab. — idem  communes d'au moins 10 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `score_potentiel_epci` | Score de potentiel Citiz de l'EPCI de la commune (vide si EPCI < 50 000 hab.) | 0-1 | calcul du projet |
| `rang_potentiel_epci` | Rang national de l'EPCI de la commune | rang | calcul du projet |
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |

## france_classement_epci

Classement des EPCI ≥ 50 000 hab. par potentiel Citiz, trié par rang (CSV pour Excel). Dossier `france/`.

**276 lignes** — fichiers : `france/france_classement_epci.csv` 0,1 Mo

| Colonne | Signification | Unité | Source |
|---|---|---|---|
| `rang_potentiel` | Rang national du potentiel Citiz (1 = plus fort), EPCI ≥ 50 000 hab. | rang | calcul du projet |
| `code_epci` | Numéro SIREN de l'EPCI (intercommunalité) | - | IGN, ADMIN EXPRESS COG 2026 |
| `nom` | Nom officiel (epci) | - | IGN, ADMIN EXPRESS COG 2026 |
| `nature` | Nature de l'EPCI : ME métropole, CU, CA, CC | - | IGN, ADMIN EXPRESS COG 2026 |
| `superficie_km2` | Superficie (projection équivalente) | km² | calcul du projet |
| `carreaux` | Carreaux habités de 200 m | carreaux | INSEE, Filosofi 2021 carreaux 200 m |
| `population` | Population calée (Σ des carreaux Filosofi recalés sur le recensement 2023), arrondie à 5 | habitants | calcul du projet |
| `menages` | Ménages fiscaux (Σ des carreaux), arrondis à 5 | ménages | INSEE, Filosofi 2021 carreaux 200 m |
| `n_options_moyen` | Options de mobilité pondérées accessibles à 5 min, moyenne par habitant | options | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_sans_option` | Part de la population sans aucun point d'offre à 5 min | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_avec_tc` | Part de la population à 5 min d'un arrêt de transport en commun | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_pop_citiz_5min` | Part de la population à 5 min d'une station Citiz | 0-1 | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `acces_1000_moyen` | Options pour 1 000 habitants (2SFCA, tient compte de la demande concurrente), moyenne par habitant | options / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `citiz_1000_moyen` | Véhicules Citiz pour 1 000 habitants (2SFCA), moyenne par habitant | véhicules / 1 000 hab. | calcul du projet (V1 : 400 m à vol d'oiseau) |
| `part_menages_sans_voiture` | Part des ménages sans voiture | 0-1 | INSEE, recensement 2023, logement par IRIS |
| `niveau_vie_moyen` | Niveau de vie moyen (ind_snv / ind) | € / an / personne | calcul du projet |
| `part_menages_pauvres` | Part des ménages pauvres (men_pauv / men) | 0-1 | calcul du projet |
| `densite_vecue_hab_km2` | Densité vécue : densité moyenne des carreaux où vivent les habitants (pondérée par la population ; insensible aux espaces vides) | habitants / km² | calcul du projet |
| `stations_citiz` | Stations Citiz (GBFS) | stations | GBFS (transport.data.gouv.fr) |
| `vehicules_citiz` | Véhicules Citiz déclarés (capacité des stations) | véhicules | GBFS (transport.data.gouv.fr) |
| `stations_autres_autopartage` | Stations d'autres opérateurs d'autopartage publiant un GBFS (Clem, Rémi, Optymo, Leo&Go) | stations | GBFS (transport.data.gouv.fr) |
| `voitures_free_floating` | Voitures d'autopartage sans station visibles en GBFS (photo du téléchargement) | voitures | GBFS (transport.data.gouv.fr) |
| `autopartage_10k_hab` | Autopartage existant connu (stations + voitures free-floating) pour 10 000 hab. — sous-estimé : la plupart des opérateurs ne publient rien | pour 10 000 hab. | calcul du projet |
| `citiz_stations_100k_hab` | Stations Citiz pour 100 000 habitants | pour 100 000 hab. | calcul du projet |
| `vols_vehicules_1000` | Vols de et dans les véhicules et d'accessoires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `degradations_1000` | Destructions et dégradations volontaires, moyenne annuelle 2023-2025 pour 1 000 hab. | faits / an / 1 000 hab. | SSMSI, délinquance enregistrée par commune 2023-2025 |
| `score_potentiel_citiz` | Potentiel Citiz : moyenne des rangs-percentiles (densité vécue ↑, ménages sans voiture ↑, autopartage existant ↓) parmi les EPCI ≥ 50 000 hab. | 0-1 | calcul du projet |
| `score_avec_risque` | Score de potentiel − 0,25 × rang-percentile des vols liés aux véhicules (variante prudente) | ≈ 0-1 | calcul du projet |
