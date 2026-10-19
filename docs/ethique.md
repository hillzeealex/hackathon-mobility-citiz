# Éthique

Ce document accompagne l'outil d'aide à la décision. Il couvre quatre enjeux : vie privée, stigmatisation
des territoires, équité, et impact environnemental (CO₂).

## 1. Vie privée et secret statistique

Les données de population sont fines (carreaux de 200 m). Dans les zones peu peuplées, un carreau peut
correspondre à quelques foyers identifiables. Nous appliquons les règles suivantes.

| Règle | Application | Où |
|---|---|---|
| Aucun carreau de **moins de 11 ménages** affiché isolément | Seuil du secret statistique INSEE, paramètre `privacy.min_households` | application (carte en carreaux), exports partagés |
| Affichage public à l'**IRIS** | Échelle par défaut de la carte ; agrégats IRIS dans les exports | application, `data/share/` |
| **Effectifs IRIS arrondis à 5 près** dans les exports partagés | Empêche de retrouver par différence (total IRIS − carreaux affichés) un carreau masqué : 18 IRIS ne masquaient qu'un seul carreau | `scripts/export_share.py` |
| IRIS de moins de 11 ménages exclus des exports | 2 IRIS concernés | `data/share/` |
| Calculs sur les valeurs exactes | Les carreaux masqués restent dans les couvertures, les indicateurs et l'optimisation : les masquer fausserait les résultats sans protéger personne | `data/processed/` (jamais versionné) |

Remarques :

- **Données déjà estimées.** Dans le fichier Filosofi public, les carreaux de moins de 11 ménages sont
  déjà des **estimations INSEE** (`i_est_200 = 1`). L'arrondi ajoute une protection, par cohérence avec
  notre règle d'affichage, plutôt qu'il ne corrige une fuite.
- **Arrondi des effectifs seulement.** Les ratios (part de ménages sans voiture, niveau de vie moyen) sont
  calculés sur les valeurs exactes puis publiés à l'IRIS. Un ratio à l'IRIS ne permet pas de remonter à un
  ménage.
- **Données brutes jamais publiées.** Les données brutes et intermédiaires (`data/`) ne sont jamais
  versionnées. Seuls le dictionnaire et la carte d'aperçu, construits sur les données filtrées, sont
  dans le dépôt.
- **Usage Citiz.** L'historique de disponibilité des stations Citiz est agrégé par station. Il ne
  contient aucune donnée de réservation ni d'usager.

## 2. Ne pas stigmatiser les territoires

- **Vocabulaire.** L'interface parle de « **potentiel d'amélioration** », jamais de zone « mal desservie »
  ou « en retard ».
- **Indicateur.** Il mesure une **offre** de mobilité à 5 minutes à pied, pas la qualité d'un quartier ni
  de ses habitants.
- *(À compléter en phase 8 : précautions de présentation des cartes et des classements.)*

## 3. Équité entre territoires denses et peu denses

- **Paramètre d'équité.** Le paramètre d'équité de l'optimiseur donne un bonus aux zones peu desservies
  ou à faible revenu. Sa valeur est un **choix politique** laissé à l'utilisateur ; la valeur 0 maximise
  la population desservie.
- *(À compléter en phase 8 : effet du paramètre sur la répartition centre / périphérie.)*

## 4. Impact environnemental (CO₂ évité)

- **Estimation prudente.** Seules les stations Citiz donnent lieu à un calcul : 10 000 km de voiture
  personnelle évités par véhicule et par an, avec le facteur d'émission bas. Ce sont les bornes basses de
  l'enquête ADEME 2022 (`config/costs.yaml`).
- **Aucun chiffre non vérifié.** Aucun chiffre du livre blanc Citiz 2026 n'est utilisé tant qu'il n'a pas
  été vérifié.
- *(À compléter en phase 8 : limites, effet rebond, fabrication des véhicules.)*
