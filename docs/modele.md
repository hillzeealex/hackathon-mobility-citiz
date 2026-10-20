# Modèle : où Citiz s'installe-t-il ?

Commandes (après `python -m src.national.build_all`) :

```bash
python -m src.model.features   # ≈ 30 s -> data/processed/model/features.parquet
python -m src.model.train      # ≈ 2 min -> predictions.parquet, validation.json, shap_importance.csv, docs/figures/modele/
```

## Cible, périmètre, variables

- **Unité** : carreau peuplé de 200 m de France métropolitaine (2 298 581 carreaux).
- **Cible** : au moins une station Citiz à 400 m (vol d'oiseau) du centroïde du carreau (classification).
- **Périmètre d'apprentissage** : les carreaux des **106 EPCI où Citiz est présent** (313 086 carreaux, dont
  11 719 positifs, 3,7 %). Ailleurs, l'absence de station traduit surtout l'absence de l'opérateur.
- **Variables** (aucune ne décrit Citiz) : population calée ; densité du voisinage à 400 m et 800 m ; niveau de vie,
  parts de ménages pauvres, de propriétaires, de logements sociaux ; part de ménages sans voiture ; arrêts de TC et
  options de mobilité hors Citiz à 400 m (V1) ; équipements BPE 2025 à 400 m (total et par domaine) ; vols liés aux
  véhicules pour 1 000 habitants (commune ≥ 10 000 hab., sinon EPCI).
- **Modèle** : LightGBM (400 arbres, taux 0,05, 31 feuilles), `src/model/train.py`.

## Validation

**Spatiale, par réseau régional Citiz** : 15 plis ; à chaque pli, un réseau entier (toutes ses villes) est retiré de
l'apprentissage et prédit. Chaque carreau reçoit donc une prédiction faite sans avoir vu son réseau (`proba_oof`).
Référence : **baseline « densité seule »** (densité du voisinage à 800 m).

| Indicateur (hors réseau) | Modèle | Densité seule |
|---|---:|---:|
| AUC | 0,922 | 0,914 |
| Précision moyenne (AP), taux de base 3,7 % | 0,238 | 0,221 |
| Positifs captés dans le top 10 % des carreaux (France) | 65,5 % | 63,7 % |
| Idem **à l'intérieur de chaque EPCI** (moyenne de 105 EPCI), top 5 % | **69,4 %** | 63,2 % |
| Idem, top 10 % | **82,3 %** | 78,1 % |
| Idem, top 20 % | **92,4 %** | 87,8 % |

**Test à l'aveugle Grenoble** : le pli exclut tout le réseau Citiz Auvergne-Rhône-Alpes (Grenoble compris) ; on
classe les 4 285 carreaux de la métropole.

| Grenoble (sans avoir vu son réseau) | Modèle | Densité seule |
|---|---:|---:|
| AUC (carreaux) | 0,953 | 0,931 |
| Vraies stations (168) dont le carreau est dans le top 5 % | **54,8 %** | 52,4 % |
| … top 10 % | **68,5 %** | 64,9 % |
| … top 20 % | **89,3 %** | 82,1 % |
| Carreaux à station (18 % des carreaux) dans le top 20 % | 77,1 % | 69,7 % |

Lecture : en ne regardant que les 20 % de carreaux les mieux notés de Grenoble, on retrouve 9 stations Citiz sur 10,
sans que le modèle ait vu une seule station de la région. Le gain sur la densité seule est réel mais modeste
(+7 points au top 20 %) : **la densité explique l'essentiel**, le modèle affine (équipements, motorisation, offre).

## Variables importantes (SHAP)

`docs/figures/modele/shap_beeswarm.png`, `shap_importance.png`, `data/processed/model/shap_importance.csv`.
Par ordre : équipements à 400 m, vols liés aux véhicules, part de ménages sans voiture, densité à 800 m, options de
mobilité hors Citiz, équipements de santé, part de propriétaires.

- Plus d'équipements, de densité, de ménages sans voiture et d'offre de mobilité → probabilité plus forte.
- Plus de propriétaires → probabilité plus faible.
- **Vols élevés → probabilité plus faible** dans l'ensemble : association, pas causalité. Le taux est communal ; il
  sert en partie d'identifiant de commune.
- Les équipements BPE du domaine « transports » (gares, taxis, stations-service…) tirent la probabilité vers le bas
  quand ils sont nombreux : effet d'interaction avec les autres comptages d'équipements, à ne pas sur-interpréter.

## Le risque de vol dans les recommandations

Dans l'optimiseur, le risque de vol n'est pas une note donnée aux quartiers : il entre dans le **coût** d'une station.
Surcoût = horizon × assurance et entretien × élasticité × excès du taux de vols de la commune sur le taux médian des
carreaux où Citiz est déjà présent (plafonné). **Hypothèse à valider avec Citiz** (`config/costs.yaml`, bloc `risque_vol`) ;
à Nantes, il ajoute en moyenne environ 1 050 € par station sur 3 ans.

## Limites

1. **Le modèle apprend où Citiz s'est installé, pas la demande pure** : il reproduit les choix passés de l'opérateur
   (centres-villes, quartiers déjà équipés) et ne voit pas une demande non servie ailleurs.
2. Cible à vol d'oiseau (V1) ; variables d'offre en V1.
3. Les EPCI sans Citiz ne servent pas à l'apprentissage ; leurs prédictions (`proba`) sont des extrapolations.
4. L'historique d'usage Citiz est abandonné comme cible (34 photos, 12 changements de disponibilité) : le modèle ne
   prédit pas la fréquentation d'une station.
5. Associations, pas causalités (SHAP explique le modèle, pas le monde).
