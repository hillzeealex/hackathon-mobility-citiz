# Dictionnaire des données — Hackathon Mobility Grenoble (Epitech × Citiz)

Généré par `scripts/export_share.py` le 2026-10-19. Méthode détaillée : `docs/methodologie.md` ; sources : `docs/sources.md`.

## Formats

| Format | Pour qui | Détails |
|---|---|---|
| `.csv` | Excel | séparateur `;`, UTF-8 avec BOM, virgule décimale ; colonnes `latitude`/`longitude` en WGS84 (centroïde pour les surfaces), pas de géométrie |
| `.gpkg` | QGIS | géométries complètes, Lambert-93 (EPSG:2154) |
| `.geojson` | web, outils en ligne | WGS84 (EPSG:4326), produit si < 50 Mo |
| `carte_apercu.html` | tout le monde | double-clic : carte interactive de toutes les couches (connexion internet requise pour le fond de carte) |

## Choix de nettoyage

- **Population calée** : Filosofi 2021 ne compte que les ménages fiscaux ordinaires (406 039 individus) ; chaque carreau est recalé sur la population communale du recensement 2023 (450 608) : `pop_calee = ind × ratio_calage`. Ratios par commune : `data/processed/population_calage_communes.csv` (ex. Saint-Martin-d'Hères 1,25 : campus).
- **Rattachement des carreaux** : par centroïde (un carreau en bordure n'est compté que dans une commune).
- **Secret statistique** : 2 006 carreaux de moins de 11 ménages sont utilisés dans les calculs et dans les agrégats IRIS, mais **ne figurent pas** dans population_carreaux (ni les IRIS de moins de 11 ménages dans population_iris). Pour empêcher de retrouver un carreau masqué par différence (total IRIS − carreaux affichés), les **effectifs des tables IRIS sont arrondis à 5 près** dans les exports partagés (`pop_calee`, `ind`, `men`, `men_pauv`, `population`, `menages`) ; les ratios et tous les calculs du projet utilisent les valeurs exactes. Voir `docs/ethique.md`.
- **Motorisation** : jointure IRIS réussie pour 99,7 % des carreaux des communes découpées en IRIS ; 8 replis sur la valeur communale ; 1 733 carreaux de communes non découpées en IRIS (valeur communale).
- **Dédoublonnage de l'offre** : points d'un même mode à moins de 40 m fusionnés (train : 150 m) ; bus 1659→1022, citiz 188→169, telepherique 2→2, train 5→4, tram 168→124, trottinette 697→685, velo 697→685.
- **Jour type GTFS** : mardi le plus chargé des 8 prochaines semaines couvertes par chaque réseau (2026-10-20, 2026-11-03, 2026-11-10) : évite les vacances scolaires. `frequencies.txt` converti en départs réels.
- **Zone tampon** : l'offre est chargée sur la métropole + 800 m (colonne `dans_zone`).
- **Exclusions** : lignes de covoiturage M covoit' ; flux GBFS « Dott France » (doublon) ; emplacement interne « DEMOBOX (Réservé Citiz) ».
- **Corrections de typage GTFS** : `route_type = 5` du téléphérique -> téléphérique ; arrêts SNCF « OCECar » (autocars de substitution) -> bus.
- **Zones Voi** : chaque zone de stationnement donne un point `velo` et un point `trottinette`.
- **Coordonnées** : filtrage des points (0,0) ou hors de France métropolitaine.

## zone_communes

Les 49 communes de Grenoble-Alpes-Métropole (périmètre d'étude).

**49 lignes** — fichiers : gpkg 0,5 Mo, csv 0,0 Mo, geojson 0,9 Mo

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

**2 279 lignes** — fichiers : gpkg 1,0 Mo, csv 0,5 Mo, geojson 2,0 Mo

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

**198 lignes** — fichiers : gpkg 0,4 Mo, csv 0,0 Mo, geojson 0,6 Mo

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

Tous les points d'offre de mobilité (arrêts TC, stations Citiz, zones Voi) sur la zone + 800 m.

**2 691 lignes** — fichiers : gpkg 1,0 Mo, csv 0,7 Mo, geojson 1,3 Mo

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
| `latitude` | Latitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
| `longitude` | Longitude du point (centroïde pour une surface) | degrés WGS84 | calcul du projet |
