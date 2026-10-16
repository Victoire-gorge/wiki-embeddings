"""Orchestration de l'étape 3 (construction des unités) pour une page entière.

`units.py` (découpage structurel) et `cleaning.py` (nettoyage du texte)
restent indépendants l'un de l'autre, volontairement — voir leurs docstrings
respectives. Ce module est celui qui les compose pour produire les `Unit`
finales d'une page, et rien d'autre : pas de logique propre ici.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from app.domain.cleaning import (
    clean_markup,
    collapse_repeated_phrases,
    strip_introductory_phrase,
    strip_reporting_frame,
)
from app.domain.units import (
    Unit,
    construire_unites,
    est_page_json,
    extract_tables,
    splice_video_fields,
    split_into_sections,
)


def construire_unites_page(
    wikitext: str,
    cible: int,
    plancher: int,
    compte_tokens: Callable[[str], int],
) -> list[Unit]:
    """Transforme le wikitext d'une page en `Unit` finales.

    Rien pour une page de données JSON (`est_page_json`) — exclusion à
    l'ingestion, ce n'est pas une page à découper du tout.

    `unit_index` est renuméroté à l'échelle de la **page**, pas par section :
    `construire_unites` ne voit qu'une section à la fois et ne peut pas le
    faire elle-même.
    """
    if est_page_json(wikitext):
        return []

    wikitext = splice_video_fields(wikitext)
    wikitext, _tableaux = extract_tables(wikitext)

    unites: list[Unit] = []
    for section in split_into_sections(wikitext):
        corps = clean_markup(section.wikitext)
        corps = strip_introductory_phrase(corps)
        corps = strip_reporting_frame(corps)
        heading = clean_markup(section.heading) if section.heading else None
        if heading and "Transcription" in heading:
            corps = collapse_repeated_phrases(corps)
        unites.extend(
            construire_unites(heading, corps, cible, plancher, compte_tokens)
        )

    return [dataclasses.replace(u, unit_index=i) for i, u in enumerate(unites)]
