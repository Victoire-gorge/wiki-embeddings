# CLAUDE.md

Guidance pour Claude Code sur ce dépôt.

## Ce qu'est ce projet

`wiki-embeddings` est un service d'indexation sémantique du wiki **Triple Performance**
(MediaWiki + Semantic MediaWiki, plusieurs milliers de pages, multilingue, ~70 000 visiteurs
par mois), développé par Neayi.

- **Objectif v1** : détecter les pages en doublon et les manques de contenu.
- **Objectif à moyen terme** : réutiliser le même index pour recommander des articles à des
  visiteurs anonymes — c'est le besoin prioritaire de l'équipe.

Le service tourne dans son propre conteneur et sera intégré à la stack Docker de Neayi
(`neayi/tripleperformance`), orchestré par n8n.

## Contexte pédagogique — à respecter strictement

Ce projet est mené par une data scientist junior dont l'objectif explicite est **d'apprendre** :
Qdrant, les bases vectorielles, les embeddings, et les bonnes pratiques d'un pipeline de données
propre. La vitesse de livraison n'est pas le critère.

- **Explique tes choix techniques avant de les implémenter.** Un choix non justifié est un choix
  à re-discuter.
- **Propose des alternatives** avec leurs compromis, plutôt qu'une solution unique présentée
  comme évidente.
- **Ne génère pas de gros blocs de code d'un coup.** Procède par incréments testables et
  arrête-toi pour valider la compréhension.
- Sur les concepts liés aux embeddings et à Qdrant, **explique le concept avant d'écrire le
  code**.
- **Signale les mauvais réflexes courants** quand tu en vois un, même s'il est demandé.
- Si une décision engage l'architecture, **pose la question** plutôt que de trancher seul.

## Discipline de code

- **Pas d'abstraction ni de configurabilité non demandées.** Le code minimal qui résout le
  problème posé, rien de spéculatif — sur un projet d'apprentissage, du code sur-ingénierié
  enseigne de mauvais réflexes.
- **Diffs chirurgicaux.** Ne pas reformater ou "améliorer" du code adjacent non concerné par la
  demande. Repérer la dead code existante plutôt que la supprimer sans le signaler.
- **Critère de vérification avant de considérer une étape terminée.** Pour les transformations
  pures du pipeline (étapes 1, 3, 6), écrire le test qui la caractérise avant de l'implémenter.

## Vocabulaire

Un seul terme par concept. Ne pas introduire de synonymes.

| Terme | Sens |
|---|---|
| **page** | une page du wiki |
| **unité** (`unit`) | un fragment de page vectorisé — une section aujourd'hui |
| **point** | l'objet stocké dans Qdrant (identifiant, vecteur, payload) |
| **run** | une exécution du pipeline |
| **candidat** | une paire de pages soumise à revue humaine |

Une unité correspond à une ligne de `units` et à un point Qdrant, les deux partageant le même
`unit_id`. **Ne jamais écrire « chunk ».**

## Modèle de données

### PostgreSQL — source de vérité

**`pages`** — une ligne par page du wiki, en upsert.

| colonne | type | note |
|---|---|---|
| `page_id` | bigint PK | identifiant MediaWiki, stable à vie |
| `title` | text | |
| `url` | text | |
| `lang` | text | colonne réelle : vient du wiki interrogé, pas des propriétés |
| `namespace` | int | ne garder que le contenu |
| `is_redirect` | boolean | les redirections ne sont pas indexées |
| `revision_id` | bigint | marqueur de version, change à chaque édition |
| `wikitext` | text | source brute, permet de re-découper sans re-télécharger |
| `properties` | jsonb | propriétés SMW, structure variable selon le type de page |
| `langlinks` | jsonb | conservé pour un usage ultérieur |
| `categories` | jsonb | |
| `last_seen_at` | timestamptz | |

Les propriétés servant de filtre sont exposées en **colonnes générées** depuis `properties`
(`GENERATED ALWAYS AS (properties->>'…') STORED`), indexées. Le `jsonb` reste la source unique,
les colonnes en sont dérivées — elles ne peuvent pas diverger. Pour les propriétés
**multivaluées** (`production` par exemple), pas de colonne générée : filtrage par containment
sur un index GIN.

**Règle de promotion** : une propriété devient une colonne si et seulement si elle sert de filtre
dans le payload Qdrant. La liste des colonnes promues et celle des champs du payload sont la
même liste, définie à un seul endroit du code.

**`units`** — une ligne par unité vectorisée.

| colonne | type | note |
|---|---|---|
| `unit_id` | uuid PK | `uuid5(page_id + content_hash + occurrence)` |
| `page_id` | bigint FK | |
| `unit_type` | text | `section` en v1 |
| `unit_index` | int | position — un attribut, jamais une identité |
| `heading` | text | titre de section, inclus dans le texte vectorisé |
| `text` | text | texte nettoyé, exactement ce qui est vectorisé |
| `content_hash` | text | hash du texte normalisé |
| `token_count` | int | |
| `embedded_at` | timestamptz | `NULL` = vecteur pas encore calculé |
| `model_name` | text | |

**`duplicate_candidates`**

| colonne | type | note |
|---|---|---|
| `candidate_id` | bigint PK | |
| `page_a`, `page_b` | bigint FK | contrainte `CHECK (page_a < page_b)` + unicité de la paire |
| `score` | real | |
| `status` | text | `nouveau`, `confirmé`, `rejeté`, `fusionné` |
| `model_name` | text | les scores dépendent du modèle |
| `run_id` | bigint FK | |
| `first_seen_at`, `updated_at` | timestamptz | |

**`candidate_evidence`** — `candidate_id`, `unit_a`, `unit_b`, `score`. Même normalisation
d'ordre. Un score seul est inexploitable pour la personne qui doit décider.

**`runs`** — `run_id`, `started_at`, `finished_at`, `watermark`, `pages_scanned`,
`units_created`, `units_embedded`, `status`.

**`run_errors`** — `error_id`, `run_id`, `page_id`, `step`, `message`, `occurred_at`.

### Qdrant — index jetable

Une collection par modèle : `wiki_units_3small_1536`. Le modèle est dans le **nom de la
collection**, pas dans le payload — changer de modèle crée une collection, ce qui permet d'en
faire tourner deux en parallèle pour les comparer.

Un point : `id` = `unit_id`, `vector` = float[1536], `payload` = `{page_id, unit_type, lang,
page_type, production}`.

**La collection déclare dès sa création un emplacement de vecteur sparse**, même si rien ne le
remplit en v1. Qdrant fige la configuration des vecteurs à la création : déclarer le créneau ne
coûte rien maintenant, alors que l'ajouter ensuite peut imposer de recréer la collection. Le
sparse servira à la recherche hybride, utile là où le dense est faible — références, sigles,
numéros AMM — et parce qu'il pondère par rareté, donc absorbe la ferraille répétée que le dense
encaisse mal.

**Critère du payload** : uniquement ce sur quoi on filtre *pendant* la recherche. Jamais de
titre, d'URL ni de texte. Tout ce qu'on affiche vient de PostgreSQL.

**Raison de la séparation** : l'index doit rester reconstructible sans perte. Changer de modèle
ou de découpage impose de détruire et reconstruire la collection.

Le filtrage se fait par filtre Qdrant (pré-filtrage pendant la traversée de l'index), pas par
post-filtrage des résultats — sinon une requête de dix résultats peut n'en rendre aucun d'utile.
Créer explicitement un index de payload sur chaque champ filtré.

## Le pipeline

| # | Étape | Lit | Écrit |
|---|---|---|---|
| 1 | Pages modifiées | `runs` (curseur), API wiki | rien |
| 2 | Extraction | API wiki | `pages` |
| 3 | Construction des unités | — | **rien** |
| 4 | Diff par hash | `units` | `units`, purge Qdrant |
| 5 | Vectorisation | `units` | Qdrant puis `units` |
| 6 | Recherche de voisins | Qdrant | rien |
| 7 | Agrégation, exclusions | `pages`, `units` | `duplicate_candidates`, `candidate_evidence` |
| 8 | Fin de run | — | `runs` |

Les étapes 1, 3 et 6 sont des transformations pures — testables sans base ni conteneur.

### Contraintes d'exécution

**L'étape 1 doit aussi récupérer les suppressions et renommages.** Ce sont des événements de
journal, ils n'apparaissent pas comme des modifications.

**L'étape 3 n'écrit rien, volontairement.** L'étape 4 doit comparer les unités produites à celles
déjà en base ; écrire avant la comparaison détruirait l'état de référence.

**Le diff est cadré par page.** Pour chaque page traitée, comparer ses unités en mémoire à ses
unités en base. Une unité absente de la mémoire n'est supprimée que si sa page fait partie du lot
traité — sinon on efface tout le corpus au premier run incrémental.

**Diff par contenu, jamais par position.** Une unité insérée décale toutes les suivantes :
comparer position par position conclut à tort que tout a changé. La comparaison d'ensembles de
hashs distingue nouveau / modifié / déplacé / supprimé. Une unité déplacée ne demande qu'une mise
à jour de `unit_index`.

**Ordre d'écriture à l'étape 5** : Qdrant d'abord, `embedded_at` ensuite. Dans l'ordre inverse,
une interruption marquerait comme fait un vecteur inexistant, perdu silencieusement. Le `NULL`
sert de mécanisme de reprise : après incident, retraiter tout ce qui a `embedded_at IS NULL`.

**Garde-fous de dépense à l'étape 5.** L'ordre d'écriture ci-dessus privilégie délibérément le
recalcul à la perte de vecteur — il va donc dans le sens de la dépense. Trois limites obligatoires,
toutes vérifiées **avant** le premier appel à l'API :

- **Plafond d'unités par run.** Un run incrémental traite quelques dizaines d'unités ; s'il en
  réclame des milliers, c'est une anomalie. Dépassement du plafond → arrêt, entrée dans
  `run_errors`, pas de traitement partiel silencieux.
- **Estimation du coût avant appel.** `SELECT SUM(token_count) FROM units WHERE embedded_at IS NULL`
  donne le volume à traiter ; au-delà d'un seuil, le run refuse de démarrer.
- **Mode à blanc.** Une option qui compte et chiffre sans appeler l'API, à utiliser
  systématiquement avant un backfill ou après un changement de découpage.

Ces limites sont des constantes lisibles, pas des valeurs enfouies. Elles ne remplacent pas le
plafond de dépense configuré côté OpenAI, qui reste la seule protection indépendante du code.

**Doublon mécanique (même `content_hash` sur deux pages) : pas de vecteur partagé.** Chaque
unité passe par l'étape 5 normalement, même si son contenu est identique à celui d'une unité
d'une autre page. L'alternative existait — copier le vecteur d'une unité « canonique » vers
l'autre pour épargner un appel API — mais le volume mesuré est faible (quelques dizaines
d'unités, qui devraient encore diminuer une fois les vrais doublons fusionnés par une personne)
et partager un vecteur créerait une dépendance entre deux `unit_id` pensés comme indépendants.
Le doublon reste signalé pour la revue humaine ; ce n'est que le recalcul du vecteur qui n'est
pas économisé. Choix à revoir si le volume de doublons exacts s'avère nettement plus élevé.

**Le curseur n'avance qu'en cas de run complet réussi**, sinon les pages non traitées ne sont
jamais rattrapées. Il se déduit de `runs`, sans table dédiée.

**Purge** : les unités disparues doivent voir leurs points supprimés dans Qdrant, sinon des
vecteurs orphelins remontent indéfiniment vers des lignes qui n'existent plus.

**Paires symétriques** : ne pas dédoublonner à l'étape 6 — l'index étant approximatif, garder les
deux directions améliore le rappel. La normalisation se fait à l'écriture, garantie par la
contrainte en base.

## Extraction et découpage

- Source : **API MediaWiki**, jamais d'accès direct à MySQL. Le schéma MediaWiki est interne et
  instable entre versions, le wikitext peut être compressé ou déporté, et l'API gère les
  redirections, namespaces, langlinks et propriétés SMW.
- **Aucun traitement spécifique par type de page.** Le texte vient du wikitext, les faits
  structurés des propriétés SMW — uniformes par construction. Le type de page est une **donnée**
  stockée et filtrée, jamais un branchement dans le code.
- **Ne pas parser les infobox depuis le wikitext.** Elles ne sont que le rendu des propriétés SMW,
  qu'on lit directement. Attention : `mwparserfromhell.strip_code()` supprime les templates.
- **Découpage par section.** Pas par paragraphe (vecteurs trop courts, instables), pas par page
  (dépasse la limite du modèle, et dilue). Découper les sections trop longues, fusionner celles de
  quelques lignes.
- Le **titre de section** fait partie du texte vectorisé. Le **titre de page** non : il relève
  d'une comparaison lexicale (`pg_trgm`).
- **Normaliser le texte avant de le hasher** (espaces, retours à la ligne), sinon une correction
  de mise en forme invalide le cache.
- **Une règle de nettoyage ne se déclenche que là où elle apporte un gain démontrable.** Elle est
  établie par la mesure, pas par l'intuition : on compte ce qui revient dans le corpus, on relit
  la liste pour écarter ce qui porte du sens (fréquent ≠ vide de sens), et on vérifie le résultat
  en recomptant après application. Se déclencher « au cas où » ajoute de la variabilité sans
  contrepartie. Voir `app/domain/cleaning.py`, dont les commentaires portent les mesures qui
  justifient chaque règle.
- **Les règles de nettoyage actuelles sont écrites pour le français**, la langue de cette
  instance (`xml:lang="fr"`). Mesuré : 0,17 % des pages ont un contenu majoritairement non
  français malgré ça — volume trop faible pour une règle dédiée aujourd'hui.

## Modèle d'unités

- **Schéma homogène**, avec `unit_type` comme discriminant.
- En v1, `unit_type` vaut toujours `section`. **L'infobox n'est pas vectorisée, sauf deux champs
  nommés sur les pages `Vidéo`.** La règle générale reste : valeurs catégorielles ou numériques,
  donc filtres plutôt que vecteurs (voir `docs/index.html`, section « Décision »). Exception
  mesurée : une page `Vidéo` (~28 % du corpus) n'a
  presque aucune prose hors de son infobox — son contenu réel (résumé rédigé, transcription
  automatique) vit dans les paramètres `Résumé` et `Transcription`. Sans extraction ciblée de ces
  deux champs, ces pages ne produiraient aucune unité, invisibles au dédoublonnage comme à la
  recommandation. Le reste de l'infobox `Vidéo` (durée, vignette, producteur, id YouTube) reste un
  filtre, comme pour toute autre page. `unit_type` reste en place si d'autres champs de prose
  comparables sont identifiés ailleurs.
- **Pas de vecteur d'article entier.** La similarité entre pages s'obtient par **agrégation par
  maximum** des similarités entre unités — la moyenne noie le cas d'inclusion, qui est le doublon
  le plus fréquent sur un wiki.
- **`unit_id` dérive du contenu, jamais de la position.** Le rang d'occurrence ne sert qu'à
  départager deux unités rigoureusement identiques dans une même page.
- Deux stratégies d'identité opposées et délibérées : `page_id` est stable (on suit une page à
  travers ses modifications), `unit_id` dépend du contenu (on veut qu'un texte modifié soit une
  nouvelle unité).

## Exclusions

- une page avec elle-même, et deux unités d'une même page
- les pages de redirection — exclusion **à l'ingestion**, on ne crée pas d'unités
- les comparaisons entre langues : le filtre `lang` dans la requête Qdrant suffit et évite de
  raisonner sur les ensembles de traductions

## Modèle d'embeddings

`text-embedding-3-small`, 1536 dimensions — le même que sur Itinera. Deux index construits avec le
même modèle vivent dans le même espace vectoriel, ce qui laisse ouverte la possibilité de relier
la documentation et l'application. **Ne pas réduire la dimension**, cela romprait cette
compatibilité.

Le backend reste abstrait derrière une interface `EmbeddingBackend`, avec une seconde
implémentation locale, pour permettre la comparaison mesurée sur le jeu annoté.

Voir `docs/embeddings-portee-et-limites.md` pour ce que les vecteurs capturent et ce qu'ils ne
capturent pas. En résumé : les nombres, la négation, les identifiants et références s'encodent
mal. Ce n'est pas bloquant ici — le pipeline propose, un humain décide — mais ça explique
pourquoi les grandeurs vont dans les filtres et les références dans une recherche lexicale.

## Calibration

Aucun seuil ni paramètre choisi par conviction. Voir `docs/calibration.md`.

- Deux seuils distincts : entre unités (permissif, pour ne rien perdre avant l'agrégation) et
  entre pages (ce qu'un humain voit).
- La recherche combine `score_threshold` comme critère et `limit` comme garde-fou. Une unité qui
  atteint la limite est un signal à logger, probablement du texte répétitif.
- Le jeu annoté est **versionné dans le dépôt**, pas en base. Il doit contenir des paires
  d'origines variées, sinon seule la précision est mesurable et le rappel reste inconnu.
- Pendant la calibration, conserver les scores bruts dans une table de travail séparée, pour
  rejouer des seuils sans recalculer de vecteurs ni polluer la table lue par la revue.

## Observabilité

Trois couches :

- **logs applicatifs** sur `stdout`, structurés — éphémères, pour déboguer ;
- **`runs`** — agrégat durable par exécution, alimente la page de statut ;
- **`run_errors`** — détail durable des échecs.

Règle : si la question se pose une fois pour déboguer, c'est un log. Si elle se pose
régulièrement ou doit apparaître dans une interface, c'est une table.

## Conventions techniques

- **Python**, **Poetry** (`pyproject.toml`, `poetry.lock` — le lock est versionné).
- **Idempotence** : réexécuter le pipeline ne doit jamais dupliquer de données.
- **Le run incrémental doit être déclenchable de l'extérieur**, puisque n8n l'appellera. Le point
  d'entrée démarre l'exécution et répond immédiatement ; il n'attend pas la fin du traitement,
  sinon la requête expire. L'avancement se consulte séparément, via un point d'état alimenté par
  `runs`.
- **Le backfill n'est pas une route HTTP.** Trop long pour une requête, et lancé à la main. Même
  image, commande différente : `docker compose run --rm app python -m app.backfill`.
- **Poetry ne crée pas de virtualenv dans le conteneur** (`POETRY_VIRTUALENVS_CREATE=false`) :
  le conteneur est déjà l'isolation. Les commandes s'écrivent donc `python -m …`, jamais
  `poetry run python -m …`.
- **Le Dockerfile copie `pyproject.toml` et `poetry.lock` avant le code**, pour que Docker
  réutilise la couche d'installation tant que les dépendances ne changent pas. Ne pas remettre
  un `COPY .` avant l'installation.
- **Ajouter une dépendance se fait dans le conteneur** (`docker compose run --rm app poetry add X`),
  pour que la résolution ait lieu dans l'environnement Linux qui est la cible réelle — puis
  `docker compose build` pour la prendre en compte.
- **Service interne** : pas de `ports:` exposés en production, pas de label Traefik. Appelé par
  n8n depuis le réseau Docker interne. Seule la page de revue peut éventuellement être exposée,
  et alors derrière une authentification.
- Conteneurs locaux : `wiki-embeddings`, `postgres`, `qdrant`, `dbgate`.
- Les contraintes d'intégrité vivent **en base** (`CHECK`, unicité, clés étrangères), pas
  seulement dans le code.

### Messages de commit

Convention **Conventional Commits** : `type: description` en résumé, description à l'impératif
présent, en minuscule, sans point final. Le corps du message explique le *pourquoi* si ce n'est
pas évident.

| type | usage |
|---|---|
| `feat` | nouvelle fonctionnalité (version mineure en SemVer) |
| `fix` | correction de bogue (version patch) |
| `docs` | documentation uniquement |
| `style` | formatage, espacements — aucun impact sur le comportement |
| `refactor` | remaniement sans correction ni ajout de fonctionnalité |
| `test` | ajout ou correction de tests |
| `perf` | amélioration des performances |
| `build`, `ci` | système de build, dépendances, intégration continue |
| `chore` | tâche de maintenance sans effet sur le code applicatif |

D'autres types sont admis s'ils clarifient l'intention. Un changement incompatible se marque par
`!` après le type (`feat!:`) ou une ligne `BREAKING CHANGE:` dans le corps.

## Commandes

À compléter au fur et à mesure.

## Ce qu'il ne faut pas faire

- **Ne jamais écrire dans le wiki.** Lecture seule sur MediaWiki.
- Ne pas lancer de calcul lourd sur l'environnement de production de Neayi.
- Ne pas committer de clés API, de dumps de base, ni de fichiers `.env`.
- Ne pas mettre de contenu métier dans le payload Qdrant.
- Ne pas conclure qu'une unité a changé sur la base de sa position.
- Ne pas vider `duplicate_candidates` : les décisions humaines survivent aux réexécutions et aux
  changements de modèle.
- Ne pas écrire « chunk ».
