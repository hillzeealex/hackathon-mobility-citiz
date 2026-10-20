# Chiffres Clés du Projet · Citiz & Mobilité Métropolitaine

Ce document consigne les indicateurs officiels validés pour l'agglomération prioritaire de **Nantes Métropole**, ainsi que les résultats de l'exploration du nouveau scénario « Flottes professionnelles & B2B ».

---

## 1. Diagnostic Territorial & Réseau Citiz Existant (Nantes Métropole)

- **Population totale (recensée et calée Filosofi 2021)** : 689 000 habitants (zone d'étude de la métropole).
- **Offre autopartage en service (V2, Citiz + Marguerite)** : 85 stations opérationnelles (23 stations Citiz officielles + 62 stations Marguerite / autopartage en boucle fermée).
- **Population couverte à 5 min à pied (400 m)** : 396 093 habitants (**27,0 %** de la population métropolitaine).
- **Emplois couverts à 5 min à pied** : 135 348 emplois (**38,7 %** des emplois métropolitains).

---

## 2. Recommandation d'Investissement Officielle · Scénario Particuliers (Budget 500 000 €)

> **Important** : Les chiffres du scénario « Particuliers » constituent la référence officielle inchangée du projet.

- **Hypothèse de coût complet par station (TCO sur 3 ans, `config/costs.yaml`)** :
  - Aménagement & raccordement voirie / pôle d'échange : 1 500 € à 3 000 €
  - Achat véhicule Citiz : 22 000 €
  - Exploitation sur 3 ans (assurance, entretien, télématique, gestion, stationnement) : 14 400 € à 18 000 €
  - Coût unitaire moyen : **≈ 41 500 €** (P+R et Pôles multimodaux) / **37 900 €** (Voirie dense).
- **Nombre de stations déployées sous budget (500 k€)** : **12 stations**.
- **Budget total engagé** : **487 200 €**.
- **Nouveaux habitants desservis à 5 min** : **117 426 habitants**.
- **Emplois situés à 5 min de ces nouvelles stations** : **18 766 emplois**.
- **Population totale bénéficiaire** : **136 192 personnes**.
- **Efficience économique** : **4,15 € par habitant** (ou **3,58 € par personne globale**).
- **Impact environnemental estimé** : **17,0 tCO₂e évitées par an** (hypothèse ADEME prudente).

---

## 3. Scénario Professionnel (Exploratoire) · Flottes d'Entreprises & B2B

Dans l'optique d'ouvrir l'autopartage Citiz aux déplacements professionnels en journée et aux flottes partagées d'entreprises, nous avons intégré les données d'emploi de la **Base Sirene géolocalisée (2024)** et les **Zones d'Activité Économique (Open Data Nantes Métropole)**.

### Contrôle de cohérence statistique (Sirene vs INSEE)
- **Établissements actifs géocodés dans Nantes Métropole** : 129 975 établissements.
- **Emplois estimés par la méthode des milieux de tranches d'effectifs INSEE** : 376 819,5 emplois bruts.
- **Emplois rattachés et agrégés sur la grille carroyée de 200 m** : **350 059,5 emplois**.
- **Total de référence INSEE (Emploi au lieu de travail, RP 2021)** : **357 000 emplois**.
- **Écart de calage** : **-1,94 %** (excellente représentativité spatiale de la base géocodée).

### Diagnostic d'accès pour les actifs
- **Emplois actuellement couverts à 5 min d'un autopartage** : **135 348 emplois** (soit **38,7 %** du total métropolitain).
- **Emplois hors d'atteinte piétonne de l'autopartage** : **214 711 emplois** (61,3 %).

### Top 10 des pôles d'emploi sans autopartage à 5 min à pied
*(Agrégats stricts par zone d'activité, aucune entreprise nommée individuellement)*

| Rang | Pôle d'activité économique | Emplois non couverts | Emplois totaux de la zone | % non couvert |
|:---:|:---|:---:|:---:|:---:|
| **1** | Pôle Commercial & Tertiaire Atlantis - ZAC d'Armor (Saint-Herblain) | 20 582 | 20 582 | 100,0 % |
| **2** | Pôle Tertiaire Nantes Nord - Santos Dumont / Pont du Cens (Nantes) | 13 055 | 13 055 | 100,0 % |
| **3** | Pôle Commercial & d'Activités Ragon / Océane (Rezé) | 11 032 | 11 032 | 100,0 % |
| **4** | Parc Tertiaire Ar Mor (Saint-Herblain Nord) | 8 455 | 8 455 | 100,0 % |
| **5** | Pôle Aéronautique & Logistique Aéroport - D2A (Bouguenais) | 7 981 | 8 923 | 94,7 % |
| **6** | Zone Industrielle & Artisanale de la Lorie (Saint-Herblain) | 5 596 | 5 596 | 100,0 % |
| **7** | Pôle Économique Jules Verne - Beaujoire Est (Nantes Erdre) | 5 087 | 5 087 | 100,0 % |
| **8** | Zone Industrielle de la Belle-Étoile (Carquefou) | 4 946 | 4 946 | 100,0 % |
| **9** | Technopole Atlanpole - Campus La Chantrerie (Nantes) | 4 662 | 4 662 | 100,0 % |
| **10** | Pôle Tertiaire Île de Nantes Sud / Beaulieu | 4 252 | 4 252 | 100,0 % |

---

## 4. Tableau Comparatif des 3 Scénarios d'Optimisation (Budget 500 k€)

Formule d'objectif dans l'optimiseur ILP :  
$$\text{Score}_i = \text{Habitants}_i + \alpha \times \text{Emplois}_i$$

- **Particuliers ($\alpha = 0$)** : priorité résidents (soirée/week-end).
- **Mixte ($\alpha = 0,3$)** : équilibre résidents et trajets professionnels de journée (hypothèse documentée dans `config/settings.yaml`).
- **Pros (100 % Emplois)** : maximisation de la desserte des zones d'emploi pour flottes B2B.

### Synthèse des performances

| Indicateur | 1. Particuliers (officiel, $\alpha = 0$) | 2. Mixte (recommandé, $\alpha = 0,3$) | 3. Pros (flottes 100% B2B) |
|:---|:---:|:---:|:---:|
| **Stations déployées** | **12** | **12** | **12** |
| **Budget investi** | 487 200 € | 487 200 € | 494 400 € |
| **Habitants nouvellement desservis** | **117 426** | **117 426** | 88 623 |
| **Emplois nouvellement desservis** | 18 766 | 18 766 | **29 406** *(+56,7 %)* |
| **Bénéficiaires totaux (hab. + emplois)** | 136 192 | 136 192 | 118 029 |
| **Coût par habitant** | **4,15 €** | **4,15 €** | 5,58 € |
| **Coût par personne globale** | **3,58 €** | **3,58 €** | 4,19 € |
| **Stations communes avec « Particuliers »** | 12 / 12 (100 %) | **12 / 12 (100 %)** | **7 / 12 (58 %)** |

### Comparaison des 12 stations sélectionnées

| ID Candidat | Emplacement & Commune | Catégorie | Scénario Particuliers | Scénario Mixte | Scénario Pros |
|:---|:---|:---|:---:|:---:|:---:|
| `cand_hub_73` | Médiathèque Jacques Demy (Nantes) | Pôle Multimodal | **#1** | **#1** | **#1** |
| `cand_dens_82` | Quartier Île de Nantes - République | Zone Résidentielle | **#2** | **#2** | — *(sort)* |
| `cand_hub_70` | Gare de Rezé Pont-Rousseau (Rezé) | Pôle Multimodal | **#3** | **#3** | — *(sort)* |
| `cand_hub_67` | Vincent Gâche - Île de Nantes (Nantes) | Pôle Multimodal | **#4** | **#4** | **#2** |
| `cand_dens_83` | Quartier Île de Nantes - Beaulieu | Zone Résidentielle | **#5** | **#5** | **#4** |
| `cand_dens_84` | Quartier Trentemoult (Rezé) | Zone Résidentielle | **#6** | **#6** | — *(sort)* |
| `cand_hub_71` | Hangar à Bananes - Quai des Antilles | Pôle Multimodal | **#7** | **#7** | — *(sort)* |
| `cand_pr_24` | P+R Gréneraie (Nantes Sud) | Parking-Relais P+R | **#8** | **#8** | — *(sort)* |
| `cand_pr_37` | P+R Trentemoult-Roquios (Rezé) | Parking-Relais P+R | **#9** | **#9** | **#12** |
| `cand_pr_46` | P+R 8 Mai (Rezé) | Parking-Relais P+R | **#10** | **#10** | **#7** |
| `cand_hub_66` | Gare de Chantenay (Nantes Ouest) | Pôle Multimodal | **#11** | **#11** | **#3** |
| `cand_pr_12` | P+R Duguay Trouin (Saint-Herblain) | Parking-Relais P+R | **#12** | **#12** | **#8** |
| `cand_hub_63` | François Mitterrand - Atlantis (Saint-Herblain) | Pôle Multimodal | — | — | **#5** *(entre)* |
| `cand_hub_61` | Haluchère - Batignolles (Nantes Est) | Pôle Multimodal | — | — | **#6** *(entre)* |
| `cand_hub_77` | Bourg de Saint-Herblain (Centre) | Pôle Multimodal | — | — | **#9** *(entre)* |
| `cand_pr_53` | P+R François Mitterrand (Saint-Herblain) | Parking-Relais P+R | — | — | **#10** *(entre)* |
| `cand_hub_74` | Campus Tertre - Facultés (Nantes Nord) | Pôle Multimodal | — | — | **#11** *(entre)* |

### Enseignement stratégique pour Citiz
1. **Convergence Particuliers - Mixte** : À $\alpha = 0,3$, les 12 stations retenues sont identiques au scénario officiel particuliers. Cela prouve que le plan de déploiement officiel est **robuste et à double dividende** : il dessert massivement les résidents tout en captant déjà 18 766 emplois de proximité.
2. **Pivots du scénario Pros** : Lorsque l'optimiseur se focalise exclusivement sur les flottes B2B (scénario Pros), il bascule 5 stations vers les grands carrefours économiques périphériques (Atlantis / François Mitterrand, Haluchère - Batignolles, Campus Tertre), augmentant les emplois desservis de **+56,7 %** (29 406 emplois).

---

## 5. Limites Méthodologiques à Documenter

- **Calibrage du modèle prédictif** : Le modèle prédictif d'usage LightGBM a été entraîné sur l'historique d'utilisation de stations Citiz à dominante résidentielle. Les flux de déplacements professionnels (trajets inter-entreprises, missions, horaires de bureaux) obéissent à des rythmes différents non calibrés dans le modèle actuel.
- **Secret statistique & RGPD** : Conformément à la déontologie du projet, aucune entreprise n'est identifiée nominativement ; les emplois sont traités exclusivement sous forme d'agrégats anonymisés par carreau de 200 m et par zone d'activité économique.
