# Ce qu'un embedding capture — et ce qu'il ne capture pas

Note de référence pour le projet `wiki-embeddings`. Objectif : poser ce que les vecteurs
permettent réellement, afin de ne pas leur faire porter des questions auxquelles ils ne
répondent pas.

## Ce que fait l'encodeur

Un modèle d'embeddings transforme un texte de longueur quelconque en une liste de nombres de
longueur fixe (1536 pour `text-embedding-3-small`). Deux textes de sens proche produisent des
vecteurs proches, ce qui permet de mesurer une similarité par un calcul géométrique plutôt que
par comparaison de mots.

**Ce que « proche » signifie dépend entièrement de l'entraînement.** Ces modèles sont entraînés
par apprentissage contrastif : on leur présente des paires de textes réputées liées — une
question et sa réponse, un titre et son paragraphe, une phrase et sa traduction — et on les
entraîne à rapprocher ces vecteurs, tout en éloignant des paires tirées au hasard.

Le modèle n'apprend donc ni la vérité, ni la logique, ni les quantités. Il apprend **ce qui a
tendance à se paraphraser ou à cohabiter**. La proximité qu'il encode est thématique.

La mesure utilisée est le **cosinus** : l'angle entre deux vecteurs. Un score de cosinus n'est
ni une probabilité, ni une valeur absolue — deux textes français sans rapport ne donnent pas
zéro, parce que partager une langue et un registre est déjà une forme de proximité. Aucun seuil
n'est donc transposable : il doit être calibré sur le corpus et le modèle utilisés.

## Ce qui s'encode bien

| Cas | Exemple |
|---|---|
| Thème et vocabulaire de domaine | « couverts végétaux » ≈ « engrais verts » |
| Paraphrase | « détruire le couvert au rouleau » ≈ « destruction mécanique du couvert » |
| Traduction | « couverts végétaux » ≈ « cover crops » |
| Registre et genre | une fiche technique ≈ une autre fiche technique |

La traduction est un objectif d'entraînement, pas un effet secondaire. Sur un wiki multilingue,
cela impose d'exclure explicitement les paires de traductions de la détection de doublons : le
modèle les signalera comme identiques, et il aura raison.

## Ce qui ne s'encode pas

**Les nombres et les grandeurs.** Rien dans l'entraînement n'incite à représenter une magnitude.
« 0,8 hectare » et « 80 hectares » produisent des vecteurs quasi identiques. Idem pour les dates,
les prix, les doses.

**La négation et les antonymes.** « L'exploitation utilise le désherbage chimique » et
« L'exploitation n'utilise pas de désherbage chimique » partagent presque tous leurs mots et le
même thème : leurs vecteurs sont très proches malgré un sens opposé. C'est une limite en partie
structurelle — un modèle d'embeddings encode chaque texte séparément, sans jamais voir l'autre,
et l'inversion doit survivre à cette compression sans que l'entraînement l'ait récompensée.

**Les identifiants, références et noms propres.** « AMM 2110024 » et « AMM 2110025 » désignent
deux produits différents avec des vecteurs presque confondus. Même chose pour les noms
commerciaux et les variétés.

**Les textes trop longs ou trop courts.** Au-delà de la limite du modèle, le texte est tronqué
silencieusement. En deçà d'une poignée de mots, le vecteur manque de contexte et devient proche
de trop de choses.

**Le texte répétitif.** Des chunks partageant un en-tête ou des libellés identiques se
ressemblent artificiellement, indépendamment de leur contenu réel.

## Pourquoi ce n'est pas un problème pour ce projet

**Les usages visés sont de l'exploration et de la génération de candidats, pas de l'affirmation.**
Le pipeline produit des paires soumises à une revue humaine, et à terme des suggestions de
lecture. Il ne répond pas à des questions et ne prend aucune décision seul. Une erreur de
polarité coûte du temps de relecture, pas une donnée fausse en base.

**L'insensibilité à la polarité est même alignée avec la raison d'être de la plateforme.** Triple
Performance sert à aider un agriculteur à se projeter dans un changement, en lui donnant accès à
des expériences réelles et contextualisées. Un retour d'expérience de quelqu'un qui a essayé une
pratique et l'a abandonnée est au moins aussi utile qu'un témoignage favorable. Rapprocher des
contenus qui traitent du même sujet, quelles que soient leurs conclusions, est donc le bon
comportement.

**Les grandeurs et les catégories sont traitées ailleurs, et mieux.** Ce n'est pas un défaut à
contourner mais une répartition des rôles : le vecteur porte le sujet, le payload porte les
filtres exacts (production, certification, surface), et une recherche lexicale traite les
références et identifiants. Chaque outil fait ce qu'il sait faire.

**La limite deviendrait réelle si l'usage changeait.** Le jour où la plateforme répondrait à des
questions précises plutôt que de faire découvrir des contenus, renvoyer un passage qui affirme
l'inverse comme s'il répondait deviendrait nuisible. La ligne de partage est entre *faire
découvrir* et *affirmer*.

## Les règles qui en découlent

- Les valeurs numériques et catégorielles vont dans le payload comme filtres, jamais dans le
  texte vectorisé.
- Les références et identifiants relèvent d'une recherche lexicale, pas d'une recherche
  vectorielle.
- Les paires de traductions sont exclues des comparaisons de doublons.
- Le découpage se fait par section : assez long pour porter du contexte, assez court pour rester
  précis.
- Les seuils sont calibrés empiriquement sur un jeu annoté, séparément par type d'unité, et ne
  sont pas transposables d'un modèle à l'autre.
- Les cas d'échec sont documentés, pas seulement le score global. Si une part notable des faux
  positifs vient d'inversions de polarité, on le saura.

## Une piste ouverte par ces limites

Le pipeline produit aujourd'hui deux issues : doublon ou non-doublon. Les limites décrites
ci-dessus en suggèrent une troisième — **divergence** : deux pages très proches sémantiquement
mais dont les conclusions s'opposent.

Sur un wiki où presque tout dépend du contexte pédoclimatique, deux retours d'expérience
contradictoires sur une même pratique ne constituent pas un défaut de contenu, mais l'une des
informations les plus utiles de la plateforme. Les repérer serait un livrable à part entière, et
peu coûteux : ce sont les mêmes candidats, avec une étiquette supplémentaire.
