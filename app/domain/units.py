"""Construction des unités (étape 3 du pipeline) — transformation pure.

Cette étape ne lit ni n'écrit rien en base : elle prend le wikitext d'une page
et détermine les frontières des sections. Le nettoyage du markup (templates,
liens, tableaux) est une étape séparée, volontairement : ici on ne fait que
découper.
"""

from __future__ import annotations

from dataclasses import dataclass

import mwparserfromhell


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


def split_into_sections(wikitext: str) -> list[RawSection]:
    """Découpe le wikitext d'une page en sections, titres inclus.

    Utilise ``get_sections(flat=True)`` : chaque section ne contient que son
    propre contenu, jamais celui de ses sous-sections (contrairement au mode
    non-flat, qui les imbrique et dupliquerait le texte entre une section et
    ses enfants). Le contenu avant le premier titre forme une section de tête
    avec ``heading=None``.
    """
    code = mwparserfromhell.parse(wikitext)
    sections = code.get_sections(flat=True, include_lead=True, include_headings=True)

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
            heading = str(headings[0].title).strip()
            fragment.remove(headings[0])

        raw_sections.append(
            RawSection(unit_index=index, heading=heading, wikitext=str(fragment).strip())
        )

    return raw_sections
