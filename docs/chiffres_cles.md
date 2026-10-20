# Chiffres clés (générés le 20/10/2026)

Généré par `python -m scripts.chiffres_cles` à partir des fichiers du pipeline : **ne pas modifier à la main**.
Accessibilité « 5 min à pied » = 400 m (4.8 km/h). Jour type des horaires de TC : mardi 2026-11-17. Population : Filosofi 2021 recalée sur le recensement 2023. V2 = marche réelle sur le réseau OpenStreetMap (méthode de référence) ; V1 = 400 m à vol d'oiseau, **méthode simplifiée, pour comparaison uniquement** (borne haute).

> ### CHIFFRES OFFICIELS POUR LES SLIDES (V2, marche réelle)
>
> Seuls ces chiffres vont dans les slides et à l'oral. Tous sont calculés en **V2** (5 minutes de marche réelle), sauf la France entière, qui n'existe qu'en V1. Les chiffres V1 plus bas servent uniquement à la comparaison.
>
> | Message | Chiffre officiel |
> |---|---:|
> | Nantes : habitants | 689 456 |
> | Nantes : au moins une option de mobilité à 5 min à pied | **80,6 %** |
> | Nantes : options pondérées accessibles par habitant | 4,7 |
> | Nantes : à 5 min à pied d'un autopartage (23 Citiz, 61 Marguerite) | **19,0 %** |
> | Nantes : habitants dont la seule option à 5 min est un unique arrêt ou station | 92 883 |
> | 500 000 € : stations Citiz recommandées | **12** |
> | 500 000 € : habitants gagnés (nouvellement à 5 min à pied d'un autopartage) | **+34 979** |
> | 500 000 € : couverture autopartage avant → après | **19,0 % → 24,1 %** |
> | 500 000 € : coût par habitant gagné (sur 3 ans) | **13,6 €** |
> | 500 000 € : CO2 évité (estimation prudente) | 17,0 t/an |
> | 1 000 000 € : stations · habitants gagnés · couverture après | 25 · +59 039 · 27,6 % |
> | Test à l'aveugle Grenoble : stations Citiz (168) retrouvées dans le top 20 % des carreaux | **89,3 %** (densité seule 82,1 %) |
> | AUC : test à l'aveugle Grenoble · validation sur les 15 réseaux | 0,953 · 0,922 (densité seule 0,931 · 0,914) |
> | Grenoble : au moins une option à 5 min à pied · à 5 min d'une station Citiz | 89,2 % · 39,7 % |
> | Grenoble : surestimation des options si l'on calcule à vol d'oiseau | +80 % |
> | France entière : sans aucune option à 5 min (V1 seule disponible : le dire, c'est une borne haute) | 25,9 % |

## 1. France entière (V1 : méthode simplifiée, seule disponible à cette échelle ; borne haute)

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

| | Rang potentiel Citiz | Habitants | Stations Citiz | Pop. à 5 min de Citiz (V1 ¹) | Vols liés aux véhicules / 1 000 hab. |
|---|---:|---:|---:|---:|---:|
| Métropole Nice Côte d'Azur | 1 | 574 287 | 0 | 0,0 % | 6,6 |
| Nantes Métropole | 58 | 689 456 | 23 | 11,8 % | 13,6 |
| Grenoble-Alpes-Métropole | 61 | 450 608 | 168 | 53,0 % | 19,1 |

¹ V1 = méthode simplifiée (400 m à vol d'oiseau), **pour comparaison uniquement** : ne pas citer dans les slides.
Source : `data/processed/national/classement_epci.parquet` · `python -m src.national.build_all` ; argumentaire : `docs/choix_ville.md`.

## 3. Grenoble, ville exemple : vol d'oiseau ou marche réelle ?

| Part de la population | V1 vol d'oiseau ¹ | V2 marche réelle |
|---|---:|---:|
| Au moins une option à 5 min | 96,4 % | **89,2 %** |
| Au moins un arrêt de TC | 95,5 % | 83,5 % |
| Une station Citiz à 5 min | 53,0 % | **39,7 %** |
| Options pondérées par habitant | 17,0 | 9,4 |

¹ V1 = méthode simplifiée (400 m à vol d'oiseau), **pour comparaison uniquement** : ne pas citer dans les slides.

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

## 5. Nantes Métropole, notre ville : diagnostic

| Chiffre | V1 vol d'oiseau ¹ | V2 marche réelle | Écart V2 / V1 |
|---|---:|---:|---:|
| Habitants | 689 456 | idem | |
| Au moins une option à 5 min | 93,3 % | **80,6 %** | −14 % |
| Au moins un arrêt de TC | 93,3 % | 79,7 % | −15 % |
| Options pondérées par habitant | 9,1 | 4,7 | −48 % |
| À 5 min d'une station Citiz | 11,8 % | 7,5 % | −37 % |
| À 5 min d'un autopartage (Citiz ou Marguerite) | 28,5 % | **19,0 %** | −33 % |

¹ V1 = méthode simplifiée (400 m à vol d'oiseau), **pour comparaison uniquement** : ne pas citer dans les slides.

- Stations existantes : 23 Citiz, 61 Marguerite. La V1 surestime les options de 93 % ; 87 591 habitants semblent desservis à vol d'oiseau mais ne le sont pas à pied (coupures du réseau piéton : cours d'eau, voies ferrées, grands axes).
- Habitants par station Citiz (médiane, V2) : 2 124 ; habitants dont la seule option est un unique arrêt / station (V2) : 92 883.
- Sources : `data/processed/nantes/access_comparaison.json`, `reco_resume_v1.json`, `reco_resume_v2.json`, `served_by_type.csv`, `offer_served.parquet` · `python -m scripts.build_all --ville nantes`.

## 6. Nantes : recommandations Citiz (ILP, équité 0,5)

Candidats (V2) : 6 385 carreaux et 1 486 arrêts de TC hors des 5 min de marche d'un autopartage. Coût d'une station : 37 900 € sur 3 ans (scénario moyen) + surcoût de risque de vol, **hypothèse à valider avec Citiz** (moyenne 1 051 €).

**12 stations (500 000 €)**

| Chiffre | V1 vol d'oiseau ¹ | V2 marche réelle | Écart V2 / V1 |
|---|---:|---:|---:|
| Couverture autopartage actuelle | 28,5 % | 19,0 % | −33 % |
| Couverture après les 12 stations | 34,9 % | **24,1 %** | −31 % |
| Habitants gagnés | 43 759 | **34 979** | −20 % |
| € par habitant gagné (3 ans) | 10,8 | 13,6 | +26 % |
| CO2 évité | 17,0 t/an | 17,0 t/an | +0 % |

¹ V1 = méthode simplifiée (400 m à vol d'oiseau), **pour comparaison uniquement** : ne pas citer dans les slides.

Sélection : **3 stations sur 12 en commun** aux deux versions (Berlioz (bus), Nantes, St-Aignan (bus), Nantes, Quartier Waldeck-Sully (Nantes)). Liste V2 retenue : 1. Quartier Harlière Sud (Saint-Herblain) ; 2. Vaucanson (bus), Nantes ; 3. Quartier Dervallières-Chézine (Nantes) ; 4. Berlioz (bus), Nantes ; 5. St-Aignan (bus), Nantes ; 6. Quartier Coudray (Nantes) ; 7. Boulay Paty (bus), Nantes ; 8. Quartier Canclaux (Nantes) ; 9. Bruneau (bus), Nantes ; 10. Quartier Waldeck-Sully (Nantes) ; 11. Quartier Grillaud-Procé (Nantes) ; 12. Quartier Beauséjour (Saint-Herblain).

**Tous les budgets (V2, ILP)**

| Budget | Stations | Habitants nouvellement à 5 min | Couverture autopartage | € / habitant | CO2 évité |
|---:|---:|---:|---:|---:|---:|
| 250 000 € | 6 | **19 138** | 19,0 % → 21,8 % | 12,4 | 8,5 t/an |
| 500 000 € | 12 | **34 979** | 19,0 % → 24,1 % | 13,6 | 17,0 t/an |
| 1 000 000 € | 25 | **59 039** | 19,0 % → 27,6 % | 16,7 | 35,5 t/an |

Glouton vs ILP (habitants nouvellement couverts, V2) : 250 000 € : 19 138 vs 19 138 ; 500 000 € : 34 979 vs 34 979 ; 1 000 000 € : 58 595 vs 59 039.
Sources : `data/processed/nantes/reco_resume_v1.json`, `reco_resume_v2.json`, `recommandations_ilp_<budget>_<v>.csv` · `python -m scripts.build_all --ville nantes`. CO2 : estimation prudente ADEME (10 000 km évités/véhicule/an × 0,142 kgCO2e/km), 1 véhicule par station.

Effet du poids d'équité (500 000 €, glouton, V2) :

| Poids d'équité | Stations | Habitants nouveaux | Part de ménages sans voiture chez les nouveaux | Priorité d'équité moyenne |
|---:|---:|---:|---:|---:|
| 0,0 | 12 | 34 979 | 27,4 % | 0,84 |
| 0,5 | 12 | 34 979 | 27,4 % | 0,84 |
| 2,0 | 12 | 34 979 | 27,4 % | 0,84 |

Lecture : la sélection ne change pas avec le poids d'équité. À Nantes, les poches denses non couvertes autour du centre sont aussi celles où vivent le plus de ménages modestes ou sans voiture : efficacité et équité vont dans le même sens (priorité d'équité moyenne des nouveaux couverts 0,84, contre 0,5 pour l'ensemble des carreaux).

Source : calcul de `python -m scripts.chiffres_cles` sur `data/processed/nantes/` (cells, candidates, coverage).

## 7. Images pour les slides (`slides/img/`)

| Image | Contenu | Produite par |
|---|---|---|
| `france_sans_option.png` | France : part des habitants sans option à 5 min, par département (V1) | python -m scripts.chiffres_cles |
| `grenoble_v1_vol_oiseau.png` | Grenoble : options accessibles à vol d'oiseau (V1) | `docs/figures/grenoble/acces_v1_buffer.png` · python -m scripts.build_all --ville grenoble |
| `grenoble_v2_marche.png` | Grenoble : options accessibles à pied (V2, même échelle) | `docs/figures/grenoble/acces_v2_reseau.png` · python -m scripts.build_all --ville grenoble |
| `grenoble_surestimation_v1.png` | Grenoble : surestimation de la V1 (V1 − V2) | `docs/figures/grenoble/acces_v1_moins_v2.png` · python -m scripts.build_all --ville grenoble |
| `nantes_acces_iris.png` | Nantes : options par habitant, par IRIS (V2 marche réelle) | `docs/figures/nantes/acces_iris_v2.png` · python -m scripts.build_all --ville nantes |
| `nantes_v1_vol_oiseau.png` | Nantes : options accessibles à vol d'oiseau (V1) | `docs/figures/nantes/acces_v1_buffer.png` · python -m scripts.build_all --ville nantes |
| `nantes_v2_marche.png` | Nantes : options accessibles à pied (V2, même échelle) | `docs/figures/nantes/acces_v2_reseau.png` · python -m scripts.build_all --ville nantes |
| `nantes_surestimation_v1.png` | Nantes : surestimation de la V1 (V1 − V2) | `docs/figures/nantes/acces_v1_moins_v2.png` · python -m scripts.build_all --ville nantes |
| `nantes_recommandations.png` | Nantes : 12 stations Citiz recommandées (500 000 €, ILP, marche réelle) | `docs/figures/nantes/reco_stations_v2.png` · python -m scripts.build_all --ville nantes |
| `nantes_recommandations_v1.png` | Nantes : les 12 stations calculées à vol d'oiseau (comparaison) | `docs/figures/nantes/reco_stations_v1.png` · python -m scripts.build_all --ville nantes |
| `modele_shap_importance.png` | Modèle : importance des variables (SHAP) | `docs/figures/modele/shap_importance.png` · python -m src.model.features && python -m src.model.train |
| `modele_shap_effets.png` | Modèle : sens des effets (SHAP) | `docs/figures/modele/shap_beeswarm.png` · python -m src.model.features && python -m src.model.train |
