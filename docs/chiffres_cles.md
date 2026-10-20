# Chiffres clés (générés le 20/10/2026)

Généré par `python -m scripts.chiffres_cles` à partir des fichiers du pipeline : **ne pas modifier à la main**.
Accessibilité « 5 min à pied » = 400 m (4.8 km/h). Jour type des horaires de TC : mardi 2026-11-17. Population : Filosofi 2021 recalée sur le recensement 2023. V1 = vol d'oiseau (borne haute), V2 = marche réelle sur le réseau OpenStreetMap.

## 1. France entière (V1)

| Chiffre | Valeur | Source (fichier · commande) |
|---|---:|---|
| Habitants couverts (carreaux de 200 m) | 67 416 412 | `data/processed/national/agg_rapport.json` · `python -m src.national.build_all` |
| Sans aucune option à 5 min | **25,9 %** | idem |
| À 5 min d'un arrêt de transport en commun | 73,1 % | idem |
| À 5 min d'une station Citiz | 5,6 % | idem |
| Options pondérées par habitant | 6,34 | idem |
| Points d'offre (après dédoublonnage) | 231 092 (sur 533 613) | `national/offer_rapport.json` · idem |
| Flux GTFS lus | 547 (12 illisibles, 74 lus sur leur dernier mardi valide) | idem |

## 2. Choix des villes (classement de 276 EPCI ≥ 50 000 hab.)

| | Rang potentiel Citiz | Habitants | Stations Citiz | Pop. à 5 min de Citiz (V1) | Vols liés aux véhicules / 1 000 hab. |
|---|---:|---:|---:|---:|---:|
| Métropole Nice Côte d'Azur | 1 | 574 287 | 0 | 0,0 % | 6,6 |
| Nantes Métropole | 58 | 689 456 | 23 | 11,8 % | 13,6 |
| Grenoble-Alpes-Métropole | 61 | 450 608 | 168 | 53,0 % | 19,1 |

Source : `data/processed/national/classement_epci.parquet` · `python -m src.national.build_all` ; argumentaire : `docs/choix_ville.md`.

## 3. Grenoble, ville exemple : vol d'oiseau ou marche réelle ?

| Part de la population | V1 vol d'oiseau | V2 marche réelle |
|---|---:|---:|
| Au moins une option à 5 min | 96,4 % | **89,2 %** |
| Au moins un arrêt de TC | 95,5 % | 83,5 % |
| Une station Citiz à 5 min | 53,0 % | **39,7 %** |
| Options pondérées par habitant | 17,0 | 9,4 |

- La V1 surestime les options de **80 %** ; 32 137 habitants semblent desservis à vol d'oiseau mais ne le sont pas à pied.
- 450 608 habitants, 4 285 carreaux habités, 2 718 points d'offre.
- Source : `data/processed/grenoble/access_comparaison.json` · `python -m scripts.build_all --ville grenoble`.

## 4. Modèle : où Citiz s'installe-t-il ?

Apprentissage : 313 086 carreaux des 106 EPCI où Citiz est présent (11 719 avec une station à 400 m) ; 15 réseaux régionaux Citiz.

| Test à l'aveugle Grenoble (réseau Auvergne-Rhône-Alpes jamais vu) | Modèle | Densité seule |
|---|---:|---:|
| Vraies stations (168) dont le carreau est dans le top 5 % | **54,8 %** | 52,4 % |
| Vraies stations (168) dont le carreau est dans le top 10 % | **68,5 %** | 64,9 % |
| Vraies stations (168) dont le carreau est dans le top 20 % | **89,3 %** | 82,1 % |
| AUC (carreaux de Grenoble) | 0,953 | 0,931 |
| AUC, validation par réseau (15 plis) | 0,922 | 0,914 |
| Positifs captés dans le top 10 % de chaque EPCI (moyenne) | 82,3 % | 78,1 % |

Variables les plus importantes (SHAP) : `equipements_400m`, `vols_vehicules_1000`, `part_sans_voiture`, `densite_800m`, `options_hors_citiz_400m`.
Source : `data/processed/model/validation.json`, `shap_importance.csv` · `python -m src.model.features && python -m src.model.train`. Limite : le modèle apprend où Citiz s'est installé, pas la demande pure (`docs/modele.md`).

## 5. Nantes Métropole, notre ville : diagnostic (V1)

| Chiffre | Valeur | Source |
|---|---:|---|
| Habitants | 689 456 | `data/processed/nantes/population_rapport.json` · `python -m scripts.build_all --ville nantes` |
| Au moins une option à 5 min | 93,3 % | `nantes/access_comparaison.json` |
| Options pondérées par habitant | 9,1 (Grenoble V1 : 17,0) | idem |
| Stations Citiz / Marguerite | 23 / 61 | `nantes/reco_resume.json` |
| À 5 min d'une station Citiz | 11,8 % | `nantes/access_comparaison.json` |
| À 5 min d'un autopartage (Citiz ou Marguerite) | **28,5 %** | `nantes/reco_resume.json` |
| Habitants par station Citiz (médiane) | 4 502 | `nantes/served_by_type.csv` |
| Habitants dont la seule option est un unique arrêt / station | 32 138 | `nantes/offer_served.parquet` |

## 6. Nantes : recommandations Citiz (ILP, équité 0,5)

Candidats : 6 163 carreaux et 1 428 arrêts de TC à plus de 400 m d'un autopartage. Coût d'une station : 37 900 € sur 3 ans (scénario moyen) + surcoût de risque de vol (moyenne 1 046 €).

| Budget | Stations | Habitants nouvellement à 5 min | Couverture autopartage | € / habitant | CO2 évité |
|---:|---:|---:|---:|---:|---:|
| 250 000 € | 6 | **25 942** | 28,5 % → 32,3 % | 9,1 | 8,5 t/an |
| 500 000 € | 12 | **43 759** | 28,5 % → 34,9 % | 10,8 | 17,0 t/an |
| 1 000 000 € | 25 | **76 261** | 28,5 % → 39,6 % | 13,0 | 35,5 t/an |

Glouton vs ILP (habitants nouvellement couverts) : 250 000 € : 25 942 vs 25 942 ; 500 000 € : 43 759 vs 43 759 ; 1 000 000 € : 76 043 vs 76 261.
Source : `data/processed/nantes/reco_resume.json`, `recommandations_ilp_<budget>.csv` · `python -m scripts.build_all --ville nantes`. CO2 : estimation prudente ADEME (10 000 km évités/véhicule/an × 0,142 kgCO2e/km), 1 véhicule par station.

Effet du poids d'équité (500 000 €, glouton) :

| Poids d'équité | Stations | Habitants nouveaux | Part de ménages sans voiture chez les nouveaux | Priorité d'équité moyenne |
|---:|---:|---:|---:|---:|
| 0,0 | 12 | 43 759 | 28,3 % | 0,85 |
| 0,5 | 12 | 43 759 | 28,3 % | 0,85 |
| 2,0 | 12 | 43 759 | 28,3 % | 0,85 |

Lecture : la sélection ne change pas avec le poids d'équité. À Nantes, les poches denses non couvertes autour du centre sont aussi celles où vivent le plus de ménages pauvres ou sans voiture : efficacité et équité vont dans le même sens (priorité d'équité moyenne des nouveaux couverts 0,85, contre 0,5 pour l'ensemble des carreaux).

Source : calcul de `python -m scripts.chiffres_cles` sur `data/processed/nantes/` (cells, candidates, coverage).

## 7. Images pour les slides (`slides/img/`)

| Image | Contenu | Produite par |
|---|---|---|
| `france_sans_option.png` | France : part des habitants sans option à 5 min, par département (V1) | python -m scripts.chiffres_cles |
| `grenoble_v1_vol_oiseau.png` | Grenoble : options accessibles à vol d'oiseau (V1) | `docs/figures/grenoble/acces_v1_buffer.png` · python -m scripts.build_all --ville grenoble |
| `grenoble_v2_marche.png` | Grenoble : options accessibles à pied (V2, même échelle) | `docs/figures/grenoble/acces_v2_reseau.png` · python -m scripts.build_all --ville grenoble |
| `grenoble_surestimation_v1.png` | Grenoble : surestimation de la V1 (V1 − V2) | `docs/figures/grenoble/acces_v1_moins_v2.png` · python -m scripts.build_all --ville grenoble |
| `nantes_acces_iris.png` | Nantes : options par habitant, par IRIS (V1) | `docs/figures/nantes/acces_iris_v1.png` · python -m scripts.build_all --ville nantes |
| `nantes_acces_carreaux.png` | Nantes : options accessibles par carreau (V1) | `docs/figures/nantes/acces_v1_buffer.png` · python -m scripts.build_all --ville nantes |
| `nantes_recommandations.png` | Nantes : 12 stations Citiz recommandées (500 000 €, ILP) | `docs/figures/nantes/reco_stations.png` · python -m scripts.build_all --ville nantes |
| `modele_shap_importance.png` | Modèle : importance des variables (SHAP) | `docs/figures/modele/shap_importance.png` · python -m src.model.features && python -m src.model.train |
| `modele_shap_effets.png` | Modèle : sens des effets (SHAP) | `docs/figures/modele/shap_beeswarm.png` · python -m src.model.features && python -m src.model.train |
