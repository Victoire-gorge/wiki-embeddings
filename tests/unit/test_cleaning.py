import pytest

from app.domain.cleaning import clean_markup, strip_introductory_phrase


@pytest.mark.parametrize(
    "texte, attendu",
    [
        (
            "Dans cette vidéo, Alain Canet présente une plantation.",
            "Alain Canet présente une plantation.",
        ),
        (
            "dans cette conférence, l'agronome Calegari partage son expérience.",
            "l'agronome Calegari partage son expérience.",
        ),
        (
            "Lors de cette table ronde, chercheurs et praticiens échangent.",
            "chercheurs et praticiens échangent.",
        ),
        (
            "Dans cet épisode, nous abordons la gestion des couverts.",
            "nous abordons la gestion des couverts.",
        ),
    ],
)
def test_retire_la_locution_introductive(texte, attendu):
    assert strip_introductory_phrase(texte) == attendu


@pytest.mark.parametrize(
    "texte",
    [
        # Sans virgule : le nom est suivi d'un complément qui porte du contenu.
        # Retirer « Dans cet atelier » couperait au milieu d'un groupe nominal
        # pour ne gagner que trois mots — l'opération s'annule.
        "Dans cet atelier consacré à l'entretien du jardin, Marceau échange avec Guillaume.",
        "Lors de cette table ronde animée à la ferme de Marciac, les praticiens exposent.",
        # Locutions fréquentes en tête de résumé mais porteuses d'information :
        # un programme, un lieu. Les supprimer détruirait du contenu.
        "Dans le cadre du programme Ecophyto, les partenaires ont expérimenté.",
        "À la ferme de Xavier Moisière, les couverts sont détruits au rouleau.",
        # Le cas de loin le plus courant : une section d'article ordinaire.
        "Les engrais verts sont implantés après la récolte de céréales.",
    ],
)
def test_laisse_intact_ce_qui_porte_du_contenu(texte):
    assert strip_introductory_phrase(texte) == texte


def test_ne_retire_qu_une_seule_occurrence():
    texte = "Dans cette vidéo, dans cette vidéo, le propos est répété."
    assert strip_introductory_phrase(texte) == "dans cette vidéo, le propos est répété."


def test_clean_markup_garde_le_texte_simple_intact():
    assert clean_markup("Les engrais verts sont implantés après récolte.") == (
        "Les engrais verts sont implantés après récolte."
    )


def test_clean_markup_retire_les_refs_avec_leur_contenu():
    texte = "Le rendement varie selon la parcelle<ref>Source : étude X</ref>."
    assert clean_markup(texte) == "Le rendement varie selon la parcelle."


def test_clean_markup_retire_les_refs_nommees_et_les_rappels():
    texte = 'Plusieurs sources<ref name="x">Étude A</ref> confirment<ref name="x" /> l\'effet.'
    assert clean_markup(texte) == "Plusieurs sources confirment l'effet."


def test_clean_markup_retire_les_liens_de_categorisation_invisibles():
    # [[Category:X]] sans ":" initial ne s'affiche jamais sur la page rendue —
    # seulement dans le bandeau de catégories, pas dans le texte.
    texte = "voir aussi [[Category:Anthracnose]]"
    assert clean_markup(texte) == "voir aussi"


def test_clean_markup_retire_les_liens_interlangues():
    texte = "Fin de l'article.\n[[en:Some article title]]"
    assert clean_markup(texte) == "Fin de l'article."


def test_clean_markup_garde_les_liens_de_categorie_avec_deux_points_et_alias():
    # [[:Catégorie:X|alias]], AVEC le ":" initial, est un lien de renvoi
    # normal et visible — le ":" initial est ce qui distingue les deux cas.
    texte = "un ravageur du [[:Catégorie:Chêne|chêne]] commun"
    assert clean_markup(texte) == "un ravageur du chêne commun"


def test_clean_markup_garde_le_texte_des_liens_normaux():
    texte = "La conduite de la [[vigne]] est une méthode."
    assert clean_markup(texte) == "La conduite de la vigne est une méthode."


def test_clean_markup_retire_le_formatage_gras_et_italique():
    texte = "'''Période de mise en œuvre''' et ''texte en italique''."
    assert clean_markup(texte) == "Période de mise en œuvre et texte en italique."


def test_clean_markup_retire_les_templates():
    texte = "{{Pages liées}}\n{{#set: Import GECO le = 01/02/2021}}"
    assert clean_markup(texte) == ""


def test_clean_markup_ne_fusionne_pas_les_paragraphes():
    texte = "Premier paragraphe.\n\nDeuxième paragraphe."
    assert clean_markup(texte) == "Premier paragraphe.\n\nDeuxième paragraphe."


def test_clean_markup_ne_laisse_pas_de_double_espace_apres_un_retrait():
    texte = "présence de [[Catégorie:Vigne]] dans la région"
    assert clean_markup(texte) == "présence de dans la région"


def test_clean_markup_retire_le_residu_de_lien_categorie_sans_crochets():
    # Un défaut d'édition/import, pas un lien valide : pas de "[[" du tout,
    # donc invisible pour strip_code() — mesuré hors des seules transcriptions
    # (1016 pages sur 3089), c'est un problème général de markup mal formé.
    texte = "avec du :Catégorie:Chêne|chêne avec de l'érable avec du :Catégorie:Platane|platane"
    assert clean_markup(texte) == "avec du chêne avec de l'érable avec du platane"


def test_clean_markup_garde_un_vrai_lien_categorie_sans_alias():
    # [[:Catégorie:Gestion des ravageurs]] (avec ":", sans alias) est un lien
    # visible normal — ce n'est pas le même cas que le résidu sans crochets
    # ci-dessus. strip_code() garde le ":" initial tel quel.
    texte = "sur la [[:Catégorie:Gestion des ravageurs]]"
    assert clean_markup(texte) == "sur la :Catégorie:Gestion des ravageurs"
