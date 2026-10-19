## Hypothèses de coût et d'impact (config/costs.yaml)

Chaque valeur de `config/costs.yaml` renvoie à l'une de ces sources ou est marquée « hypothèse à valider ».

- [S1] ADEME / 6t, *Enquête nationale sur l'autopartage 2022* : 1 voiture en autopartage remplace 5 à 8 voitures personnelles, supprime 10 000 à 19 000 km/an, libère 0,9 à 3 places — <https://www.ort.bourgogne-franche-comte.developpement-durable.gouv.fr/IMG/pdf/ademe_cp_autopartage_22092022.pdf>, rapport complet <https://www.ort.bourgogne-franche-comte.developpement-durable.gouv.fr/IMG/pdf/enquete-autopartage-2022-rapport.pdf>
- [S2] GART, coût moyen d'un vélo en libre-service 2 000 à 3 000 €/vélo/an, cité par la Banque des Territoires — <https://www.banquedesterritoires.fr/velos-en-libre-service-un-bilan-coutsavantages-juge-globalement-equilibre>
- [S3] Commune de Beyne-Heusay (Belgique), tableau de bord : arrêt de bus PMR, quais, abribus (ordre de grandeur, prix belges) — <https://beyne-heusay.be/sites/default/files/documents/news/Tableau-de-bord%20.pdf>
- [S4] Transition Vélo, ordres de grandeur assurance et entretien d'une voiture (particulier) — <https://www.transitionvelo.com/?p=32352>
- [S5] Base Empreinte ADEME (voiture thermique 218 gCO2e/km, électrique 103 gCO2e/km), via Greenly — <https://greenly.earth/blog/secteurs/empreinte-carbone-comparatif-transports> ; à vérifier sur <https://base-empreinte.ademe.fr>
- [S6] ADEME Impact CO2, comparateur transport — <https://impactco2.fr/outils/transport>
- [S7] Citiz, *Livre blanc de l'autopartage 2026* — <https://www.citiz.coop/uploads/2026/02/2026-CITIZ-livre_blanc.pdf>

## Services et API utilisés

- geo.api.gouv.fr (API Découpage administratif, Etalab) : rattachement des stations aux communes et EPCI, contour provisoire de la zone — <https://geo.api.gouv.fr>
- transport.data.gouv.fr, API et métadonnées de validation des GTFS — <https://transport.data.gouv.fr/api/datasets>
