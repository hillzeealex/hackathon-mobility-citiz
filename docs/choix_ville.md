# Choix des villes

Décision (20/10/2026) : **Nantes = ville de recommandation**, **Grenoble = ville exemple et test à l'aveugle**,
**Nice = contre-exemple** (documentation seulement). Voir [`decisions.md`](decisions.md).

Source des chiffres : `data/processed/national/classement_epci.parquet`, produit par
`python -m src.national.build_all` (recalculé le 20/10/2026). Accessibilité **V1** (400 m à vol d'oiseau, borne
haute). Classement : 276 EPCI d'au moins 50 000 habitants ; score = moyenne des rangs-percentiles de la densité vécue,
de la part de ménages sans voiture et de l'autopartage existant (faible = mieux). Vols : SSMSI, faits enregistrés
2023-2025, moyenne annuelle pour 1 000 habitants.

| | Grenoble-Alpes-Métropole | **Nantes Métropole** | Métropole Nice Côte d'Azur |
|---|---:|---:|---:|
| Rôle | exemple, test à l'aveugle | **recommandations** | contre-exemple |
| Habitants (carreaux calés) | 450 608 | **689 456** | 574 287 |
| Densité vécue (hab./km²) | 10 919 | 8 665 | 14 232 |
| Ménages sans voiture | 24,0 % | 20,4 % | 28,7 % |
| Niveau de vie moyen (€/an) | 25 511 | 26 353 | 24 908 |
| Stations Citiz (véhicules) | 168 (444) | **23 (37)** | 0 |
| Stations Citiz pour 100 000 hab. | 37,3 | **3,3** | 0 |
| Population à 5 min d'une station Citiz (V1) | 53,0 % | **11,8 %** | 0 % |
| Options pondérées à 5 min par habitant (V1) | 16,9 | 8,5 | 13,2 |
| Population sans aucune option (V1) | 3,6 % | 6,7 % | 3,9 % |
| Population à 5 min d'un arrêt de TC (V1) | 95,5 % | 93,3 % | 96,0 % |
| Vols liés aux véhicules / 1 000 hab. / an | 19,1 | 13,6 | 6,6 |
| Dégradations / 1 000 hab. / an | 11,7 | 8,0 | 8,7 |
| Rang potentiel Citiz (/276) | 61 | 58 | **1** |
| Rang avec pénalité de risque de vol | 130 | 122 | 5 |

## Pourquoi Nantes pour les recommandations

- **Densification réelle** : Citiz y est déjà implanté (23 stations) mais 11 fois moins dense qu'à Grenoble
  (3,3 stations pour 100 000 habitants contre 37,3) ; seuls 11,8 % des habitants ont une station à 5 minutes
  (borne haute V1). La marge de progression est la plus forte des trois villes, sur un opérateur qui existe déjà.
- **Taille** : la plus grande des trois (689 000 habitants calés), dense au centre, avec un bon réseau de TC
  (93 % de la population à 5 min d'un arrêt en V1) : l'autopartage y complète les transports en commun.
- **Risque modéré** : vols liés aux véhicules plus faibles qu'à Grenoble (13,6 contre 19,1 pour 1 000 habitants).
- **Données** : GTFS Naolib, GBFS Citiz et vélos, extrait OSM `pays-de-la-loire`. Les autres opérateurs
  d'autopartage (Marguerite, Getaround) ne publient pas de GBFS : à chercher dans la cartographie de Nantes
  Métropole (étape 2), sinon limite documentée.

## Pourquoi Grenoble comme exemple

Citiz y est le plus dense des trois (168 stations, 53 % des habitants à 5 minutes en V1) : c'est la ville où le
modèle peut être **testé à l'aveugle** (les stations existantes servent de vérité terrain) et où la comparaison
V1 / V2 est déjà faite (la V1 surestime les options de 80 % ; voir `docs/methodologie.md`).

## Pourquoi Nice est un contre-exemple

Nice arrive **1ʳᵉ** du classement (densité vécue la plus forte, 28,7 % de ménages sans voiture, aucun autopartage
visible, risque de vol faible), mais ce rang illustre surtout les **limites du score** :

- **Autopartage invisible** : le critère « peu d'autopartage existant » ne voit que les opérateurs qui publient un
  GBFS (Citiz, Clem, Rémi, Optymo, Leo&Go). Un « 0 » à Nice signifie « rien en open data », pas forcément
  « rien sur le terrain » (non vérifié pour Nice).
- **Implantation ex nihilo** : sans aucune station Citiz, il n'y a ni réseau local ni données d'usage pour
  calibrer ; le modèle (étape 3) prédit « où Citiz s'installerait », pas une demande observée sur place.
- **Message pour le pitch** : un bon score de potentiel ne suffit pas ; la décision d'implantation demande une
  vérification terrain du marché existant. Nice est donc documentée, sans calcul dédié.
