# Chiffres officiels pour les slides (source : Microsoft Fabric, 21/10/2026)

Décision de l'équipe du 21/10/2026 : **les chiffres de la soutenance sortent de Fabric** (pipeline `citiz_pipeline`,
espace « Hackathon Citz »), et **aucune donnée de délinquance n'entre dans le calcul** (ni variable du modèle, ni
surcoût). Ce fichier remplace l'encadré « chiffres officiels » de [`chiffres_cles.md`](chiffres_cles.md), qui reste la
référence du pipeline local (calculé avec la délinquance, avant cette décision).

- **Nantes Métropole** : 5 minutes de **marche réelle** (400 m sur le réseau piéton OpenStreetMap, V2).
- **France entière** : 400 m à vol d'oiseau (V1, borne haute) ; la V2 n'existe pas à cette échelle.
- Population : Filosofi 2021 (carreaux de 200 m) calée sur le recensement 2023. Coûts : `config/costs.yaml`, scénario
  moyen, 3 ans (station Citiz : 37 900 €). Optimisation : ILP optimal, stations Citiz, équité 0,5.

| Message | Chiffre officiel |
|---|---:|
| Nantes : habitants | 689 456 |
| Nantes : au moins une option de mobilité à 5 min à pied | **80,7 %** |
| Nantes : à 5 min à pied d'un arrêt de transport en commun | 79,7 % |
| Nantes : à 5 min à pied d'un autopartage (23 Citiz, 62 Marguerite) | **19,0 %** |
| Nantes : à 5 min à pied d'une station Citiz | 7,5 % |
| Nantes : habitants dont la seule option à 5 min est un unique arrêt ou station | 107 205 |
| 250 000 € : stations Citiz · habitants gagnés | 6 · +12 515 |
| **500 000 € : stations Citiz recommandées** | **13** |
| **500 000 € : habitants gagnés (nouvellement à 5 min à pied d'un autopartage)** | **+22 510** |
| 500 000 € : couverture autopartage avant → après | **19,0 % → 22,3 %** |
| 500 000 € : coût par habitant gagné (sur 3 ans) | **21,9 €** |
| 500 000 € : CO2 évité (estimation prudente) | 18,5 t/an |
| 1 000 000 € : stations · habitants gagnés · couverture après | 26 · +50 290 · 26,3 % |
| Modèle, test à l'aveugle Grenoble : part des carreaux Citiz retrouvés en haut de liste | **67,5 %** (densité seule 63,7 %) |
| Modèle, test à l'aveugle Grenoble : AUC · précision moyenne | 0,935 · 0,746 (densité seule 0,929 · 0,749) |
| France entière : habitants sans aucune option à 5 min (V1, borne haute : le dire) | 24,1 % |

**Cités depuis le pipeline local** (méthode, non recalculés dans Fabric) : à Grenoble, le vol d'oiseau surestime les
options de **80 %** ; en marche réelle, 89,2 % des Grenoblois ont une option à 5 min et 39,7 % une station Citiz
([`chiffres_cles.md`](chiffres_cles.md), section 3).

## Pourquoi ces chiffres diffèrent de l'ancien encadré

Le diagnostic de Nantes est identique (80,7 % contre 80,6 %, 19,0 % contre 19,0 %) : même réseau piéton, mêmes points
d'offre. Les recommandations changent (13 stations, +22 510 habitants, contre 12 et +34 979) pour deux raisons :

1. **Plus de délinquance** : le modèle local utilisait les vols de véhicules comme variable et comme surcoût.
2. **Un autre modèle** : celui de Fabric apprend sur tous les carreaux de métropole, sans les équipements BPE ; pour
   Nantes, sa probabilité est prédite par un modèle qui n'a pas vu la région (comme `proba_oof` en local).

## Reproduire

Exécuter `citiz_pipeline` dans Fabric (Bronze désactivé), puis lire les tables `gold` : `gold_acces_carreau`
(colonnes `*_v2`), `gold_resume_optim` (`methode = ILP`, `perimetre = citiz_station`, `equite = 0.5`),
`gold_modele_validation`. Le rapport Power BI `citiz_acces_investissement` affiche les mêmes valeurs (page 5 :
budget 500 000 €, stations Citiz, avec modèle, ILP, équité 0,5).
