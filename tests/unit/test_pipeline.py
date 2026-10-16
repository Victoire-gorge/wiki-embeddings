from app.domain.pipeline import construire_unites_page


def _compte_mots(texte: str) -> int:
    """Compteur trivial pour les tests : un mot = un token."""
    return len(texte.split())


def test_construire_unites_page_renumerote_a_l_echelle_de_la_page():
    wikitext = (
        "== Un ==\nPremière section avec du texte dedans.\n\n"
        "== Deux ==\nDeuxième section ici aussi présente."
    )
    unites = construire_unites_page(
        wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
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
        wikitext, cible=6, plancher=1, compte_tokens=_compte_mots
    )
    assert len(unites) > 2
    assert [u.unit_index for u in unites] == list(range(len(unites)))
    assert unites[-1].heading == "Courte"


def test_construire_unites_page_rend_rien_pour_une_page_json():
    wikitext = '{"title": "Rotation", "series": [{"name": "a", "value": 1}]}'
    unites = construire_unites_page(
        wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert unites == []


def test_construire_unites_page_integre_les_champs_video():
    wikitext = "{{Vidéo\n| Résumé = Un résumé court à propos de légumes.\n}}"
    unites = construire_unites_page(
        wikitext, cible=20, plancher=1, compte_tokens=_compte_mots
    )
    assert any(u.heading == "Résumé court" for u in unites)


def test_construire_unites_page_rend_rien_pour_une_page_vide():
    assert (
        construire_unites_page("", cible=20, plancher=1, compte_tokens=_compte_mots)
        == []
    )
