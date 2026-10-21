# Notebooks Microsoft Fabric

Espace Fabric « Hackathon Citz », runtime **Python** (pas Spark), lakehouses `bronze`, `silver`, `gold`.
Pour importer : Espace de travail → Importer → Notebook, puis exécuter dans l'ordre ci-dessous.

| Ordre | Notebook | Lit | Écrit | Rôle |
|---|---|---|---|---|
| 1 | `bronze_notebook` | sources ouvertes | `bronze` | GTFS, GBFS, Filosofi 200 m, communes, INSEE (population, logement, flux), SSMSI, Omphale (environ 1 h) |
| 2 | `silver_notebook` | `bronze` | `silver` | normalisation, rattachement aux communes, contrôles |
| 3 | `acces_notebook` | `silver`, `bronze` | `gold` | objectifs 1 et 2 : options à 5 min par carreau, population desservie par arrêt et station |
| 4 | `modele_notebook` | `gold`, `silver` | `gold` | modèle LightGBM « où Citiz s'installerait », validation par région et à l'aveugle sur Grenoble |
| 5 | `optimisation_notebook` | `gold`, `silver` | `gold` | objectif 3 : liste priorisée sous budget à Nantes Métropole, projection de population, saisie de la rentabilité |
| 6 | `gold_notebook` | `silver` | `gold` | indicateurs par commune et score à 8 critères (présélection) |

Chaque notebook relit le dernier run complet de l'étape précédente (`pipeline_run`, colonne `_run_id`) :
après une modification, on relance à partir du premier notebook modifié. **Ne pas relancer une partie seulement
de `bronze_notebook`** : les tables réécrites prendraient un nouvel identifiant de run et Silver les ignorerait.
Pour ajouter une source à un Bronze existant, utiliser `REPRENDRE_RUN = True` (cellule Omphale).

Le rapport Power BI `citiz_acces_investissement` lit les tables de `gold` en Direct Lake.

## Rapport Power BI

`powerbi/citiz_acces_investissement/` : modèle sémantique (TMDL, Direct Lake sur `gold`) et rapport (PBIR), 8 pages :
France (accès à 5 min), Nantes diagnostic, Nantes desserte, Nantes potentiel prédit, Nantes où investir (budget,
équipements, scénario, méthode, équité, horizon de population), rentabilité d'une station (saisie libre, non
enregistrée), méthode, limites (modèle, données, hypothèses). L'expression `DirectLake - Gold` pointe vers l'identifiant du lakehouse `gold`
de l'espace « Hackathon Citz » : à adapter dans `semantic_model/definition/expressions.tmdl` pour un autre espace.
