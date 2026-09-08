# Calibration des paramètres

Note de référence pour le projet `wiki-embeddings`.

## Pourquoi une étape de calibration

Un score de similarité cosinus n'a pas de signification absolue. Deux textes sans rapport ne
donnent pas zéro, et la valeur au-delà de laquelle deux sections « se ressemblent vraiment »
dépend du modèle, du corpus, de la langue et de la taille des unités comparées.

Aucun seuil n'est donc transposable depuis un autre projet, ni d'un modèle à l'autre. Il doit
être établi par l'observation. C'est l'objet de la calibration : transformer des paramètres
choisis au jugé en paramètres justifiés par des mesures.

## Les paramètres à fixer

| Paramètre | Ce qu'il fait | Trop bas | Trop haut |
|---|---|---|---|
| Seuil de recherche (section) | score minimal pour qu'une paire de sections soit retenue | flot de bruit, agrégation polluée | des doublons réels perdus avant l'agrégation |
| Limite de voisins (`limit`) | nombre maximal de voisins ramenés par unité | des paires manquées sur les sections très denses | volume inutile |
| `hnsw_ef` (recherche) | largeur d'exploration de l'index | recherche rapide mais incomplète | recherche lente sans gain |
| Règle d'agrégation | comment passer d'un score entre sections à un score entre pages | — | — |
| Seuil de candidat (page) | score à partir duquel une paire est soumise à revue | trop de paires à relire | des doublons jamais vus |
| Taille des unités | découpage des sections longues, fusion des courtes | vecteurs instables, peu de contexte | vecteurs dilués, peu précis |

Les deux seuils sont distincts et ne se calibrent pas ensemble. Celui de la recherche s'applique
aux sections et doit rester permissif, pour ne pas perdre de signal avant l'agrégation. Celui des
candidats s'applique aux pages et détermine ce qu'un humain voit.

## Le jeu annoté

C'est l'instrument de mesure. Sans lui, on ne calibre pas, on devine.

Il contient des paires de pages avec un verdict humain : doublon, non-doublon, ou divergence
(même sujet, conclusions opposées).

**Comment le construire, et le piège à éviter.** Le réflexe naturel est de prendre les paires les
mieux notées par le modèle et de les annoter. C'est insuffisant, et biaisé : on ne peut alors
mesurer que la précision — la proportion de vrais doublons parmi ceux qu'on propose. Le rappel,
lui, reste inconnu, puisqu'on n'a par construction aucune paire que le modèle a ratée.

Le jeu doit donc contenir trois origines :

- **des paires échantillonnées sur toute l'échelle de score**, pas seulement en haut, afin
  d'observer où se situe la frontière ;
- **des paires trouvées par d'autres moyens** — similarité de titres via `pg_trgm`, pages d'une
  même catégorie, connaissance de l'équipe éditoriale. Ce sont elles qui révèlent ce que les
  vecteurs manquent ;
- **des paires manifestement sans rapport**, pour vérifier que le bas de l'échelle se comporte
  comme attendu.

Quelques centaines de paires suffisent pour placer un seuil. Ce n'est pas un problème de volume,
c'est un problème de représentativité.

## Comment chaque paramètre se choisit

**Le seuil de recherche.** Regarder la distribution des scores des paires de sections issues des
doublons connus du jeu annoté. Placer le seuil en dessous de leur valeur la plus basse : à ce
stade on ne cherche pas à décider, seulement à ne rien perdre.

**Le seuil de candidat.** Faire varier le seuil et calculer, pour chaque valeur, la précision (la
proportion de vrais doublons parmi les paires proposées) et le rappel (la proportion de vrais
doublons effectivement retrouvés). Ces deux quantités s'opposent : remonter le seuil améliore la
précision et dégrade le rappel.

Le choix ne se fait pas seulement sur la courbe, mais sur la **capacité de relecture**. Si
l'équipe peut examiner une cinquantaine de paires par semaine, le bon seuil est celui qui produit
ce volume avec la meilleure précision possible. Un seuil qui génère trois cents paires par
semaine est inutilisable, quelle que soit la qualité de la courbe.

**La règle d'agrégation.** Comparer les règles candidates — maximum des similarités entre
sections, comptage des paires au-dessus d'un seuil, moyenne des meilleures correspondances — sur
le même jeu annoté, et retenir celle qui donne la meilleure séparation. C'est une mesure, pas une
préférence.

**La limite de voisins.** L'observation la fixe : relever le nombre maximal de voisins réellement
au-dessus du seuil, et placer la limite au-dessus. Si une unité atteint la limite, c'est un signal
en soi — probablement du texte répétitif à examiner, pas un cas de doublon.

**`hnsw_ef`.** Mesurer le rappel de la recherche approximative contre une recherche exacte, sur un
échantillon. C'est l'un des rares usages où `pgvector` est utile : une recherche exhaustive en SQL
fournit la vérité terrain permettant de savoir ce que l'index approximatif laisse passer.

**La taille des unités.** Comparer deux configurations de découpage sur le même jeu annoté. C'est
le paramètre le plus coûteux à faire varier, puisqu'il impose de tout réembedder — d'où l'intérêt
de conserver le wikitext brut en base, qui permet de re-découper sans re-télécharger.

## Quand refaire la calibration

- **Changement de modèle d'embeddings** : tous les seuils deviennent caducs. Les scores de deux
  modèles ne sont pas comparables, même à dimension égale.
- **Changement de stratégie de découpage** : les unités comparées ne sont plus les mêmes.
- **Évolution significative du corpus** : arrivée massive de contenus d'un nouveau type, ou d'une
  nouvelle langue.
- **Jamais par transposition** : un seuil calibré sur un type d'unité ou une langue ne vaut pas
  pour un autre.

## Ce qu'on consigne

Un paramètre sans sa provenance devient un nombre magique que plus personne n'ose toucher. Pour
chaque calibration, on garde :

- **le jeu annoté**, versionné dans le dépôt sous forme de fichier — c'est un actif du projet,
  relisible et amendable comme du code, pas une donnée d'exécution ;
- **les valeurs retenues**, avec la date, le modèle et la version de découpage auxquels elles se
  rapportent ;
- **les mesures obtenues** au point choisi : précision, rappel, volume de paires produites ;
- **les cas d'échec observés**, classés par nature (inversion de polarité, ferraille répétée,
  pages trop courtes). C'est cette liste, plus que le score global, qui indique quoi améliorer
  ensuite.
