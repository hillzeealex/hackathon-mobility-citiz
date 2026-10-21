# Slides

| Fichier | Pour qui, quand | Contenu |
|---|---|---|
| [`citiz_strategie.pptx`](citiz_strategie.pptx) | Premier orateur, ≈ 3 min | L'ambition, le constat Autolib', notre réponse GO / NO GO, transition |
| [`citiz_soutenance.pptx`](citiz_soutenance.pptx) | Second orateur, avec la démo | Contexte, problème, solution, recommandation chiffrée ; annexes pour les questions |
| [`DONNEES_ET_AUTOMATISATION.pptx`](DONNEES_ET_AUTOMATISATION.pptx) | Annexe | Nos données de A à Z : sources, extraction, nettoyage, automatisation |

Les deux premiers decks sont aux couleurs de Citiz (turquoise `#32B4B5`, texte `#202020`, rouge `#E63329` pour
les alertes, logos Citiz × Epitech × Microsoft). Le texte à dire est dans les **notes de l'orateur** de chaque slide.

Format imposé : 15 minutes par groupe, dont **5 minutes de présentation + démo**, le reste en questions.

---

## 1. Le deck stratégie, slide par slide

### Slide 1 · Couverture

- **Objectif** : poser le sujet pendant que l'équipe se présente.
- **À l'écran** : « Développer l'autopartage sans refaire Autolib' », sous-titre « une croissance maîtrisée, mesurable
  et durable pour Citiz, à Nantes Métropole », logos des trois partenaires.
- **Données** : aucune.

### Slide 2 · L'ambition (≈ 45 s)

- **Objectif** : montrer que le marché va exploser, et que la vraie question est *où* implanter.
- **À l'écran** : le chiffre 70 000, un graphique « début 2025 → objectif 2031 », la bascule « posséder → utiliser »,
  et la question : où implanter les prochaines stations, de façon soutenable et utile ?
- **D'où viennent les chiffres** :

| Chiffre | Source |
|---|---|
| 70 000 voitures en autopartage visées en 2031 | Annonce de Philippe Tabarot, ministre des Transports, le 4 décembre 2025 ([Banque des Territoires](https://www.banquedesterritoires.fr/autopartage-le-gouvernement-vise-un-objectif-de-70000-vehicules-dici-2031)) |
| 13 862 voitures en autopartage début 2025 | Même article ; d'où « plus de cinq fois le parc actuel » (70 000 / 13 862 = 5,05) |

### Slide 3 · Le constat Autolib' (≈ 50 s)

- **Objectif** : montrer qu'un service utilisé peut échouer faute de rentabilité, et qu'il faut donc décider avec
  des chiffres.
- **À l'écran** : trois causes (prévisions trop optimistes, trop peu d'usage par voiture, pertes qui se creusent),
  puis la leçon « le succès d'usage ne garantit pas la rentabilité ».
- **D'où viennent les chiffres** :

| Chiffre | Source |
|---|---|
| Autolib' de 2011 à 2018, contrat résilié en juin 2018 | [Observatoire européen de la mobilité urbaine](https://urban-mobility-observatory.transport.ec.europa.eu/news-events/news/plug-pulled-paris-shared-electric-car-service-autolib-2018-06-28_en) (28/06/2018) |
| Rentabilité promise pour 2018, jamais atteinte | Même source |
| Jusqu'à 300 M€ de pertes prévues sur 5 ans | Même source |
| 4,5 locations par voiture et par jour en 2016 | AFP, juin 2018 ([phys.org](https://phys.org/news/2018-06-paris-slams-electric-car-sharing-scheme.html)) |

« Investissements sous-estimés » est dit à l'oral mais n'est pas écrit sur la slide : nous n'avons pas trouvé de
source chiffrée.

### Slide 4 · Notre réponse (≈ 1 min)

- **Objectif** : annoncer la méthode avant l'outil : trois principes, puis une qualification GO / NO GO.
- **À l'écran** :
  1. **Objectiver les besoins** : population, transports, stations existantes.
  2. **Mesurer la viabilité** : coût, potentiel d'usage, seuil de rentabilité, risques (entretien, dégradations,
     exploitation).
  3. **Préserver l'équité** : utilité sociale, accès aux mobilités.

  En bas : « un arbitrage, pas un seul critère », puis GO (rentable et utile) et NO GO (besoin faible ou non rentable).
- **Où le retrouver dans l'outil** :

| Principe | Dans le rapport Power BI |
|---|---|
| Objectiver les besoins | Pages 2 à 4 : accès par carreau, population desservie, potentiel prédit |
| Mesurer la viabilité | Page 5 (coût, habitants gagnés, coût par habitant) et page 6 (seuil de rentabilité, verdict « Rentable / Non rentable ») |
| Préserver l'équité | Page 5, curseur « Poids équité » (ménages pauvres et sans voiture) |

### Slide 5 · Transition (≈ 25 s)

- **Objectif** : passer la parole au binôme.
- **À l'écran** : « Un outil d'aide à la décision, fondé sur des données fiables » ; identifier les zones
  prioritaires, estimer la valeur d'une implantation, arbitrer sous contrainte de budget.
- **Données** : aucune.

### Puis le deck soutenance (binôme)

| Moment | Contenu | Temps |
|---|---|---|
| Slide 1 · Contexte | Nantes Métropole, et pourquoi : Citiz y est présent mais peu dense | 0:20 |
| Slide 2 · Problème | Part des habitants à 5 min à pied d'une voiture partagée | 0:30 |
| Slide 3 · Solution | Mesurer → prédire → optimiser → décider, dans Microsoft Fabric | 0:40 |
| **Démo** | Rapport Power BI : pages 2, 5 et 6 | 2:45 |
| Slide 4 · Recommandation | Liste priorisée à 500 000 € : stations, habitants gagnés, coût par habitant | 0:45 |

Chiffres : [`docs/chiffres_officiels.md`](../docs/chiffres_officiels.md), calculés dans Fabric (décision du 21/10/2026).

---

## 2. Le rapport Power BI : d'où viennent les données

Rapport `citiz_acces_investissement` (définition dans [`fabric/powerbi/`](../fabric/powerbi/citiz_acces_investissement/)).
Il lit le lakehouse `gold` en **Direct Lake** : aucune donnée n'est importée dans Power BI, chaque visuel lit une table
Delta écrite par un notebook Fabric.

### 2.1 La chaîne, de la source au lakehouse gold

| Source d'origine | Producteur | Table bronze | Table silver | Tables gold qui l'utilisent |
|---|---|---|---|---|
| Carreaux de 200 m (population, niveau de vie, âges), Filosofi 2021 | [INSEE](https://www.insee.fr/fr/statistiques/8735162) | `carreaux`, `carreaux_filosofi` | `fact_carreau_population` | `gold_acces_carreau`, `gold_acces_commune` |
| Population des communes 1876-2023 | [INSEE](https://www.insee.fr/fr/statistiques/fichier/3698339/base-pop-historiques-1876-2023.xlsx) | `population_historique_*` | `fact_population` | Calage de la population (2023) ; `gold_projection_commune` (tendance 2017-2023) |
| Communes et contours | [geo.api.gouv.fr](https://geo.api.gouv.fr/departements) (API Découpage administratif) | `communes` | `dim_commune` | Toutes (rattachement des carreaux, arrêts et stations aux communes) |
| Arrêts de transport en commun (GTFS de tous les réseaux) | [transport.data.gouv.fr](https://transport.data.gouv.fr/api/datasets) | `gtfs_stops` | `dim_arret` | `gold_acces_carreau`, `gold_offre_desservie` |
| Stations Citiz, autopartage, vélos, free-floating (GBFS) | [transport.data.gouv.fr](https://transport.data.gouv.fr/api/datasets) | `gbfs_stations` | `dim_station` | `gold_acces_carreau`, `gold_offre_desservie`, cible du modèle |
| Stations Marguerite (autopartage de Nantes) | [Open data Nantes Métropole](https://data.nantesmetropole.fr) | lue directement par `acces_notebook` | — | `gold_acces_carreau` (couverture autopartage), `gold_offre_desservie` |
| Ménages et voitures, logement 2022 | [INSEE](https://www.insee.fr/fr/statistiques/fichier/8581474/base-cc-logement-2022_csv.zip) | `logement_2022` | `fact_motorisation` | Variable du modèle ; priorité d'équité de l'optimisation |
| Délinquance enregistrée | [SSMSI, data.gouv.fr](https://www.data.gouv.fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales) | `delinquance_communale` | `fact_delinquance` | **Aucune** : retirée le 21/10, on ne pénalise pas un territoire sur ses vols |
| Projections de population Omphale 2021-2070 | [INSEE](https://www.insee.fr/fr/statistiques/fichier/6652134/projdepreg_2021-2070_excel.zip) | `projections_omphale_dep` | — | `gold_projection_commune`, `gold_age_departement` |
| Communes de Nantes Métropole | [geo.api.gouv.fr](https://geo.api.gouv.fr) (EPCI 244400404) | — | — | Filtre de la zone dans `optimisation_notebook` et `acces_notebook` |
| Coûts des équipements | Hypothèses sourcées de [`config/costs.yaml`](../config/costs.yaml) ([`docs/sources_hypotheses.md`](../docs/sources_hypotheses.md)) | — | — | `gold_couts`, `gold_selection` (coût) |
| CO2 évité | ADEME : 10 000 km évités × 142 gCO2e/km, par station et par an (borne basse) | — | — | `gold_selection` |

Les flux domicile-travail (INSEE 2022) vont jusqu'en silver (`fact_flux`) mais ne servent pas dans le rapport.

| Notebook | Lit | Écrit les tables gold du rapport |
|---|---|---|
| `acces_notebook` | silver `dim_arret`, `dim_commune`, `fact_carreau_population`, `fact_population` ; bronze `gbfs_stations`, `carreaux_filosofi` ; Marguerite | `gold_acces_carreau`, `gold_acces_commune`, `gold_offre_desservie` |
| `modele_notebook` | gold `gold_acces_carreau`, `gold_offre_desservie` ; silver `dim_commune`, `fact_motorisation` | `gold_modele_proba_carreau`, `gold_modele_validation`, `gold_modele_importance` |
| `optimisation_notebook` | gold accès, réseau piéton et modèle ; silver `fact_motorisation`, `fact_population` ; bronze `projections_omphale_dep` | `gold_selection`, `gold_resume_optim`, `gold_couts`, `gold_horizons`, `gold_projection_commune`, `gold_age_departement`, `gold_axe_reservations`, `gold_saisie_*` |

### 2.2 Page par page

**Page 1 · France : accès à 5 min**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| Carte « Habitants » | `Habitants` = somme de `pop_calee` | `gold_acces_carreau` | Population Filosofi recalée sur le recensement 2023 de la commune |
| Carte « Options par habitant » | moyenne de `options_ponderees` pondérée par `pop_calee` | `gold_acces_carreau` | Options pondérées à 400 m du carreau : TC 1, Citiz ou autopartage 1,5, vélos 1, free-floating 0,5 par mode |
| Carte « Part sans option » | part de `pop_calee` où `sans_option` | `gold_acces_carreau` | Aucun point d'offre à 400 m |
| Carte « Part à 5 min Citiz » | part de `pop_calee` où `couvert_citiz` | `gold_acces_carreau` | Une station Citiz (GBFS) à 400 m |
| Carte Azure Maps des communes | `lat`, `lon`, `classe_acces`, `pop_calee` | `gold_acces_commune` | Centre de la commune, couleur selon les options par habitant |
| Tableau « Communes » | `nom`, `options_par_habitant`, `part_pop_sans_option`, `part_pop_citiz`, `pop_calee` | `gold_acces_commune` | Agrégat des carreaux de la commune |
| Segment « Département » | `code_dept` | `gold_acces_commune` | Contours des communes (geo.api.gouv.fr) |

**Page 2 · Nantes : diagnostic**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| Carte « Habitants » | somme de `pop_calee` | `gold_acces_carreau` | Comme la page 1 |
| 5 cartes « (marche) » : options par habitant, part sans option, part à 5 min TC, Citiz, autopartage | Mesures sur `options_v2`, `sans_option_v2`, `couvert_tc_v2`, `couvert_citiz_v2`, `couvert_autopartage_v2` | `gold_acces_carreau` | **Marche réelle (V2)** : chemin à pied ≤ 400 m sur le réseau piéton OpenStreetMap (Geofabrik Pays de la Loire, zone + 800 m) ; « autopartage » = Citiz ou Marguerite |
| Carte des carreaux | `lat`, `lon`, `classe_acces_v2` | `gold_acces_carreau` | Carreaux habités, couleur en marche réelle ; les carreaux imputés (moins de 11 ménages) sont masqués |
| Barres « Options par habitant (marche réelle), par commune » | `nom`, `options_par_habitant_v2` | `gold_acces_commune` | Agrégat par commune de la V2 |
| Tableau « Profil social » | `niveau_vie_moyen`, `part_menages_pauvres`, `part_18_24`, `part_65_plus` | `gold_acces_commune` | Filosofi 2021 (bronze `carreaux_filosofi`) agrégé à la commune |

**Page 3 · Nantes : qui est desservi**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| Carte des arrêts et stations | `lat`, `lon`, `famille`, `pop_desservie_v2` | `gold_offre_desservie` | Une ligne par arrêt GTFS (fusionnés à 50 m), station GBFS ou Marguerite ; taille = habitants à 5 min à pied |
| Barres « Nombre de points par type » | `Points` = nombre de lignes, par `famille` | `gold_offre_desservie` | |
| Tableau « Points les plus utiles » | `nom`, `commune`, `famille`, `pop_desservie_v2`, `pop_seule_option_v2` | `gold_offre_desservie` | En marche réelle : habitants à 5 min à pied du point, et ceux pour qui c'est l'unique option. Arrondis à 5, masqués sous 20 |

**Page 4 · Nantes : potentiel prédit**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| Carte du potentiel | `lat`, `lon`, `classe_potentiel` | `gold_modele_proba_carreau` | Probabilité LightGBM qu'un carreau ressemble à un lieu où Citiz est installé ; quintiles parmi les carreaux de la zone |
| Tableau de validation | `evaluation`, `auc_modele`, `auc_densite_seule`, `pr_auc_modele`, `pr_auc_densite_seule` | `gold_modele_validation` | Chaque région prédite sans l'avoir vue ; Grenoble à l'aveugle (Isère retirée) ; comparaison à la densité seule |
| Barres « Ce qui compte pour le modèle » | `variable`, `part_shap` | `gold_modele_importance` | Part de l'importance SHAP de chaque variable |

Cible du modèle : présence d'une station Citiz (GBFS) à 400 m. Variables : population à 400 m et 1 km, offre de TC,
vélos et free-floating, distance au TC (gold accès), ménages sans voiture (`fact_motorisation`), niveau de vie (Filosofi).
Aucune variable de délinquance.

**Page 5 · Nantes : où investir**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| Segments Budget, Équipements, Usage potentiel, Méthode, Poids équité | `budget`, `perimetre`, `scenario`, `methode`, `equite` | `gold_selection` | Un scénario précalculé par combinaison : budget de 50 k€ à 1 M€, glouton ou ILP, avec ou sans modèle, équité 0 ou 0,5 (ménages pauvres et sans voiture) |
| Segment Horizon (ans) | `horizon_ans` | `gold_horizons` | 0, 5, 10 … 30 ans |
| Carte « Emplacements » | `Emplacements` = nombre de lignes | `gold_selection` | |
| Carte « Coût total » | somme de `cout` | `gold_selection` | Investissement + 3 ans d'exploitation (`gold_couts`), identique partout pour un même équipement |
| Carte « Habitants gagnés » | `pop_nouvellement_desservie` × facteur de population de la commune à l'horizon | `gold_selection`, `gold_projection_commune` | Habitants qui passent à 5 min de l'équipement ; facteur = tendance 2017-2023 recalée sur Omphale |
| Carte « Coût par habitant » | Coût total / habitants gagnés à l'horizon | `gold_selection` | |
| Carte « CO2 évité » | somme de `co2_evite_t_an` | `gold_selection` | 1,42 t par station Citiz et par an (ADEME) |
| Carte « Part des 65 ans et plus » | `part_65_plus` de la Loire-Atlantique à l'horizon | `gold_age_departement` | Omphale ; âges publiés seulement pour 2018 et 2070, interpolés |
| Carte Azure Maps des emplacements | `lat`, `lon`, `type`, `pop_nouvellement_desservie` | `gold_selection` | |
| Tableau « Liste priorisée » | `rang`, `nom`, `commune`, `type`, `cout`, `pop_nouvellement_desservie`, `cout_par_habitant`, `proba_citiz`, habitants à l'horizon | `gold_selection` | `proba_citiz` : probabilité au candidat, prédite par un modèle qui n'a pas vu la région de Nantes |
| Courbe « Habitants gagnés selon le budget » | `budget`, `scenario`, `pop_nouvellement_desservie` | `gold_resume_optim` | Un point par palier de budget (glouton, tous équipements) |

**Page 6 · Rentabilité d'une station**

| Visuel | Champ ou mesure | Table gold | Calcul |
|---|---|---|---|
| 8 champs de saisie : véhicules, investissement, amortissement, charges station, charges par véhicule, recette et coût variable par réservation, réservations par véhicule | `valeur` | `gold_saisie_*` | Grilles de valeurs vides : **aucune donnée**, c'est l'utilisateur qui saisit |
| Verdict, charges fixes, marge, seuils, résultat mensuel | Mesures DAX | `gold_axe_reservations` | Charges fixes = charges station + véhicules × charges par véhicule + investissement / (durée × 12) ; seuil = charges fixes / (recette − coût variable) ; verdict « Rentable » si le résultat prévu est ≥ 0 |
| Courbe du résultat mensuel | `reservations_vehicule` | `gold_axe_reservations` | Axe de 0 à N réservations par véhicule ; le seuil est le passage à 0 € |

Rien n'est enregistré : chaque personne fait sa simulation.

**Page 7 · Méthode et limites**

| Visuel | Champ | Table gold | Calcul |
|---|---|---|---|
| Textes de méthode | — | — | Rédigés dans le rapport |
| Tableau « Coûts retenus » | `libelle`, `investissement`, `exploitation_annuelle`, `cout_total`, `source` | `gold_couts` | Scénario moyen de `config/costs.yaml`, sur 3 ans |

### 2.3 À savoir avant la démo

- **V1 ou V2 ?** `acces_notebook` écrit la marche réelle de Nantes dans des colonnes à part (`options_v2`,
  `couvert_*_v2`, `classe_acces_v2`, `pop_desservie_v2`) et garde le vol d'oiseau dans les colonnes sans suffixe.
  Les pages Nantes (2 et 3) lisent la **V2** ; la page 1 (France entière) reste en V1, seule méthode disponible à
  cette échelle (borne haute). Contrôle : la carte « Part à 5 min autopartage (marche) » de la page 2 doit afficher
  19,0 %.
- **Page 5 : marche réelle.** `optimisation_notebook` utilise la couverture V2 (`ACCES = 'v2'`, réseau piéton relu
  dans `gold_reseau_pieton`) ; colonne `acces` de `gold_selection` pour le vérifier. Repli en V1 si le réseau manque.
- **Secret statistique** : carreaux de moins de 11 ménages jamais affichés seuls, populations desservies arrondies à 5
  et masquées sous 20.
