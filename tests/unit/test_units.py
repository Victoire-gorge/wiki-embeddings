from pathlib import Path

from app.domain.units import split_into_sections

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_lead_section_has_no_heading():
    wikitext = "{{Infobox}}\ntexte d'intro\n== Titre ==\ncorps"
    sections = split_into_sections(wikitext)

    assert sections[0].heading is None
    assert sections[0].unit_index == 0


def test_splits_on_headings_of_any_level():
    wikitext = "= Un =\ncorps 1\n== Deux ==\ncorps 2\n=== Trois ===\ncorps 3"
    sections = split_into_sections(wikitext)

    # index 0 = section de tête, vide ici puisque le wikitext commence
    # directement par un titre.
    headings = [s.heading for s in sections]
    assert headings == [None, "Un", "Deux", "Trois"]


def test_section_content_excludes_subsections():
    wikitext = "== Parent ==\ntexte parent\n=== Enfant ===\ntexte enfant"
    sections = split_into_sections(wikitext)

    parent = next(s for s in sections if s.heading == "Parent")
    assert "texte enfant" not in parent.wikitext
    assert "texte parent" in parent.wikitext


def test_heading_markup_is_not_cleaned_yet():
    # Le nettoyage du markup dans les titres est la responsabilité de
    # l'étape suivante : ici on garde le wikitext brut.
    wikitext = "== [[Bioagresseurs]] favorisés ==\ncorps"
    sections = split_into_sections(wikitext)

    assert sections[1].heading == "[[Bioagresseurs]] favorisés"


def test_real_article_sample():
    wikitext = (FIXTURES / "systeme_conduite_vigne.wikitext").read_text(encoding="utf-8")
    sections = split_into_sections(wikitext)

    # 1 section de tête (les deux templates d'infobox) + 21 titres du fixture.
    assert len(sections) == 22
    assert sections[0].heading is None
    assert "Pratique" in sections[0].wikitext

    described = next(s for s in sections if s.heading == "Description de la technique :")
    assert "conduite de la [[vigne]]" in described.wikitext

    # Beaucoup de sections de ce wiki sont des coquilles vides (juste un
    # titre et un séparateur "----") : la fonction ne doit pas les filtrer,
    # ça revient à l'étape de nettoyage / fusion, pas au découpage.
    empty_shell = next(s for s in sections if s.heading == "Caractérisation de la technique")
    assert empty_shell.wikitext == ""
