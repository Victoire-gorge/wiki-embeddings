"""Orchestration de l'étape 3 (construction des unités) pour une page entière.

`units.py` (découpage structurel) et `cleaning.py` (nettoyage du texte)
restent indépendants l'un de l'autre, volontairement — voir leurs docstrings
respectives. Ce module est celui qui les compose pour produire les `Unit`
finales d'une page, et rien d'autre : pas de logique propre ici.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Callable

from app.domain.cleaning import (
    clean_markup,
    collapse_repeated_phrases,
    strip_introductory_phrase,
    strip_reporting_frame,
)
from app.domain.units import (
    Unit,
    build_units,
    extract_tables,
    is_json_page,
    splice_video_fields,
    split_into_sections,
)

# Espace de noms fixe pour calculer unit_id par uuid5 — à ne JAMAIS changer
# une fois choisi : le changer recalculerait silencieusement tous les
# unit_id au run suivant, invalidant tout embedded_at et forçant un
# backfill complet. Généré une fois avec uuid.uuid4(), figé ici pour de bon.
_NAMESPACE_UNIT_ID = uuid.UUID("cb78bcab-df4f-4d5f-bca4-d66a79fa2da0")


def build_page_units(
    page_id: int,
    wikitext: str,
    cible: int,
    plancher: int,
    compte_tokens: Callable[[str], int],
) -> list[Unit]:
    """Transforme le wikitext d'une page en `Unit` finales.

    Rien pour une page de données JSON (`is_json_page`) — exclusion à
    l'ingestion, ce n'est pas une page à découper du tout.

    `unit_index` est renuméroté à l'échelle de la **page**, pas par section :
    `build_units` ne voit qu'une section à la fois et ne peut pas le
    faire elle-même. `unit_id` est calculé ici pour la même raison : c'est
    la première fonction de l'appel qui connaît à la fois `page_id` et
    l'occurrence d'un `content_hash` au sein de la page entière.
    """
    if is_json_page(wikitext):
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
            build_units(heading, corps, cible, plancher, compte_tokens)
        )

    occurrences: dict[str, int] = {}
    unites_finales = []
    for index, unite in enumerate(unites):
        occurrence = occurrences.get(unite.content_hash, 0)
        occurrences[unite.content_hash] = occurrence + 1
        unit_id = uuid.uuid5(
            _NAMESPACE_UNIT_ID, f"{page_id}:{unite.content_hash}:{occurrence}"
        )
        unites_finales.append(
            dataclasses.replace(
                unite, unit_index=index, page_id=page_id, unit_id=unit_id
            )
        )

    return unites_finales
