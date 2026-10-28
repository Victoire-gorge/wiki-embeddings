# wiki-embeddings

Indexation sémantique du wiki [Triple Performance](https://wiki.tripleperformance.fr) —
détection des pages en doublon, et socle pour la recommandation d'articles.

> **Statut : en construction.** L'étape 3 (construction des unités) est entièrement implémentée
> et testée : nettoyage du wikitext mesuré sur le corpus réel, découpage par taille, calcul des
> identifiants. Les étapes 1, 2 et 4 à 8 restent à écrire ; les seuils de calibration restent à
> établir sur le jeu annoté.

## Le problème

Triple Performance est un commun de connaissances agroécologiques opéré par
[Neayi](https://neayi.com) : plusieurs milliers d'articles rédigés collaborativement,
multilingues, consultés par environ 70 000 visiteurs par mois.

Comme sur tout wiki collaboratif, du contenu redondant s'accumule : deux contributeurs
documentent le même sujet sans savoir que l'autre l'a déjà fait. La recherche actuelle repose sur
des mots-clés et des facettes, ce qui ne permet ni de repérer ces redondances, ni de rapprocher
des contenus qui disent la même chose avec des mots différents.

Ce service calcule une représentation vectorielle de chaque section d'article, et s'en sert pour
proposer à une relecture humaine les paires de pages susceptibles de faire doublon.

Le même index constitue la base d'un second usage, prioritaire pour la plateforme : recommander
à un visiteur les retours d'expérience pertinents pour ce qu'il est en train de lire.

## Comment ça marche

Un pipeline déclenché périodiquement, en huit étapes :

1. **Pages modifiées** — interroger le wiki pour les pages créées, modifiées ou supprimées
   depuis la dernière exécution.
2. **Extraction** — récupérer le texte source et les propriétés Semantic MediaWiki via l'API.
3. **Construction des unités** — nettoyer le wikitext et le découper en sections.
4. **Diff par hash** — ne conserver que ce qui a réellement changé, distinguer les sections
   modifiées de celles simplement déplacées.
5. **Vectorisation** — calculer un vecteur par unité nouvelle ou modifiée.
6. **Recherche de voisins** — interroger l'index vectoriel pour trouver les unités proches.
7. **Agrégation** — passer d'un score entre sections à un score entre pages, appliquer les
   exclusions.
8. **Revue** — présenter les candidats à un humain, qui tranche.

Le détail de l'architecture et de la structure des données est dans
[`docs/index.html`](docs/index.html).

## Pile technique

| | |
|---|---|
| Application | Python, Poetry |
| Source de vérité | PostgreSQL |
| Index vectoriel | Qdrant |
| Embeddings | `text-embedding-3-small` |
| Orchestration | n8n |
| Exécution | Docker |

## Documentation

- [`docs/index.html`](docs/index.html) — architecture et structure des données, avec exemples
- [`docs/embeddings-portee-et-limites.md`](docs/embeddings-portee-et-limites.md) — ce que les
  vecteurs capturent et ce qu'ils ne capturent pas
- [`docs/calibration.md`](docs/calibration.md) — comment les seuils et paramètres sont établis
- [`CLAUDE.md`](CLAUDE.md) — conventions et décisions, à destination des agents de code

## Démarrage

```bash
poetry install
poetry run pytest -q   # étape 3 : transformation pure, testable sans base ni conteneur
```

`docker compose up --build` démarre PostgreSQL, Qdrant et le service — mais `app/main.py` n'est
encore qu'un squelette (pas de point d'entrée HTTP réel tant que les étapes 1 à 8 ne sont pas
toutes écrites).

## Principes

**Lecture seule sur le wiki.** Ce service n'écrit jamais dans Triple Performance.

**L'index vectoriel est jetable.** Toute la donnée métier vit dans PostgreSQL ; Qdrant ne
contient que des vecteurs et de quoi filtrer. On doit pouvoir reconstruire l'index entier sans
rien perdre.

**Rien n'est décidé automatiquement.** Le pipeline produit des candidats, un humain tranche, et
sa décision est conservée d'une exécution à l'autre.

**Aucun paramètre choisi par conviction.** Les seuils sont établis sur un jeu de paires annotées,
et documentés avec les mesures qui les justifient.

## Licence

MIT — voir [`LICENSE`](LICENSE).

Projet contribué bénévolement à Neayi.
