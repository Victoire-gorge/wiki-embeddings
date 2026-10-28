from collections import defaultdict
from dataclasses import dataclass

from app.domain.units import Unit


@dataclass(frozen=True)
class DiffResult:
    """Résultat de la comparaison des unités d'une page entre la mémoire
    (ce que l'étape 3 vient de produire) et la base (ce qui y était déjà).

    `modified` rapproche un couple (ancienne, nouvelle) pour le reporting —
    cette information n'est jamais utilisée pour décider quoi écrire : une
    unité « modifiée » est, du point de vue de l'écriture, une suppression
    plus une création, exactement comme un nouveau et un supprimé non
    rapprochés.
    """

    unchanged: list[Unit]
    new: list[Unit]
    deleted: list[Unit]
    moved: list[Unit]
    modified: list[tuple[Unit, Unit]]


def diff_units(in_memory: list[Unit], in_db: list[Unit]) -> DiffResult:
    """Compare les unités d'une page entre mémoire et base, par contenu.

    `unit_id` dépend du contenu (jamais de la position), donc deux unités
    partageant le même `unit_id` ont le même texte : seul `unit_index` peut
    différer, ce qui signale un déplacement plutôt qu'une modification.
    """
    units_in_db = {unit.unit_id: unit for unit in in_db}
    units_in_memory = {unit.unit_id: unit for unit in in_memory}

    unchanged: list[Unit] = []
    moved: list[Unit] = []
    new: list[Unit] = []
    for unit in in_memory:
        db_unit = units_in_db.get(unit.unit_id)
        if db_unit is None:
            new.append(unit)
        elif db_unit.unit_index == unit.unit_index:
            unchanged.append(unit)
        else:
            moved.append(unit)

    deleted = [unit for unit in in_db if unit.unit_id not in units_in_memory]

    modified, new, deleted = _match_by_heading(new, deleted)

    return DiffResult(
        unchanged=unchanged, new=new, deleted=deleted, moved=moved, modified=modified
    )


def _match_by_heading(
    new: list[Unit], deleted: list[Unit]
) -> tuple[list[tuple[Unit, Unit]], list[Unit], list[Unit]]:
    """Rapproche un nouveau et un supprimé de même titre, seulement s'il n'y
    en a exactement qu'un de chaque côté pour ce titre — sinon rien ne dit
    lequel remplace lequel, et deviner serait pire que ne rien rapprocher."""
    new_by_heading: dict[str, list[Unit]] = defaultdict(list)
    for unit in new:
        new_by_heading[unit.heading].append(unit)
    deleted_by_heading: dict[str, list[Unit]] = defaultdict(list)
    for unit in deleted:
        deleted_by_heading[unit.heading].append(unit)

    matched_new_ids = set()
    matched_deleted_ids = set()
    modified = []
    for heading, news in new_by_heading.items():
        deletions = deleted_by_heading.get(heading, [])
        if len(news) == 1 and len(deletions) == 1:
            modified.append((deletions[0], news[0]))
            matched_new_ids.add(news[0].unit_id)
            matched_deleted_ids.add(deletions[0].unit_id)

    remaining_new = [unit for unit in new if unit.unit_id not in matched_new_ids]
    remaining_deleted = [
        unit for unit in deleted if unit.unit_id not in matched_deleted_ids
    ]
    return modified, remaining_new, remaining_deleted
