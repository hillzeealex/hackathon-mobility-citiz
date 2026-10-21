# Décisions du projet

Journal des décisions de l'équipe. La plus récente prime en cas de contradiction.
Comparatif chiffré des villes : [`choix_ville.md`](choix_ville.md). Chiffres de la soutenance :
[`chiffres_officiels.md`](chiffres_officiels.md).

## 21/10/2026 : Fabric devient la source officielle

| Sujet | Décision |
|---|---|
| **Source des chiffres** | Les chiffres de la soutenance sortent de **Microsoft Fabric** (`citiz_pipeline`) : [`chiffres_officiels.md`](chiffres_officiels.md). [`chiffres_cles.md`](chiffres_cles.md) reste la référence du pipeline local. |
| **Marche réelle** | Nantes Métropole est calculée en **V2 dans Fabric** (réseau piéton OpenStreetMap Pays de la Loire, zone + 800 m) ; la France reste en V1 (borne haute). Grenoble en V2 est cité depuis le pipeline local, comme validation de la méthode. |
| **Délinquance** | **Retirée** : ni variable du modèle, ni surcoût d'une station. On ne pénalise pas un territoire sur ses statistiques de vols. |
| **Modèle** | Pour Nantes, probabilité prédite par un modèle qui n'a **pas vu sa région** (équivalent de `proba_oof` en local). Niveau de vie ajouté aux variables ; tranches d'âge testées, non retenues. |
| **Équité** | Moyenne des rangs des ménages pauvres et sans voiture ; scénarios 0 et 0,5 (0,5 par défaut, comme en local). |
| **Rentabilité** | Page de simulation dans Power BI : 8 valeurs saisies par les collaborateurs, non enregistrées ; recette, coût variable et réservations à fournir par Citiz. |
| **Fabric** | Remplace la ligne « Fabric : paragraphe de justification seulement » du 20/10 : la chaîne complète tourne dans Fabric (bronze → silver → gold, pipeline, Power BI en Direct Lake). |

## 20/10/2026 : stratégie finale

| Sujet | Décision |
|---|---|
| **Grenoble** | **Ville exemple** : vitrine méthodologique (accessibilité V1 vol d'oiseau vs V2 marche réelle) et **test à l'aveugle** du modèle (Citiz y est dense : 168 stations). Pas de recommandation d'implantation. |
| **Nantes** | **Notre ville** : toutes les recommandations (diagnostic, candidats, optimisation, liste priorisée) se font sur Nantes Métropole. Citiz y est présent mais peu dense (cas de **densification**). |
| **Nice** | **Contre-exemple**, documentation seulement (aucun calcul dédié). |
| **Historique Citiz** | **Abandonné comme cible** du modèle : 34 photos, trou de 16,5 h, 12 changements de disponibilité. Limite documentée. |
| **Cible du modèle** | Pour chaque carreau peuplé de métropole : présence d'une station Citiz à 400 m (classification LightGBM). Le modèle apprend **où Citiz s'est installé**, pas la demande pure. |
| **Validation** | Spatiale, par réseau régional Citiz ; test à l'aveugle Grenoble ; comparaison à une baseline « densité seule » ; importance des variables (SHAP). |
| **Optimisation** | Candidats à Nantes : centroïdes des carreaux peuplés et arrêts de TC, hors zones déjà couvertes par Citiz (et Marguerite si disponible). Score = population nouvellement couverte × probabilité du modèle, avec poids d'équité et surcoût de risque de vol. Glouton et ILP. |
| **Appli** | Zoom sur données **réelles** uniquement (Nantes ; Grenoble pour la carte et la validation). Données factices retirées de la démo. Onglet « Validation ». |
| **Fabric** | Paragraphe de justification seulement (ci-dessous). |
| **Ordre de travail** | 1 correctifs (multi-ville, GTFS, jour type figé, commande unique) · 2 Nantes · 3 modèle · 4 optimisation · 5 appli · 6 chiffres clés. Un commit et un point court par étape. |

### Pourquoi Microsoft Fabric n'est pas au cœur du pipeline (décision du 20/10, remplacée le 21/10)

Le pipeline tourne en local en moins de 10 minutes sur un PC portable (8 Go de RAM, pic mesuré 1,5 Go pour toute la
France) avec des fichiers GeoParquet : le volume (≈ 7 Go bruts, 2,3 M carreaux) ne justifie pas un cluster Spark, et
les traitements clés (réseau piéton, Dijkstra, ILP HiGHS, LightGBM) reposent sur des bibliothèques Python
géospatiales qui ne bénéficient pas de la distribution. Le notebook `fabric/01_ingestion.ipynb` de l'équipe montre
que l'ingestion est **portable** vers un Lakehouse (tables Delta des arrêts, GBFS, Filosofi, communes) : c'est la voie
naturelle pour **industrialiser** chez Citiz (collecte GBFS planifiée, historique long, tableaux de bord Power BI),
une fois la méthode validée ici. Nos sorties étant des fichiers Parquet, elles se chargent telles quelles dans un
Lakehouse.

## 19/10/2026 : décisions antérieures toujours valables

- **Population** : `pop_calee` (Filosofi recalé sur le recensement 2023) pour toutes les couvertures ; `ind` conservé.
- **Offre** : chargée sur la zone + 800 m ; candidats et affichage limités à la zone. Free-floating : 1 option par
  zone et par mode, pondérée 0,5.
- **Indicateurs** : principal = options pondérées par carreau, rapportées à l'habitant à l'IRIS ; secondaire =
  2SFCA (Citiz), couche optionnelle, variable du modèle et critère de l'optimiseur.
- **Secret statistique** : aucun carreau de moins de 11 ménages affiché ; agrégation à l'IRIS ; effectifs des exports
  partagés arrondis à 5 ; taux de vols par commune publiés seulement à partir de 10 000 habitants.
- **Motorisation** : par IRIS, repli sur la commune.
- **Sources de coûts et de CO2** : ADEME et sources publiques citées dans `config/costs.yaml` ; **aucun chiffre du
  livre blanc Citiz 2026** (non vérifié).
- **Réseau piéton** : depuis l'extrait Geofabrik local, découpé sur la zone + 800 m (pas d'API Overpass).
- **Données** : jamais de données brutes dans Git ; données nettoyées partagées par la Release `donnees-v1`.
- **France entière** : accessibilité V1 (borne haute) pour tous les carreaux ; biais mesuré sur les zooms.
