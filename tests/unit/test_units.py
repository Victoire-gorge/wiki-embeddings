from pathlib import Path

from app.domain.units import (
    atomiser,
    construire_unites,
    est_page_json,
    extract_tables,
    remplir,
    splice_video_fields,
    split_into_sections,
)


def _compte_mots(texte: str) -> int:
    """Compteur trivial pour les tests : un mot = un token — pas besoin de
    tiktoken pour tester une cascade de découpage, seul le comptage change."""
    return len(texte.split())

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
    wikitext = (FIXTURES / "systeme_conduite_vigne.wikitext").read_text(
        encoding="utf-8"
    )
    sections = split_into_sections(wikitext)

    # 1 section de tête (les deux templates d'infobox) + 21 titres du fixture.
    assert len(sections) == 22
    assert sections[0].heading is None
    assert "Pratique" in sections[0].wikitext

    # Le titre inclut le fil des ancêtres : la vraie prose est au niveau 3,
    # imbriquée sous deux titres vides de texte mais porteurs de contexte.
    described = next(
        s for s in sections
        if s.heading == (
            "1. Présentation > Caractérisation de la technique > "
            "Description de la technique :"
        )
    )
    assert "conduite de la [[vigne]]" in described.wikitext

    # Beaucoup de sections de ce wiki sont des coquilles vides (juste un
    # titre et un séparateur "----") : la fonction ne doit pas les filtrer,
    # ça revient à l'étape de nettoyage / fusion, pas au découpage.
    empty_shell = next(
        s for s in sections
        if s.heading == "1. Présentation > Caractérisation de la technique"
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
    wikitext = (
        "== Avant ==\ntexte avant\n{|\n!Nom\n|-\n|Dumoulin\n|}\n"
        "== Après ==\ntexte après"
    )
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
    wikitext = (
        "{{Vidéo\n| Producteur = X\n}}\n"
        "{{Transcription\n|transcription=texte transcrit ici\n}}"
    )
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
        "|Résumé=== Introduction ==\nTexte d'intro.\n== Témoignage ==\n"
        "Texte du témoignage.\n"
        "}}"
    )
    spliced = splice_video_fields(wikitext)
    sections = split_into_sections(spliced)

    # "Résumé long" est injecté à un niveau de titre moins profond que ses
    # propres sous-titres (mesuré sur une vraie page : jusqu'à 3 niveaux
    # d'imbrication) — sinon le fil d'ancêtres générique les traiterait comme
    # des frères, et chaque unité perdrait tout lien vers "Résumé long".
    headings = [s.heading for s in sections]
    assert "Résumé long > Introduction" in headings
    assert "Résumé long > Témoignage" in headings


def test_splice_video_fields_garde_resume_court_et_transcription_frères():
    # Les sous-titres internes du résumé long ne doivent pas faire déborder
    # leur imbrication sur les sections voisines : Résumé court et
    # Transcription restent des frères propres, jamais des enfants l'un de
    # l'autre ni de Résumé long.
    wikitext = (
        "{{Vidéo\n| Résumé = Résumé court.\n}}\n"
        "{{Résumé long\n|Résumé=== Introduction ==\nTexte.\n}}\n"
        "{{Transcription\n|transcription=texte transcrit\n}}"
    )
    spliced = splice_video_fields(wikitext)
    sections = split_into_sections(spliced)

    headings = [s.heading for s in sections]
    assert "Résumé court" in headings
    assert "Transcription" in headings


def test_extract_tables_on_real_article_sample():
    wikitext = (FIXTURES / "systeme_conduite_vigne.wikitext").read_text(
        encoding="utf-8"
    )
    remaining, tables = extract_tables(wikitext)

    # Les 6 sections "Bioagresseurs/Auxiliaires/Accidents ... favorisés/défavorisés"
    # du fixture contiennent chacune exactement un tableau, toutes coquilles vides.
    assert len(tables) == 6
    assert "{|" not in remaining

    sections = split_into_sections(remaining)
    now_empty = next(
        s for s in sections
        if s.heading == (
            "4. Organismes favorisés ou défavorisés > "
            "[[Bioagresseurs]] favorisés"
        )
    )
    assert now_empty.wikitext == ""


def test_est_page_json_reconnait_un_wikitext_qui_est_du_json_valide():
    # Mesuré sur ce wiki : 317 pages (3,3 % du corpus) dont tout le contenu
    # est un JSON de configuration de graphique, pas du wikitexte — des
    # pages de données, jamais de la prose. Le titre finissant par ".json"
    # ne suffit pas : 2 de ces 317 pages n'ont pas ce suffixe, le contenu
    # lui-même est le seul signal fiable à 100 %.
    wikitext = '{"title": "Rotation", "series": [{"name": "a", "value": 1}]}'
    assert est_page_json(wikitext) is True


def test_est_page_json_rejette_du_wikitexte_normal():
    wikitext = "== Titre ==\nLes engrais verts sont implantés après récolte."
    assert est_page_json(wikitext) is False


def test_est_page_json_rejette_du_wikitexte_qui_contient_juste_des_accolades():
    # {{Pages liées}} n'est pas un objet JSON : json.loads doit échouer, pas
    # confondre un template wiki avec un objet.
    wikitext = "{{Pages liées}}"
    assert est_page_json(wikitext) is False


def test_atomiser_garde_un_texte_court_intact():
    texte = "Les engrais verts sont implantés après récolte."
    assert atomiser(texte, cible=20, compte_tokens=_compte_mots) == [texte]


def test_atomiser_coupe_par_paragraphe_quand_necessaire():
    texte = "Premier paragraphe court.\n\nDeuxième paragraphe aussi court."
    atomes = atomiser(texte, cible=4, compte_tokens=_compte_mots)
    assert atomes == ["Premier paragraphe court.", "Deuxième paragraphe aussi court."]


def test_atomiser_descend_aux_phrases_si_le_paragraphe_depasse():
    texte = "Première phrase courte. Deuxième phrase courte aussi. Troisième phrase."
    atomes = atomiser(texte, cible=4, compte_tokens=_compte_mots)
    assert atomes == [
        "Première phrase courte.",
        "Deuxième phrase courte aussi.",
        "Troisième phrase.",
    ]


def test_atomiser_tombe_sur_la_coupe_equilibree_sans_ponctuation():
    # Le cas transcription : ni ligne vide, ni ponctuation forte.
    texte = " ".join(["mot"] * 20)
    atomes = atomiser(texte, cible=6, compte_tokens=_compte_mots)
    assert len(atomes) == 4  # ceil(20 / 6)
    assert all(_compte_mots(a) <= 6 for a in atomes)


def test_atomiser_rejette_les_paragraphes_vides():
    # cible=3 force la cascade : à cible=10, les 4 mots du texte entier
    # rentreraient déjà sans la déclencher, et le test ne prouverait rien.
    texte = "Premier paragraphe.\n\n\n\nDeuxième paragraphe."
    atomes = atomiser(texte, cible=3, compte_tokens=_compte_mots)
    assert atomes == ["Premier paragraphe.", "Deuxième paragraphe."]


def test_atomiser_ne_rend_rien_pour_un_texte_vide():
    assert atomiser("   ", cible=10, compte_tokens=_compte_mots) == []


def test_atomiser_ne_perd_et_ne_duplique_aucun_mot():
    # L'invariant le plus utile : la concaténation des atomes redonne le
    # texte d'origine, mot pour mot — il attrape à la fois la perte et la
    # duplication, contrairement à une simple vérification de tailles.
    texte = (
        "Premier paragraphe avec plusieurs phrases courtes. Une deuxième "
        "phrase ici pour faire bonne mesure.\n\n"
        "Second paragraphe plus long sans aucune ponctuation forte dedans "
        "qui va forcer une coupe equilibree a un moment ou un autre du "
        "texte puisque rien ne permet de le decouper autrement du tout"
    )
    atomes = atomiser(texte, cible=8, compte_tokens=_compte_mots)
    assert " ".join(" ".join(atomes).split()) == " ".join(texte.split())


def test_remplir_empile_des_atomes_tant_que_ca_rentre():
    atomes = ["un deux trois", "quatre cinq six", "sept huit neuf dix"]
    groupes = remplir(atomes, cible=6, plancher=1, compte_tokens=_compte_mots)
    assert groupes == ["un deux trois quatre cinq six", "sept huit neuf dix"]


def test_remplir_ferme_un_groupe_des_que_le_suivant_ne_rentre_plus():
    atomes = ["un deux trois quatre cinq", "six"]
    groupes = remplir(atomes, cible=5, plancher=1, compte_tokens=_compte_mots)
    assert groupes == ["un deux trois quatre cinq", "six"]


def test_remplir_recolle_la_queue_sous_le_plancher():
    # "six sept" (2 mots) tombe sous le plancher (3) une fois seul dans son
    # propre groupe : recollé au précédent, même si ça dépasse la cible.
    atomes = ["un deux trois quatre cinq", "six sept"]
    groupes = remplir(atomes, cible=5, plancher=3, compte_tokens=_compte_mots)
    assert groupes == ["un deux trois quatre cinq six sept"]


def test_remplir_ne_recolle_pas_si_la_queue_depasse_le_plancher():
    atomes = ["un deux trois quatre cinq", "six sept huit"]
    groupes = remplir(atomes, cible=5, plancher=3, compte_tokens=_compte_mots)
    assert groupes == ["un deux trois quatre cinq", "six sept huit"]


def test_remplir_recolle_un_groupe_de_tete_sous_le_plancher():
    # Trouvé sur le corpus réel ("Céréales > Principales variétés") : un
    # titre court suivi d'une première phrase courte peut former un premier
    # groupe isolé sous le plancher — pas seulement le dernier.
    atomes = ["titre court", "une phrase plus longue avec six mots exactement"]
    groupes = remplir(atomes, cible=6, plancher=3, compte_tokens=_compte_mots)
    assert groupes == ["titre court une phrase plus longue avec six mots exactement"]


def test_remplir_sur_un_seul_atome_le_rend_tel_quel():
    atomes = ["un seul atome ici"]
    groupes = remplir(atomes, cible=10, plancher=1, compte_tokens=_compte_mots)
    assert groupes == ["un seul atome ici"]


def test_remplir_ne_perd_et_ne_duplique_aucun_mot():
    atomes = ["un deux trois", "quatre cinq", "six sept huit neuf", "dix"]
    groupes = remplir(atomes, cible=4, plancher=2, compte_tokens=_compte_mots)
    assert " ".join(" ".join(groupes).split()) == " ".join(" ".join(atomes).split())


def test_construire_unites_rend_une_seule_unite_si_ca_tient():
    unites = construire_unites(
        heading="Titre",
        corps="Un corps de texte assez court.",
        cible=20,
        plancher=2,
        compte_tokens=_compte_mots,
    )
    assert len(unites) == 1
    assert unites[0].heading == "Titre"
    assert unites[0].text == "Titre\nUn corps de texte assez court."
    assert unites[0].unit_index == 0
    assert unites[0].token_count == _compte_mots(unites[0].text)


def test_construire_unites_sans_titre_ne_prefixe_rien():
    unites = construire_unites(
        heading=None,
        corps="Un texte sans titre associé.",
        cible=20,
        plancher=2,
        compte_tokens=_compte_mots,
    )
    assert unites[0].text == "Un texte sans titre associé."
    assert unites[0].heading is None


def test_construire_unites_rejette_un_corps_vide():
    unites = construire_unites(
        heading="Titre", corps="   ", cible=20, plancher=2, compte_tokens=_compte_mots
    )
    assert unites == []


def test_construire_unites_rejette_sous_le_plancher():
    unites = construire_unites(
        heading="T", corps="court", cible=20, plancher=5, compte_tokens=_compte_mots
    )
    assert unites == []


def test_construire_unites_repete_le_titre_dans_chaque_morceau():
    # Le titre est inclus dans le budget de la cible pour chaque morceau,
    # pas combiné une seule fois avant découpage — sinon les morceaux après
    # le premier perdraient tout contexte de section une fois vectorisés.
    unites = construire_unites(
        heading="Titre",
        corps=" ".join(["mot"] * 20),
        cible=8,
        plancher=2,
        compte_tokens=_compte_mots,
    )
    assert len(unites) > 1
    for i, unite in enumerate(unites):
        assert unite.heading == "Titre"
        assert unite.text.startswith("Titre\n")
        assert unite.unit_index == i
        assert unite.token_count <= 8 + 1  # tolérance : approximation par mots


def test_construire_unites_calcule_un_hash_deterministe_et_distinct():
    a = construire_unites(
        heading="T", corps="Un corps.", cible=20, plancher=1, compte_tokens=_compte_mots
    )
    b = construire_unites(
        heading="T", corps="Un corps.", cible=20, plancher=1, compte_tokens=_compte_mots
    )
    c = construire_unites(
        heading="T",
        corps="Un autre corps.",
        cible=20,
        plancher=1,
        compte_tokens=_compte_mots,
    )
    assert a[0].content_hash == b[0].content_hash
    assert a[0].content_hash != c[0].content_hash
