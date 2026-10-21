# Slides

Deck de soutenance : [`citiz_soutenance.pptx`](citiz_soutenance.pptx), aux couleurs de Citiz (turquoise `#32B4B5`,
texte `#202020`, rouge `#E63329` pour les alertes), logos Citiz × Epitech × Microsoft. Le texte à dire et le
déroulé de la démo sont dans les **notes de l'orateur**.

Partie stratégique (premier orateur) : [`citiz_strategie.pptx`](citiz_strategie.pptx), 5 slides, environ 3 min :
couverture, l'ambition (70 000 véhicules en 2031, Philippe Tabarot, 4 décembre 2025), le constat Autolib' (2011-2018),
notre réponse (3 principes et qualification GO / NO GO à Nantes Métropole), transition vers la démonstration technique.
Le texte de chaque partie et ses sources sont dans les notes de l'orateur.

Format imposé : 15 minutes par groupe, dont **5 minutes de présentation + démo**, le reste en questions.
Discours : problème, solution, démonstration, résultats.

| Moment | Contenu | Temps |
|---|---|---|
| Slide 1 · Contexte | Nantes Métropole : 689 000 habitants, 23 stations Citiz, 11 fois moins qu'à Grenoble : un réseau à densifier | 0:20 |
| Slide 2 · Problème | 19,0 % seulement à 5 min à pied d'une voiture partagée ; le besoin de Citiz : où ouvrir, à budget donné ? | 0:30 |
| Slide 3 · Solution | Mesurer → prédire → optimiser → décider, toute la chaîne dans Microsoft Fabric | 0:40 |
| **Démo** | Rapport Power BI `citiz_acces_investissement` : Nantes diagnostic, où investir (500 k€ puis 1 M€), rentabilité | 2:45 |
| Slide 4 · Recommandation | 500 000 € : 12 stations, +34 979 habitants, 19,0 → 24,1 %, 13,6 € par habitant ; hypothèse de coût | 0:45 |
| Annexes | Pour les questions : modèle (validation Grenoble), pipeline Fabric, Fabric = local + Power BI, limites, France | — |

Plan B de la démo : application Streamlit (`lancer_demo.bat`) ou captures de `img/demo/`. Montrer un **run passé
réussi** du pipeline, pas un lancement en direct : la capacité Fabric peut être saturée.

Tous les chiffres viennent de l'encadré « Chiffres officiels pour les slides » de
[`docs/chiffres_cles.md`](../docs/chiffres_cles.md) (V2, marche réelle), sauf la France entière (V1, borne haute) et
la concordance Fabric / local (80,7 % contre 80,6 %, 19,0 % contre 19,0 %). Cartes : `img/`.
