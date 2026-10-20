# Slides

Présentation du projet (livrable du hackathon) : en préparation.

Prévu : un deck Marp (`slides.md`, exportable en PDF / PPTX) pour un public non technique, avec :

1. Le problème : qui a vraiment accès à une option de mobilité à 5 minutes à pied ?
2. La carte d'accès France entière et le classement des agglomérations à fort potentiel Citiz.
3. Le zoom Grenoble (+ 2 agglomérations) : marche réelle, offre par type, population desservie.
4. Le modèle et l'optimiseur : où ajouter des stations pour un budget donné.
5. L'impact (CO2, équité) et les limites (données, éthique).

---

## Périmètre : la France, DROM compris quand la donnée existe

Le sujet couvre la France « DROM inclus ». La carte nationale (objectifs 1 et 2) intègre donc les DROM dès que la population au carreau existe. La recommandation (objectif 3) porte sur la métropole.

| Territoire | Population au carreau 200 m | Sur la carte | Stations Citiz |
|---|---|---|---|
| Métropole | oui | oui | 1 617 |
| Martinique, La Réunion | oui | oui | 0 |
| Guadeloupe, Guyane, Mayotte | **non** | en gris, offre seule | 0 |

**Phrase pour la soutenance :**

> « La carte couvre la métropole, la Martinique et La Réunion. La Guadeloupe, la Guyane et Mayotte apparaissent en gris : l'INSEE n'y publie pas la population au carreau, et nous refusons d'afficher comme « mal desservis » des territoires qui sont surtout mal documentés. Citiz n'étant présent dans aucun DROM, la recommandation porte sur la métropole. »

- **Lien avec la grille éthique :** c'est le point « ne pas stigmatiser un territoire ».
- **Diapo « Limites et suite » :** la Guyane a 42 % de ménages sans voiture, le plus fort taux de France, et c'est là que la donnée manque le plus.

### Sources

- **Couverture des DROM :** [`docs/methodologie.md`](../docs/methodologie.md), section « Couverture des DROM ».
- **Population au carreau :** [INSEE, Filosofi 2021](https://www.insee.fr/fr/statistiques/8735162) (métropole, Martinique, La Réunion seulement).
- **Ménages sans voiture en Guyane :** [INSEE, recensement 2023, Logement à l'IRIS](https://www.insee.fr/fr/statistiques/9061333).
- **Stations Citiz :** flux GBFS des réseaux Citiz, [transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=vehicles-sharing&q=citiz).

---

## Choix des territoires

Chiffres : classement national des EPCI (`france_classement_epci.csv`, release `donnees-v1`).

| | Grenoble | Nantes | Nice |
|---|---|---|---|
| Rôle | Entraîner et valider le modèle | Recommander : densifier Citiz | Écarté (piste « sans Citiz ») |
| Rang potentiel Citiz | 61 | 58 | 1 |
| Habitants | 451 000 | 689 000 | 574 000 |
| Stations Citiz | 168 | 23 | 0 |
| Stations Citiz pour 100 000 hab. | 37,3 | 3,3 | 0 |
| Population à 5 min d'une station Citiz | 53 % | 11,8 % | 0 % |
| Population sans aucune option à 5 min | 3,6 % | 6,7 % | 3,9 % |
| Ménages sans voiture | 24,0 % | 20,4 % | 28,7 % |

### Pourquoi Grenoble pour entraîner le modèle

- **Le réseau Citiz le plus dense de France :** 168 stations, 37 pour 100 000 habitants, et la moitié de la population à 5 min d'une station. C'est le plus grand nombre d'exemples pour apprendre où une station fonctionne.
- **Des données propres :** le réseau de bus et tram TAG ne présente aucune anomalie au validateur national, et la population est recalée sur le recensement. Le jeu nettoyé est publié (release `donnees-v1`).
- **Les quatre types d'offre présents :** transports en commun, vélo, trottinette, Citiz.
- **Un relief marqué :** l'écart entre la distance à vol d'oiseau et la marche réelle y est un vrai enjeu, ce qui teste la méthode.
- **Mais pas un terrain de recommandation :** le réseau est déjà saturé, et une nouvelle station toucherait surtout des gens déjà desservis.

### Pourquoi Nantes pour recommander

- **Le plus gros retard parmi les villes où Citiz est déjà là :** 3,3 stations pour 100 000 habitants, 11 fois moins qu'à Grenoble.
- **Un vrai besoin :** 6,7 % de la population n'a aucune option à 5 min, le plus fort taux des grandes métropoles comparées.
- **Citiz est présent :** les 23 stations existantes permettent de vérifier les recommandations sur le terrain.
- **Une taille raisonnable :** 689 000 habitants, faisable en 2,5 jours.
- **Bordeaux étudiée puis écartée :** c'est le territoire le mieux desservi (98 % de la population a un transport en commun à 5 min), avec moins de gain par station ajoutée.

### Pourquoi pas Nice, malgré son rang n°1

- **Le rang n°1 est en partie un artefact :** le score récompense l'absence d'autopartage *visible*. Or plusieurs opérateurs (Getaround, Zity, Communauto…) ne publient pas de données ouvertes. « Pas d'autopartage visible » ne veut pas dire « pas d'autopartage ».
- **Aucune station Citiz :** impossible de vérifier le modèle sur le terrain local.
- **Un territoire très étendu :** 1 477 km², du littoral dense à l'arrière-pays de montagne, beaucoup plus difficile à traiter en 2,5 jours.
- **À garder en perspective :** c'est le meilleur candidat pour le cas « où et comment Citiz pourrait s'installer ».

### Sources

- **Tous les chiffres du tableau**, plus la superficie de Nice et les 98 % de Bordeaux : classement national des EPCI, `france/france_classement_epci.csv` de la [release `donnees-v1`](https://github.com/hillzeealex/hackathon-mobility-citiz/releases/tag/donnees-v1), produit par `src/national/ranking.py`. Il croise les sources ci-dessous.
- **Stations Citiz :** flux GBFS des réseaux Citiz, [transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=vehicles-sharing&q=citiz).
- **Arrêts de transport :** [Arrêts de transport en France](https://www.data.gouv.fr/datasets/arrets-de-transport-en-france) (agrégat GTFS national) et GTFS des réseaux sur [transport.data.gouv.fr](https://transport.data.gouv.fr/datasets?type=public-transit).
- **Population au carreau de 200 m :** [INSEE, Filosofi 2021](https://www.insee.fr/fr/statistiques/8735162).
- **Habitants et ménages sans voiture :** [INSEE, recensement 2023, Logement à l'IRIS](https://www.insee.fr/fr/statistiques/9061333).
- **Contours des communes, EPCI et IRIS :** [IGN, ADMIN EXPRESS](https://geoservices.ign.fr/adminexpress).
- **Choix de Grenoble** (GTFS TAG sans anomalie, relief) **et limite sur les opérateurs d'autopartage sans données ouvertes :** [`docs/methodologie.md`](../docs/methodologie.md).

---

## Estimation du coût d'une station Citiz

Source : `config/costs.yaml` (scénario moyen, euros HT).

| Équipement | Investissement (moyenne) | Exploitation par an (moyenne) | Solidité |
|---|---|---|---|
| Station Citiz (1 voiture + 1 place) | voiture 22 k€ + aménagement 1,5 k€ | assurance et entretien 1,7 k€, gestion 2,5 k€, place 600 € | presque tout « à valider » |

- **Coût sur 3 ans :** 23,5 k€ d'investissement + 3 × 4,8 k€ d'exploitation, soit **≈ 38 k€ par station**.
- **Qui paie :** chez Citiz, la voiture est souvent financée par la coopérative et la place fournie par la collectivité. Le coût pour la collectivité peut se limiter à la place et à l'aménagement.
- **À confirmer avec Citiz :** leur coût réel d'ouverture d'une station remplacerait toutes les hypothèses.

### Sources

- **Assurance et entretien (1,7 k€/an) :** ordres de grandeur pour un particulier (assurance 600-900 €/an, entretien 500-1 200 €/an), [Transition Vélo](https://www.transitionvelo.com/?p=32352). Le coût pour une flotte reste à valider.
- **Voiture, aménagement, gestion et place :** pas de source, ce sont des « hypothèses à valider » dans [`config/costs.yaml`](../config/costs.yaml).
- **Horizon de 3 ans et répartition coopérative / collectivité :** hypothèses de l'équipe, dans [`config/costs.yaml`](../config/costs.yaml).
- **Liste complète des sources de coûts :** [`docs/sources_hypotheses.md`](../docs/sources_hypotheses.md).

---

## Limites à assumer devant le jury

- **Arrêts en double :** le fichier national des arrêts contient des doublons, un même arrêt pouvant apparaître dans plusieurs jeux. On les fusionne par position.
- **Offre, pas usage :** le GBFS est une photo de l'offre à un instant. La collecte toutes les 5 minutes sert à estimer l'usage réel des stations Citiz.
- **Autopartage invisible :** Getaround, Zity, Communauto… ne publient pas de données ouvertes. Le classement surestime le potentiel des villes où ils sont présents.
- **Coûts hypothétiques :** la plupart des coûts sont des hypothèses sourcées, pas les coûts réels de Citiz.
- **Échelle :** les voitures par ménage sont connues à l'IRIS, une échelle plus grossière que les carreaux de 200 m.
- **Accès à vol d'oiseau au niveau national :** 400 m à vol d'oiseau surestime l'accès. La marche réelle sur le réseau OpenStreetMap n'est calculée que sur les agglomérations zoomées.

### Sources

- **Doublons, rayon de fusion et accès à vol d'oiseau :** [`docs/methodologie.md`](../docs/methodologie.md) et [`config/settings.yaml`](../config/settings.yaml).
- **Arrêts de transport :** [Arrêts de transport en France](https://www.data.gouv.fr/datasets/arrets-de-transport-en-france) (« non dédupliqué », selon le producteur).
- **Opérateurs d'autopartage sans données ouvertes :** [`docs/methodologie.md`](../docs/methodologie.md), section du classement des EPCI.
