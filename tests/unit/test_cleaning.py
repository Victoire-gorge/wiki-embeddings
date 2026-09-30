import pytest

from app.domain.cleaning import strip_introductory_phrase


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
