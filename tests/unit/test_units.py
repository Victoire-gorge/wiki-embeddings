from pathlib import Path

from app.domain.units import extract_tables, splice_video_fields, split_into_sections

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
    # directement par un titre. Chaque titre inclut le fil de ses ancêtres :
    # Trois est imbriqué sous Deux, lui-même sous Un.
    headings = [s.heading for s in sections]
    assert headings == [None, "Un", "Un > Deux", "Un > Deux > Trois"]


def test_heading_breadcrumb_resets_on_sibling():
    # Un nouveau titre de même niveau (ou moins profond) remplace son frère
    # précédent dans la pile plutôt que de s'accumuler dessus : C ne doit pas
    # hériter de B, qui n'est pas son ancêtre mais celui d'un autre rameau.
    wikitext = "== A ==\ncorps\n=== B ===\ncorps\n== C ==\ncorps"
    sections = split_into_sections(wikitext)

    headings = [s.heading for s in sections]
    assert headings == [None, "A", "A > B", "C"]


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

    # Le titre inclut le fil des ancêtres : la vraie prose est au niveau 3,
    # imbriquée sous deux titres vides de texte mais porteurs de contexte.
    described = next(
        s for s in sections
        if s.heading == "1. Présentation > Caractérisation de la technique > Description de la technique :"
    )
    assert "conduite de la [[vigne]]" in described.wikitext

    # Beaucoup de sections de ce wiki sont des coquilles vides (juste un
    # titre et un séparateur "----") : la fonction ne doit pas les filtrer,
    # ça revient à l'étape de nettoyage / fusion, pas au découpage.
    empty_shell = next(
        s for s in sections if s.heading == "1. Présentation > Caractérisation de la technique"
    )
    assert empty_shell.wikitext == ""


def test_extract_tables_returns_unchanged_text_when_no_table():
    wikitext = "== Titre ==\ntexte sans tableau"
    remaining, tables = extract_tables(wikitext)

    assert remaining == wikitext
    assert tables == []


def test_extract_tables_removes_table_from_text():
    wikitext = '== Titre ==\ntexte avant\n{|\n!Nom\n|-\n|Dumoulin\n|}\ntexte après'
    remaining, tables = extract_tables(wikitext)

    assert "{|" not in remaining
    assert "Dumoulin" not in remaining
    assert "texte avant" in remaining
    assert "texte après" in remaining
    assert len(tables) == 1
    assert "Dumoulin" in tables[0]


def test_extract_tables_does_not_disrupt_heading_detection():
    wikitext = "== Avant ==\ntexte avant\n{|\n!Nom\n|-\n|Dumoulin\n|}\n== Après ==\ntexte après"
    remaining, _ = extract_tables(wikitext)
    sections = split_into_sections(remaining)

    headings = [s.heading for s in sections]
    assert headings == [None, "Avant", "Après"]


def test_extract_tables_handles_nested_tables():
    # Rencontré sur une page réelle (un PDF importé tel quel) : un tableau
    # imbriqué dans une cellule. Retirer le tableau extérieur retire aussi
    # l'intérieur ; sans garde, la seconde tentative de retrait échoue avec
    # un ValueError (le nœud n'existe plus dans l'arbre).
    wikitext = (
        "== Titre ==\n"
        "{|\n! {|\n!Interne\n|}\n|}\n"
        "texte après"
    )
    remaining, tables = extract_tables(wikitext)

    assert "{|" not in remaining
    assert "texte après" in remaining
    assert len(tables) >= 1


def test_splice_video_fields_leaves_non_video_pages_unchanged():
    wikitext = "== Titre ==\ntexte normal, aucun rapport avec une vidéo"
    assert splice_video_fields(wikitext) == wikitext


def test_splice_video_fields_adds_resume_court_as_a_section():
    wikitext = "{{Vidéo\n| Résumé = Un résumé court.\n}}"
    spliced = splice_video_fields(wikitext)

    sections = split_into_sections(spliced)
    resume = next(s for s in sections if s.heading == "Résumé court")
    assert "Un résumé court." in resume.wikitext


def test_splice_video_fields_prefers_separate_resume_long_distinctly():
    # Décision actée : les deux résumés sont gardés, sous deux titres distincts —
    # le tri entre les deux se fera plus tard, par la mesure sur les embeddings.
    wikitext = (
        "{{Vidéo\n| Résumé = Résumé court ici.\n}}\n"
        "{{Résumé long\n|Résumé=Résumé long ici, plus détaillé.\n}}"
    )
    spliced = splice_video_fields(wikitext)
    sections = split_into_sections(spliced)

    court = next(s for s in sections if s.heading == "Résumé court")
    long_ = next(s for s in sections if s.heading == "Résumé long")
    assert "Résumé court ici." in court.wikitext
    assert "Résumé long ici" in long_.wikitext


def test_splice_video_fields_adds_transcription_as_a_section():
    # Un template Transcription n'existe jamais sans le template Vidéo qui
    # l'accompagne sur ce wiki — la garde de la fonction s'appuie dessus.
    wikitext = "{{Vidéo\n| Producteur = X\n}}\n{{Transcription\n|transcription=texte transcrit ici\n}}"
    spliced = splice_video_fields(wikitext)

    sections = split_into_sections(spliced)
    transcription = next(s for s in sections if s.heading == "Transcription")
    assert "texte transcrit ici" in transcription.wikitext


def test_splice_video_fields_keeps_prose_outside_templates():
    wikitext = (
        "{{Vidéo\n| Résumé = Résumé.\n}}\n"
        "Texte hors template, après l'infobox."
    )
    spliced = splice_video_fields(wikitext)

    assert "Texte hors template, après l'infobox." in spliced
    assert "{{Vidéo" not in spliced


def test_splice_video_fields_recovers_internal_headings_of_long_resume():
    # Le bénéfice attendu de l'option retenue : le résumé long a souvent ses
    # propres sous-titres, qui deviennent des unités à part une fois repassés
    # par split_into_sections — sans retravailler le découpage.
    # Trois "=" d'affilée dans le wikitext réel : le séparateur du paramètre,
    # puis l'ouverture "==" du titre lui-même — motif vérifié sur une vraie
    # page du corpus.
    wikitext = (
        "{{Vidéo\n| Producteur = X\n}}\n"
        "{{Résumé long\n"
        "|Résumé=== Introduction ==\nTexte d'intro.\n== Témoignage ==\nTexte du témoignage.\n"
        "}}"
    )
    spliced = splice_video_fields(wikitext)
    sections = split_into_sections(spliced)

    headings = [s.heading for s in sections]
    assert "Introduction" in headings
    assert "Témoignage" in headings


def test_extract_tables_on_real_article_sample():
    wikitext = (FIXTURES / "systeme_conduite_vigne.wikitext").read_text(encoding="utf-8")
    remaining, tables = extract_tables(wikitext)

    # Les 6 sections "Bioagresseurs/Auxiliaires/Accidents ... favorisés/défavorisés"
    # du fixture contiennent chacune exactement un tableau, toutes coquilles vides.
    assert len(tables) == 6
    assert "{|" not in remaining

    sections = split_into_sections(remaining)
    now_empty = next(
        s for s in sections
        if s.heading == "4. Organismes favorisés ou défavorisés > [[Bioagresseurs]] favorisés"
    )
    assert now_empty.wikitext == ""
