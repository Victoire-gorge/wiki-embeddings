from dataclasses import dataclass

from app.domain.units import Unit


@dataclass(frozen=True)
class SpendingEstimate:
    """Ce que coûterait la vectorisation des unités passées, sans appeler
    l'API — c'est cette estimation seule que sert le mode à blanc."""

    unit_count: int
    token_count: int


class SpendingCapExceeded(Exception):
    def __init__(self, estimate: SpendingEstimate, max_units: int, max_tokens: int):
        self.estimate = estimate
        self.max_units = max_units
        self.max_tokens = max_tokens
        super().__init__(
            f"{estimate.unit_count} unités ({estimate.token_count} tokens) "
            f"dépasse le plafond ({max_units} unités, {max_tokens} tokens) — "
            "probablement une anomalie, pas un run incrémental normal."
        )


def estimate_spending(units: list[Unit]) -> SpendingEstimate:
    return SpendingEstimate(
        unit_count=len(units),
        token_count=sum(unit.token_count for unit in units),
    )


def assert_within_cap(
    estimate: SpendingEstimate, max_units: int, max_tokens: int
) -> None:
    """Lève avant le premier appel API si l'étape 5 réclame plus que ce
    qu'un run incrémental normal devrait traiter — voir CLAUDE.md, « Garde-
    fous de dépense à l'étape 5 »."""
    if estimate.unit_count > max_units or estimate.token_count > max_tokens:
        raise SpendingCapExceeded(estimate, max_units, max_tokens)
