# Questions du Jury & Éléments de Réponse

Ce document prépare l'équipe aux questions techniques, méthodologiques et stratégiques susceptibles d'être posées lors de la soutenance devant le jury.

---

### Q1. Pourquoi et comment intégrer un scénario « Pros / Flottes professionnelles » pour Citiz ? Ne risque-t-on pas de cannibaliser l'usage des particuliers ?

**Réponse de l'équipe :**
- **Complémentarité temporelle idéale** : Les particuliers utilisent principalement l'autopartage en soirée, le week-end et lors des congés. À l'inverse, les besoins des flottes d'entreprises (déplacements professionnels, missions de service, rendez-vous inter-sites) se concentrent du lundi au vendredi entre 9h et 17h. Développer l'usage professionnel permet donc d'augmenter significativement le taux de rotation des véhicules sur leurs heures creuses, sans dégrader la disponibilité pour les résidents.
- **Pondération $\alpha = 0,3$ dans l'optimiseur** : Un emploi génère en moyenne moins de rotations complètes en autopartage qu'un ménage résidentiel complet. Nous avons donc retenu une pondération de $\alpha = 0,3$ dans `config/settings.yaml` (« hypothèse à valider avec Citiz ») pour valoriser la proximité des pôles tertiaires sans sacrifier le socle résidentiel.
- **Résultat clé (« double dividende »)** : À 500 k€ d'investissement, le scénario mixte ($\alpha = 0,3$) retient **exactement les mêmes 12 stations** que le scénario particuliers, tout en couvrant immédiatement **18 766 emplois** en plus des **117 426 habitants**. Le réseau est donc naturellement vertueux pour les deux publics.
- **Cas extrême 100 % B2B (Pros)** : Si Citiz décide de créer des stations exclusivement dédiées aux parcs d'activités et zones industrielles (flottes fermées ou réservées), l'optimiseur réoriente 5 stations sur 12 vers la périphérie économique (Atlantis, Haluchère, Campus Tertre), augmentant les emplois desservis à **29 406** (+56,7 %).

---

### Q2. Quelle est la limite méthodologique de ce scénario professionnel ?

**Réponse de l'équipe :**
- **Modèle entraîné sur l'historique résidentiel** : Notre modèle LightGBM d'estimation de l'usage relatif a été entraîné sur le réseau historique de Citiz, dont la quasi-totalité des stations actuelles sont implantées au cœur des quartiers résidentiels denses ou près des gares centrales.
- **Comportement professionnel non modélisé** : Les entreprises obéissent à des contraintes contractuelles spécifiques (abonnements flotte, facturation centralisée, réservations régulières). Le modèle n'est donc pas formellement calibré pour prédire l'élasticité de la demande B2B.
- **Positionnement assumé** : C'est pour cette raison exacte que nous présentons ce volet comme un **scénario exploratoire à part**, tout en garantissant que les chiffres officiels du scénario Particuliers restent strictement inchangés.

---

### Q3. Comment avez-vous traité les données d'entreprises et le secret statistique ?

**Réponse de l'équipe :**
- **Sources ouvertes et officielles** : Nous avons croisé la base SIRENE géolocalisée de l'INSEE (2024, 130 000 établissements actifs sur Nantes Métropole) avec le cadastre des Zones d'Activité Économique de Nantes Métropole Open Data.
- **Étalonnage rigoureux** : L'estimation des effectifs par le milieu des tranches INSEE a donné 350 060 emplois rattachés sur notre carroyage, soit un écart de seulement **-1,94 %** par rapport au recensement officiel INSEE (357 000 emplois au lieu de travail).
- **Protection des données & Éthique** : Conformément à la réglementation et au secret statistique, **aucun nom d'entreprise n'apparaît dans l'application**. Les données sont strictement agrégées au carreau de 200 m et par pôle d'activité économique.

---

### Q4. Pourquoi le coût par station est-il d'environ 41 500 € et non 7 500 € ?

**Réponse de l'équipe :**
- **Coût complet (TCO sur 3 ans) vs aménagement de surface** : 7 500 € correspond uniquement à l'aménagement physique initial de la voirie (marquage, panneau, borne, arceau).
- **Modèle complet issu de `config/costs.yaml`** : Pour une recommandation financière réaliste auprès de la direction de Citiz et de Nantes Métropole, nous intégrons :
  1. L'investissement initial : véhicule Citiz (22 000 €) + aménagement voirie (1 500 €) = 23 500 €.
  2. L'exploitation sur 3 ans : assurance, entretien, nettoyage, télématique et redevance de stationnement = 14 400 € à 18 000 €.
  3. Total TCO 3 ans : **≈ 37 900 € à 41 500 € par station**.
- Ainsi, avec une enveloppe de **500 000 €**, Citiz et la Métropole financent l'ouverture et l'exploitation pérenne de **12 stations complètes**.
