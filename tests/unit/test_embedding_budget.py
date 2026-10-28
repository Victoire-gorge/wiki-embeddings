import pytest

from app.domain.embedding_budget import (
    SpendingCapExceeded,
    assert_within_cap,
    estimate_spending,
)
from app.domain.units import Unit


def _unit(token_count):
    return Unit(
        unit_index=0,
        heading=None,
        text="x",
        content_hash="h",
        token_count=token_count,
    )


def test_estimate_spending_compte_les_unites_et_somme_les_tokens():
    units = [_unit(10), _unit(25), _unit(5)]
    estimate = estimate_spending(units)
    assert estimate.unit_count == 3
    assert estimate.token_count == 40


def test_estimate_spending_sur_une_liste_vide():
    estimate = estimate_spending([])
    assert estimate.unit_count == 0
    assert estimate.token_count == 0


def test_assert_within_cap_laisse_passer_sous_les_plafonds():
    estimate = estimate_spending([_unit(10), _unit(10)])
    assert_within_cap(estimate, max_units=100, max_tokens=1000)  # ne lève rien


def test_assert_within_cap_laisse_passer_exactement_au_plafond():
    estimate = estimate_spending([_unit(10), _unit(10)])
    assert_within_cap(estimate, max_units=2, max_tokens=20)  # pile au plafond


def test_assert_within_cap_leve_si_trop_d_unites():
    estimate = estimate_spending([_unit(10), _unit(10), _unit(10)])
    with pytest.raises(SpendingCapExceeded):
        assert_within_cap(estimate, max_units=2, max_tokens=1000)


def test_assert_within_cap_leve_si_trop_de_tokens():
    estimate = estimate_spending([_unit(500), _unit(500)])
    with pytest.raises(SpendingCapExceeded):
        assert_within_cap(estimate, max_units=100, max_tokens=999)


def test_mode_a_blanc_estime_sans_jamais_lever():
    # Le mode à blanc n'appelle que l'estimation, jamais la vérification —
    # il doit pouvoir chiffrer un dépassement sans planter.
    estimate = estimate_spending([_unit(10_000)])
    assert estimate.token_count == 10_000
