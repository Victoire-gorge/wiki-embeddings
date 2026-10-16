"""Construction des unités (étape 3 du pipeline) — transformation pure.

Cette étape ne lit ni n'écrit rien en base : elle prend le wikitext d'une page
et détermine les frontières des sections. Le nettoyage du markup (templates,
liens, tableaux) est une étape séparée, volontairement : ici on ne fait que
découper.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import mwparserfromhell

# Frontière de phrase : ponctuation forte suivie d'une espace. Même
# définition que la mesure 3 du notebook de calibrage, pour rester cohérent
# avec ce qui a servi à décider si cette cascade était nécessaire.
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+")


def est_page_json(wikitext: str) -> bool:
    """Détecte une page dont le contenu entier est du JSON, pas du wikitexte.

    Mesuré sur ce wiki : 317 pages (3,3 % du corpus) sont des pages de
    données pour un widget de graphique — jamais de la prose, juste de la
    configuration (couleurs, séries, UUID). Le titre finit par ".json" sur
    315 d'entre elles, mais pas sur les 2 autres : le contenu lui-même,
    pas une convention de nommage, est le seul signal fiable à 100 %.

    Ces pages ne doivent jamais être découpées en sections : ce n'est pas un
    problème de nettoyage de texte, c'est une page qui n'est pas un article.
    """
    try:
        contenu = json.loads(wikitext)
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(contenu, dict)


@dataclass(frozen=True)
class RawSection:
    """Une section brute, avant nettoyage du markup.

    `heading` peut encore contenir des liens ou du formatage wiki
    (ex. ``[[Bioagresseurs]]``) : le nettoyer est la responsabilité de
    l'étape suivante, pas de celle-ci.
    """

    unit_index: int
    heading: str | None
    wikitext: str


def extract_tables(wikitext: str) -> tuple[str, list[str]]:
    """Retire les tableaux wiki (`{| ... |}`) du wikitext d'une page.

    Un tableau n'est pas de la prose : `strip_code()` colle ses cellules sans
    aucun séparateur (mesuré : "Organisme Impact ..." devient
    "OrganismeImpact..."), et mwparserfromhell 0.6 n'a pas d'API structurée
    (lignes/cellules) pour les traiter proprement. On les extrait donc avant
    le découpage en sections, pour que le nettoyage du texte n'ait jamais à
    les gérer.

    Les tableaux retirés sont renvoyés tels quels, pas jetés : une partie
    contient de vraies données (annuaires de contact, tableaux d'intrants),
    à explorer séparément pour décider quels champs récurrents méritent de
    devenir des filtres — pas tranché ici.
    """
    code = mwparserfromhell.parse(wikitext)
    tables = code.filter_tags(matches=lambda tag: tag.tag == "table")
    raw_tables = [str(table) for table in tables]
    for table in tables:
        try:
            code.remove(table)
        except ValueError:
            # Tableau imbriqué : déjà retiré avec le tableau parent qui le
            # contenait. Son wikitext brut reste dans raw_tables (capturé
            # avant le retrait), rien n'est perdu.
            pass
    return str(code), raw_tables


def splice_video_fields(wikitext: str) -> str:
    """Réinjecte le résumé et la transcription d'une page `Vidéo` comme sections.

    Une page `Vidéo` porte son vrai contenu dans des paramètres de template —
    pas dans le corps de l'article — pour deux champs distincts : un résumé
    court (paramètre `Résumé` du template `Vidéo` lui-même) et, séparément, un
    résumé long (template `Résumé long`, souvent structuré avec ses propres
    titres `==`) et une transcription (template `Transcription`). Sans ce
    repli, ces pages (~28 % du corpus) ne produisent aucune unité : les
    templates sont retirés tels quels par `clean_markup` en aval.

    Les deux résumés sont gardés sous deux titres distincts plutôt que l'un
    des deux choisi d'avance : lequel est le plus utile se mesure sur les
    embeddings, pas par principe (mesuré : 1325 pages sur 1809 ont les deux,
    74 n'ont que le court).

    Ce n'est pas un branchement par type de page : c'est l'extraction de trois
    champs nommés, qui deviennent des sections comme les autres dès qu'on
    repasse par `split_into_sections` — y compris les sous-titres internes du
    résumé long, récupérés sans traitement supplémentaire.
    """
    code = mwparserfromhell.parse(wikitext)
    templates = code.filter_templates()

    video_template = next(
        (t for t in templates if str(t.name).strip().lower() in ("vidéo", "video")),
        None,
    )
    if video_template is None:
        return wikitext

    def champ(template, nom_param):
        for param in template.params:
            if str(param.name).strip().lower() == nom_param:
                valeur = str(param.value).strip()
                if valeur:
                    return valeur
        return None

    resume_court = champ(video_template, "résumé")

    resume_long = None
    transcription = None
    for t in templates:
        name = str(t.name).strip().lower()
        if name.startswith("résumé") and t is not video_template:
            resume_long = champ(t, "résumé") or resume_long
        elif name == "transcription":
            transcription = champ(t, "transcription") or transcription

    for t in templates:
        name = str(t.name).strip().lower()
        if (
            name in ("vidéo", "video")
            or name.startswith("résumé")
            or name == "transcription"
        ):
            try:
                code.remove(t)
            except ValueError:
                pass  # déjà retiré (imbriqué dans un template déjà retiré)

    # Niveau 1, pas 2 : le résumé long a souvent ses propres sous-titres à
    # "==" (mesuré sur une page réelle : jusqu'à 3 niveaux de profondeur).
    # Au même niveau que "Résumé long", ils le dépileraient comme un frère
    # plutôt que de s'y imbriquer — perdant tout fil vers "Résumé long" dans
    # le titre de chaque unité qui en résulte. Un niveau en dessous, l'algo
    # générique de fil d'ancêtres les traite comme des enfants, sans aucun
    # branchement spécifique aux pages Vidéo.
    sections = []
    if resume_court:
        sections.append(f"= Résumé court =\n{resume_court}")
    if resume_long:
        sections.append(f"= Résumé long =\n{resume_long}")
    if transcription:
        sections.append(f"= Transcription =\n{transcription}")

    reste = str(code).strip()
    return "\n\n".join(([reste] if reste else []) + sections)


def _heading_breadcrumbs(headings: list) -> list[str]:
    """Pour chaque titre, dans l'ordre du document, son chemin depuis la racine.

    Un titre de même niveau (ou moins profond) que celui au sommet de la pile
    n'est pas son enfant : on dépile avant d'empiler, pour qu'un rameau ne
    hérite pas du contexte d'un rameau frère déjà refermé.
    """
    pile: list[tuple[int, str]] = []
    chemins = []
    for heading in headings:
        niveau = heading.level
        titre = str(heading.title).strip()
        while pile and pile[-1][0] >= niveau:
            pile.pop()
        pile.append((niveau, titre))
        chemins.append(" > ".join(t for _, t in pile))
    return chemins


def split_into_sections(wikitext: str) -> list[RawSection]:
    """Découpe le wikitext d'une page en sections, titres inclus.

    Utilise ``get_sections(flat=True)`` : chaque section ne contient que son
    propre contenu, jamais celui de ses sous-sections (contrairement au mode
    non-flat, qui les imbrique et dupliquerait le texte entre une section et
    ses enfants). Le contenu avant le premier titre forme une section de tête
    avec ``heading=None``.

    Le titre de chaque section inclut le fil de ses ancêtres (``"A > B > C"``)
    même quand ceux-ci n'ont pas de texte propre : beaucoup de pages de ce
    wiki imbriquent la seule prose utile sous deux ou trois titres vides
    (ex. ``1. Présentation > Caractérisation de la technique > Description``)
    — sans ce fil, cette unité perdrait tout contexte une fois ses ancêtres
    filtrés à l'étape suivante pour absence de texte.
    """
    code = mwparserfromhell.parse(wikitext)
    sections = code.get_sections(flat=True, include_lead=True, include_headings=True)
    chemins = _heading_breadcrumbs(code.filter_headings())

    raw_sections = []
    for index, section in enumerate(sections):
        # get_sections() renvoie des fragments qui partagent leurs noeuds avec
        # l'arbre `code` d'origine : muter un fragment mute `code`. On reparse
        # une chaîne indépendante avant de retirer le titre pour éviter cet
        # effet de bord.
        fragment = mwparserfromhell.parse(str(section))
        headings = fragment.filter_headings()
        heading = None
        if headings:
            heading = chemins[index - 1]
            fragment.remove(headings[0])

        raw_sections.append(
            RawSection(
                unit_index=index, heading=heading, wikitext=str(fragment).strip()
            )
        )

    return raw_sections


def _decouper_phrases(texte: str) -> list[str]:
    return [p for p in _FIN_DE_PHRASE.split(texte) if p]


def _coupe_equilibree(
    texte: str, cible: int, compte_tokens: Callable[[str], int]
) -> list[str]:
    """Dernier recours : découpe par nombre de mots, à défaut de ponctuation.

    Approximatif par construction — répartit les *mots* en parts égales,
    pas les tokens, pour n'appeler `compte_tokens` qu'une fois sur
    l'ensemble plutôt qu'à chaque mot. Assez bon : la taille cible n'a pas
    besoin d'être exacte (480 ou 520 tokens sont indiscernables pour un
    embedding), et le pire mot isolé mesuré sur ce wiki fait 46 tokens —
    largement sous toute taille cible envisagée, donc jamais de quoi faire
    déborder une part de façon significative.
    """
    mots = texte.split()
    k = math.ceil(compte_tokens(texte) / cible)
    taille = math.ceil(len(mots) / k)
    return [
        " ".join(mots[i:i + taille])
        for i in range(0, len(mots), taille)
    ]


def atomiser(
    texte: str, cible: int, compte_tokens: Callable[[str], int]
) -> list[str]:
    """Découpe `texte` en atomes qui tiennent chacun sous `cible` tokens.

    Cascade, chaque niveau n'intervenant que si le précédent ne suffit pas :

    1. un paragraphe (séparé par une ligne vide) qui tient déjà sous `cible`
       est un atome tel quel ;
    2. sinon, ses phrases ;
    3. sinon, une coupe équilibrée par nombre de mots (`_coupe_equilibree`) —
       le cas des transcriptions, qui n'ont ni paragraphe ni ponctuation
       forte (mesuré : moins de 2 % en ont une tous les ~1300 tokens).

    `compte_tokens` est injecté plutôt qu'un appel direct à `tiktoken` : ça
    garde cette transformation testable sans réseau, et laisse la place à
    un second tokenizer pour le futur `EmbeddingBackend` local.

    Un paragraphe vide (ligne vide répétée) ne produit aucun atome — pas une
    unité à filtrer plus tard, simplement rien à découper.
    """
    texte = texte.strip()
    if not texte:
        return []
    if compte_tokens(texte) <= cible:
        return [texte]

    paragraphes = [p for p in texte.split("\n\n") if p.strip()]
    if len(paragraphes) > 1:
        atomes = []
        for paragraphe in paragraphes:
            atomes.extend(atomiser(paragraphe, cible, compte_tokens))
        return atomes

    phrases = _decouper_phrases(texte)
    if len(phrases) > 1:
        atomes = []
        for phrase in phrases:
            atomes.extend(atomiser(phrase, cible, compte_tokens))
        return atomes

    return _coupe_equilibree(texte, cible, compte_tokens)


def remplir(
    atomes: list[str], cible: int, plancher: int, compte_tokens: Callable[[str], int]
) -> list[str]:
    """Empile des atomes en groupes qui tiennent chacun sous `cible`.

    Glouton : ajoute un atome au groupe courant tant que ça tient, ferme le
    groupe et en ouvre un nouveau dès que le suivant ne rentre plus.

    Recollage : un groupe qui tombe sous `plancher` une fois isolé est
    rattaché à un voisin (le précédent si possible, sinon le suivant)
    plutôt que laissé seul — en acceptant que le groupe obtenu dépasse
    `cible` d'autant. Pas seulement le dernier groupe : un titre court suivi
    d'une première phrase courte peut produire un groupe de tête tout aussi
    isolé (mesuré sur ce wiki — ex. "Céréales > Principales variétés").
    C'est la seule fusion conservée dans tout le pipeline, et elle est sûre :
    elle ne recolle que des atomes voisins d'une même section, jamais deux
    sujets différents.
    """
    groupes: list[list[str]] = []
    groupe_courant: list[str] = []
    taille_courante = 0

    for atome in atomes:
        taille_atome = compte_tokens(atome)
        if groupe_courant and taille_courante + taille_atome > cible:
            groupes.append(groupe_courant)
            groupe_courant = []
            taille_courante = 0
        groupe_courant.append(atome)
        taille_courante += taille_atome

    if groupe_courant:
        groupes.append(groupe_courant)

    i = 0
    while len(groupes) > 1 and i < len(groupes):
        if compte_tokens(" ".join(groupes[i])) < plancher:
            if i > 0:
                groupes[i - 1].extend(groupes[i])
                del groupes[i]
            else:
                groupes[1] = groupes[0] + groupes[1]
                del groupes[0]
            continue  # le groupe à cette position vient de changer, réévaluer
        i += 1

    return [" ".join(groupe) for groupe in groupes]


@dataclass(frozen=True)
class Unit:
    """Une unité finale — le fragment prêt à stocker et vectoriser.

    `unit_index` est relatif aux unités rendues par un seul appel de
    `construire_unites`, pas à la page entière : renuméroter à l'échelle de
    la page revient à l'appelant qui combine plusieurs sections, puisque
    cette fonction ne voit qu'une section à la fois.

    `page_id` et `unit_id` valent `None` tant que cette fonction les rend :
    elle ne connaît pas `page_id`, donc ne peut pas calculer `unit_id`
    (`uuid5(page_id + content_hash + occurrence)`) elle-même. Même
    convention que `embedded_at` dans la table `units` — `None` signifie
    « pas encore calculé », pas « n'existe pas ». C'est
    `construire_unites_page` (`app/domain/pipeline.py`) qui les remplit.
    """

    unit_index: int
    heading: str | None
    text: str
    content_hash: str
    token_count: int
    page_id: int | None = None
    unit_id: uuid.UUID | None = None


def construire_unites(
    heading: str | None,
    corps: str,
    cible: int,
    plancher: int,
    compte_tokens: Callable[[str], int],
) -> list[Unit]:
    """Transforme le corps nettoyé d'une `RawSection` en zéro, une ou plusieurs `Unit`.

    Zéro si le corps est vide, ou si le texte complet (titre compris) tombe
    sous `plancher` — une section trop courte est jetée, jamais fusionnée
    avec sa voisine (`CLAUDE.md` : fusionner coulerait deux idées distinctes
    dans un vecteur qui ne représente ni l'une ni l'autre).

    Le titre est inclus dans le budget de **chaque** morceau si la section
    se scinde, pas combiné une seule fois avant découpage : sinon les
    morceaux après le premier perdraient tout contexte de section une fois
    vectorisés.
    """
    corps = corps.strip()
    if not corps:
        return []

    prefixe = f"{heading}\n" if heading else ""
    if compte_tokens(prefixe + corps) < plancher:
        return []

    if compte_tokens(prefixe + corps) <= cible:
        textes = [corps]
        cible_corps = cible
    else:
        cible_corps = max(1, cible - compte_tokens(prefixe))
        atomes = atomiser(corps, cible_corps, compte_tokens)
        textes = remplir(atomes, cible_corps, plancher, compte_tokens)

    unites = []
    for index, morceau in enumerate(textes):
        texte = prefixe + morceau
        unites.append(
            Unit(
                unit_index=index,
                heading=heading,
                text=texte,
                content_hash=hashlib.sha256(texte.encode()).hexdigest(),
                token_count=compte_tokens(texte),
            )
        )
    return unites
