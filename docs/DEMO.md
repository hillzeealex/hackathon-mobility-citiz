# Démo en 3 minutes

> **Avant la démo**, relancer `python -m scripts.build_all --ville grenoble` et `python -m scripts.build_all --ville nantes` si les données ont été construites avant le 20/10.

Scénario clic par clic de l'application pour la soutenance, avec les phrases à dire. Tous les chiffres viennent
de l'encadré « Chiffres officiels pour les slides » de [`chiffres_cles.md`](chiffres_cles.md) (V2, marche réelle).
Version de secours : tag `demo-v1`.

## Avant de passer (10 min avant)

1. **Lancer** : double-clic sur `lancer_demo.bat` à la racine du dépôt. Le navigateur s'ouvre sur
   <http://localhost:8501> en 10 s environ. En ligne de commande, ça donne :

   ```bat
   .venv\Scripts\python -m streamlit run app\app.py
   ```

2. **Préchauffer** : ouvrir une fois la vue Nantes (onglets 1 à 5), puis revenir sur « France entière ».
   Ensuite, tout s'affiche en moins d'une seconde.
3. Navigateur en plein écran (F11), zoom 90 %, notifications coupées. Ouvrir aussi le dossier `slides\img\demo\`
   dans l'explorateur (plan B).
4. **Internet** : seul le fond de carte (CARTO / OpenStreetMap) en a besoin. Sans connexion, tout fonctionne et
   les cartes s'affichent sur fond blanc.

## Le scénario (≈ 3 min)

| Temps | Clic | Ce qu'on dit |
|---|---|---|
| 0:00 | **Vue** = « France entière » (écran d'accueil). | « Voici la France entière, carreau de 200 m par carreau de 200 m. **Un habitant sur quatre (25,9 %) n'a aucune option de mobilité à 5 minutes à pied** : ni bus, ni tram, ni vélo, ni voiture partagée. Et c'est une estimation optimiste, à vol d'oiseau. » |
| 0:25 | **Vue** = « Nantes Métropole ». Onglet **1 · Carte d'accès**. | « Nantes, notre ville : 689 000 habitants. On mesure ici la vraie marche, sur les rues et les chemins. **80,6 %** des habitants ont une option à 5 minutes, mais **seulement 19 % ont une voiture partagée** à 5 minutes. Les zones bleues ne sont pas des quartiers à problème : ce sont des **potentiels d'amélioration**. » |
| 0:55 | Barre latérale : **▶ Scénario démo (500 000 €)**, puis onglet **3 · Où investir ?**. | « Question de Citiz : avec 500 000 €, où ouvrir des stations ? L'optimiseur choisit **12 stations**. **35 000 habitants** de plus se retrouvent à 5 minutes à pied d'une voiture partagée : la couverture passe de **19,0 % à 24,1 %**, pour **13,6 € par habitant** sur 3 ans. » |
| 1:25 | Survoler une station (ex. n° 2, Vaucanson). | « Pour chaque station : le quartier, le coût, les habitants gagnés, et la distance à pied jusqu'à l'autopartage le plus proche. Ici 7 minutes : sur la carte, elle paraît proche d'une station existante, mais à pied, il faut faire le tour. » |
| 1:40 | Faire glisser **Budget** jusqu'à **1 000 000 €**. | « Si le budget double : 25 stations, 59 000 habitants gagnés, 27,6 % de couverture. Chaque euro supplémentaire rapporte un peu moins : on voit où s'arrêter. » |
| 2:00 | Descendre à la **Liste priorisée**. | « Ce que Citiz emporte : une liste priorisée, exportable en CSV, avec pour chaque emplacement le coût et la probabilité, selon notre modèle, qu'une station y fonctionne. » |
| 2:15 | Onglet **4 · Validation**. | « Peut-on faire confiance au modèle ? On lui a caché tout le réseau Citiz de Grenoble. Il retrouve **89 % des stations** dans les 20 % de carreaux qu'il juge les plus favorables, contre 82 % avec la densité seule. Et la marche réelle compte : à vol d'oiseau, on surestime l'offre de 80 %. » |
| 2:45 | Conclusion (rester sur Validation). | « Données 100 % ouvertes, recalculables en une commande, limites assumées : le modèle apprend où Citiz s'est déjà installé, et le surcoût lié au risque de vol est une hypothèse à valider avec Citiz. » |

Retour au point de départ à tout moment : bouton **▶ Scénario démo** (500 000 €, équité 0,5, ILP, comme dans
les slides).

## Si le jury demande…

| Question | Réponse courte | Où le montrer |
|---|---|---|
| « Pourquoi cette station si près d'une station existante ? » | La règle est 5 min **à pied réelles**. Vaucanson : 358 m à vol d'oiseau, mais 508 m à pied (≈ 7 min). | Infobulle (onglet 3) ; onglet 5, « Pourquoi une station… » |
| « Glouton ou ILP ? » | L'ILP trouve l'optimum exact du score ; le glouton fait aussi bien à 500 000 € (34 979 habitants dans les deux cas). | Onglet 3, choix « Méthode » |
| « Et l'équité ? » | Curseur « Poids de l'équité » : à Nantes, la sélection ne change pas (vérifié de 0 à 2), car les zones denses non couvertes sont aussi celles des ménages modestes ou sans voiture. | Onglet 3 ; `chiffres_cles.md`, section 6 |
| « Le modèle, c'est quoi ? » | LightGBM sur 313 000 carreaux, 106 intercommunalités ; AUC 0,922 sur les 15 réseaux, chaque réseau étant prédit sans l'avoir vu. | Onglet 4 (tableau par réseau, SHAP) |
| « Les formules ? » | Options accessibles, 2SFCA, score et contraintes de l'optimiseur, surcoût de risque. | Onglet 5 |

## Plan B : les captures

Si l'appli ne démarre pas, montrer dans l'ordre les images de `slides\img\demo\` (visionneuse Windows, flèche droite) :

| Étape du scénario | Capture |
|---|---|
| France entière | `01_france.png` |
| Nantes, carte d'accès | `02_nantes_carte_acces.png` |
| (offre et population desservie, si on a le temps) | `03_nantes_offre_desservie.png` |
| Scénario démo 500 000 € | `04_nantes_ou_investir_500k.png` |
| Budget 1 000 000 € | `05_nantes_ou_investir_1M.png` |
| Liste priorisée | `06_nantes_liste_priorisee.png` |
| Validation | `07_validation.png`, `08_validation_reseaux_shap.png` |
| Méthode et limites (questions) | `09_methode.png`, `10_methode_limites.png` |
| Grenoble, ville exemple | `11_grenoble_carte_acces.png` |

Pour régénérer les captures (appli fermée), lancer `python -m scripts.captures_demo`, en ajoutant `--hors-ligne`
pour vérifier le fonctionnement sans Internet.

## Si l'appli ne démarre pas

| Symptôme | Action |
|---|---|
| `lancer_demo.bat` affiche « Environnement Python absent » | Plan B (captures). Pour réinstaller : `python -m venv .venv` puis `.venv\Scripts\python -m pip install -r requirements.txt`. |
| Message rouge « Données … absentes » dans l'appli | Plan B. L'appli lit `data/processed/` (jamais versionné) : copier ce dossier depuis le PC qui a servi aux répétitions, ou tout reconstruire depuis les données brutes (`docs/RECUPERER_LES_DONNEES.md`, ≈ 30 min). La Release `donnees-v2` contient les exports partagés (CSV, GPKG, cartes HTML), pas les fichiers de l'appli. |
| Port 8501 occupé | Streamlit prend automatiquement le port suivant (8502) : lire l'adresse affichée dans la fenêtre noire. |
| Erreur Python après une modification de dernière minute | `git stash`, puis `git checkout demo-v1`. Les données de `data/processed/` restent compatibles. |
| Pas d'Internet | Rien à faire : seul le fond de carte disparaît. |
| Calcul lent sur un budget inhabituel | Rester sur 250 000, 500 000 ou 1 000 000 € (instantanés), ou choisir « Glouton (rapide) ». |
