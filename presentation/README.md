# Notes pour la présentation

Notes de travail de l'équipe pour préparer la soutenance. Chacun complète sa partie.

## Périmètre : France métropolitaine, sans les DROM

Le sujet couvre la France « DROM inclus », mais autorise à restreindre l'analyse si le choix est justifié. Nous l'écartons explicitement.

**Phrase pour la soutenance :**

> « Nous nous concentrons sur la France métropolitaine. Dans les DROM, les données nécessaires à une analyse fine sont incomplètes, et Citiz n'y est présent nulle part, ce qui empêche de vérifier le modèle. Une carte partielle des DROM risquerait de présenter comme « mal desservis » des territoires qui sont surtout mal documentés. »

**Les chiffres derrière ce choix** (recensement 2023, arrêts GTFS, flux GBFS) :

| Territoire | Habitants | Ménages sans voiture | Population au carreau 200 m | Arrêts TC | Mobilité partagée |
|---|---|---|---|---|---|
| La Réunion | 890 000 | 25 % | oui | 5 647 | 36 stations vélo (Saint-Pierre) |
| Martinique | 361 000 | 25 % | oui | 5 911 | 24 stations Clem (autopartage) |
| Guadeloupe | 384 000 | 28 % | **non** | 1 747 | 17 stations vélo |
| Guyane | 294 000 | **42 %** | **non** | 538 | aucune |
| Mayotte | 257 000 | pas de données | **non** | **0** | aucune |

- Citiz : 0 station dans les DROM.
- La population au carreau de 200 m (INSEE Filosofi) n'existe que pour la métropole, la Martinique et La Réunion.

**Lien avec la grille d'évaluation (éthique) :** écarter les DROM évite de stigmatiser des territoires mal documentés comme « mal desservis ».

**Diapo « Limites et suite » :** la Guyane a 42 % de ménages sans voiture, le plus fort besoin de France, mais c'est là que la donnée manque le plus. C'est la piste à suivre en priorité si les données s'améliorent.

## Territoire pour la recommandation (objectif 3) : proposition Nantes Métropole

À valider en équipe.

- **Retard Citiz :** 3,1 stations pour 10 000 ménages sans voiture, contre 25 à Strasbourg et 34,5 à Grenoble. Pour un non-technicien : « Nantes a 8 fois moins de Citiz que Strasbourg pour le même besoin ».
- **Besoin :** 73 300 ménages sans voiture (22 %).
- **Citiz déjà présent :** 23 stations, ce qui permet de vérifier le modèle sur le terrain.
- **Données complètes :** arrêts de bus et de tram, vélos Naolib, tarifs de 93 parkings (base nationale des lieux de stationnement).
- **Taille raisonnable :** 690 000 habitants.
- **Alternative :** Toulouse, avec plus de besoin en volume (108 000 ménages sans voiture) et une aide locale de 1 000 € pour passer à Citiz.

## Limites à assumer

- Le fichier national des arrêts contient des doublons : un même arrêt peut apparaître dans plusieurs jeux. On déduplique par position.
- Le GBFS est une photo de l'offre à un instant, pas de l'usage réel. La collecte toutes les 5 minutes sert à estimer l'usage.
- Les coûts d'installation sont des hypothèses sourcées (voir `../hypotheses_couts.csv`), pas des coûts réels Citiz.
- Les voitures par ménage sont données à l'IRIS, une échelle plus grossière que les carreaux de 200 m.

## Notes de l'équipe

<!-- Ajoutez vos notes ici : partie traitée, chiffres clés, questions possibles du jury. -->
