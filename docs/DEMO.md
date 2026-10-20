# Démo en 3 minutes

Scénario clic par clic de l'application Streamlit pour la soutenance. Chiffres tirés de
[`chiffres_cles.md`](chiffres_cles.md) (version de démo : tag `demo-v1` puis branche `data-pipeline`).

## Avant de passer (5 min avant)

```bash
cd hackathon-mobility-citiz
.venv\Scripts\activate                      # Linux / Mac : source .venv/bin/activate
streamlit run app/app.py                    # ouvre http://localhost:8501
```

- Laisser l'appli **ouverte sur la vue France** (premier chargement ≈ 5 s, ensuite instantané).
- Ouvrir une fois la vue Nantes puis revenir sur France : les données sont alors en cache.
- Navigateur en plein écran, zoom 90 %. Couper les notifications.

## Le scénario (≈ 3 min)

| Temps | Clic | Ce qu'on dit |
|---|---|---|
| 0:00 | Barre latérale **Vue** = « France entière ». Carte par **Départements**, indicateur « Part de la population sans aucune option à 5 min ». | « Un Français sur quatre (25,9 %) n'a aucune option de mobilité à 5 minutes à pied, même à vol d'oiseau. Bleu = peu d'habitants sans option, rouge = beaucoup. » |
| 0:25 | **Échelle** = « EPCI », puis descendre au tableau « Classement des EPCI… potentiel Citiz ». | « On a classé 276 intercommunalités selon la densité, la part de ménages sans voiture et l'autopartage existant. Nice est 1ʳᵉ mais c'est notre contre-exemple : l'autopartage y est invisible en open data. » |
| 0:50 | **Vue** = « Nantes Métropole (recommandations) ». Onglet **1 · Carte d'accès**, échelle IRIS. | « Nantes, notre ville : 689 000 habitants. En marche réelle, 80,6 % ont une option à 5 min, et seulement 19 % un autopartage (23 Citiz, 61 Marguerite). » |
| 1:10 | Onglet **2 · Offre et population desservie** : survoler un arrêt, montrer le tableau « Points dont dépendent le plus d'habitants ». | « Pour chaque arrêt et station : combien d'habitants à 5 min, et combien n'ont aucune autre option. » |
| 1:30 | Onglet **3 · Où investir ?** : budget 500 000 €, équité 0,5, méthode « Glouton ». | « Avec 500 000 €, 12 stations Citiz : +35 000 habitants à 5 min d'un autopartage, 14 € par habitant sur 3 ans, 17 tonnes de CO₂ évitées par an, estimation prudente. » |
| 1:50 | Faire glisser **Budget** à 1 000 000 €, puis **Méthode** = « ILP optimal » (≈ 5 s). | « Le curseur recalcule en direct : 25 stations, +59 000 habitants. L'ILP prouve l'optimalité ; ici le glouton fait presque aussi bien. » |
| 2:10 | Descendre à la **Liste priorisée**, montrer la colonne « probabilité modèle », cliquer **Exporter en CSV**. | « Une liste priorisée exportable : quartier, coût, habitants gagnés, probabilité que Citiz s'y installe selon le modèle. » |
| 2:25 | Onglet **4 · Validation**. | « Le modèle n'a jamais vu le réseau Citiz de Grenoble : il y retrouve 89 % des stations dans les 20 % de carreaux qu'il juge les plus favorables (82 % avec la densité seule). Et la marche réelle compte : à vol d'oiseau, on surestime l'offre de 80 %. » |
| 2:50 | Conclusion (rester sur Validation). | « Données ouvertes, méthode reproductible en une commande, limites assumées : le modèle apprend où Citiz s'est installé, pas la demande pure ; le surcoût de risque est une hypothèse à valider avec Citiz. » |

## Si l'appli ne démarre pas

| Symptôme | Action |
|---|---|
| `streamlit` introuvable | Activer le venv : `.venv\Scripts\activate`, puis `python -m streamlit run app/app.py`. |
| Port occupé | `streamlit run app/app.py --server.port 8502`. |
| Message « Données de nantes absentes » ou « Fichiers nationaux absents » | Données non construites sur ce PC : `python -m src.national.build_all`, `python -m src.model.features`, `python -m src.model.train`, puis `python -m scripts.build_all --ville nantes` et `--ville grenoble` (≈ 12 min au total ; voir `README.md`). |
| Erreur Python après une modification de dernière minute | Revenir à la version de secours : `git stash` puis `git checkout demo-v1` (les données de `data/processed/` restent compatibles). |
| Rien ne marche (PC de secours sans données) | Montrer les images de `slides/img/` (cartes France, Grenoble V1/V2, Nantes recommandations, SHAP) et la carte interactive `data/share/france/carte_france_departements.html` (double-clic, fonctionne sans Python). |
| ILP trop lent en direct | Rester en méthode « Glouton » : même résultat à 0,8 % près sur 1 M€. |
