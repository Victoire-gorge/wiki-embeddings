from app.domain.construction_unites import construire_unites_page


def _compte_mots(texte: str) -> int:
    """Compteur trivial pour les tests : un mot = un token."""
    return len(texte.split())


def test_construire_unites_page_renumerote_a_l_echelle_de_la_page():
    wikitext = (
        "== Un ==\nPremière section avec du texte dedans.\n\n"
        "== Deux ==\nDeuxième section ici aussi présente."
    )
    unites = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert len(unites) == 2
    assert [u.unit_index for u in unites] == [0, 1]
    assert unites[0].heading == "Un"
    assert unites[1].heading == "Deux"


def test_construire_unites_page_continue_la_numerotation_apres_une_scission():
    # La première section se scinde en plusieurs Unit : la seconde section
    # doit reprendre la numérotation là où la première l'a laissée, pas
    # repartir de zéro — construire_unites ne voit qu'une section à la fois
    # et ne peut pas le garantir elle-même.
    wikitext = (
        "== Longue ==\n" + " ".join(["mot"] * 20) + "\n\n"
        "== Courte ==\nUne petite section après celle-ci."
    )
    unites = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=6, plancher=1, compte_tokens=_compte_mots
    )
    assert len(unites) > 2
    assert [u.unit_index for u in unites] == list(range(len(unites)))
    assert unites[-1].heading == "Courte"


def test_construire_unites_page_rend_rien_pour_une_page_json():
    wikitext = '{"title": "Rotation", "series": [{"name": "a", "value": 1}]}'
    unites = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert unites == []


def test_construire_unites_page_integre_les_champs_video():
    wikitext = "{{Vidéo\n| Résumé = Un résumé court à propos de légumes.\n}}"
    unites = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert any(u.heading == "Résumé court" for u in unites)


def test_construire_unites_page_rend_rien_pour_une_page_vide():
    unites = construire_unites_page(
        page_id=1, wikitext="", cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert unites == []


def test_construire_unites_page_porte_le_page_id():
    wikitext = "== Un ==\nUne section avec du texte dedans."
    unites = construire_unites_page(
        page_id=42, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert unites[0].page_id == 42


def test_construire_unites_page_calcule_un_unit_id_deterministe():
    wikitext = "== Un ==\nUne section avec du texte dedans."
    a = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    b = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert a[0].unit_id == b[0].unit_id


def test_construire_unites_page_distingue_deux_pages_au_contenu_identique():
    # unit_id dépend de page_id, pas seulement du contenu : page_id est
    # l'identité stable d'une page, content_hash celle d'un contenu — deux
    # pages différentes avec exactement le même texte restent deux unit_id
    # distincts (CLAUDE.md : "Deux stratégies d'identité opposées").
    wikitext = "== Un ==\nUne section avec du texte dedans."
    a = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    b = construire_unites_page(
        page_id=2, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert a[0].content_hash == b[0].content_hash
    assert a[0].unit_id != b[0].unit_id


def test_construire_unites_page_distingue_un_contenu_duplique_dans_la_meme_page():
    # Deux sections rigoureusement identiques dans la même page : occurrence
    # est exactement fait pour ce cas, le seul rôle documenté du rang
    # d'occurrence dans unit_id.
    # Même titre, même corps : seul moyen d'obtenir deux Unit dont le texte
    # (donc le content_hash) est rigoureusement identique, puisque le titre
    # fait partie du texte vectorisé.
    wikitext = (
        "== Un ==\nLe texte est rigoureusement identique ici.\n\n"
        "== Un ==\nLe texte est rigoureusement identique ici."
    )
    unites = construire_unites_page(
        page_id=1, wikitext=wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert len(unites) == 2
    assert unites[0].content_hash == unites[1].content_hash
    assert unites[0].unit_id != unites[1].unit_id
