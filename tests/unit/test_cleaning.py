import pytest

from app.domain.cleaning import (
    clean_markup,
    collapse_repeated_phrases,
    strip_chart_blocks,
    strip_introductory_phrase,
    strip_reporting_frame,
    strip_urls,
)


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
        "Dans cet atelier consacré à l'entretien du jardin, Marceau échange avec "
        "Guillaume.",
        "Lors de cette table ronde animée à la ferme de Marciac, les praticiens "
        "exposent.",
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
    texte = (
        'Plusieurs sources<ref name="x">Étude A</ref> confirment<ref name="x" /> '
        "l'effet."
    )
    assert clean_markup(texte) == "Plusieurs sources confirment l'effet."


def test_clean_markup_retire_les_liens_de_categorisation_invisibles():
    # [[Category:X]] sans ":" initial ne s'affiche jamais sur la page rendue —
    # seulement dans le bandeau de catégories, pas dans le texte.
    texte = "voir aussi [[Category:Anthracnose]]"
    assert clean_markup(texte) == "voir aussi"


def test_clean_markup_retire_les_liens_interlangues():
    texte = "Fin de l'article.\n[[en:Some article title]]"
    assert clean_markup(texte) == "Fin de l'article."


def test_clean_markup_retire_une_image_sans_parametre():
    # [[Image:X]] nu : juste un nom de fichier, jamais une légende écrite par
    # un humain — pas d'information à garder, même nettoyé des "_".
    texte = "Voir [[Image:Schema.png]] ci-dessous."
    assert clean_markup(texte) == "Voir ci-dessous."


def test_clean_markup_retire_une_image_sans_legende():
    # Mesuré : 10 % des liens image avec paramètres n'ont que des mots-clés
    # de mise en page (position, taille), aucune légende — pur bruit.
    texte = "Voir [[Fichier:Schema.png|vignette|300px]] ci-dessous."
    assert clean_markup(texte) == "Voir ci-dessous."


def test_clean_markup_garde_la_legende_d_une_image():
    # Mesuré : 90 % des liens image avec paramètres ont une vraie légende,
    # noyée dans les mots-clés de mise en page — à en extraire, pas à jeter.
    texte = "[[Fichier:Faucon.jpg|vignette|droite|Faucon crécerelle]]"
    assert clean_markup(texte) == "Faucon crécerelle"


def test_clean_markup_nettoie_le_markup_a_l_interieur_d_une_legende():
    texte = (
        "[[Fichier:Fabaceae.jpg|vignette|Évolution des feuilles chez les "
        "''Fabaceae''.]]"
    )
    assert clean_markup(texte) == "Évolution des feuilles chez les Fabaceae."


def test_clean_markup_reconnait_image_fichier_et_file():
    for prefixe in ("Image", "Fichier", "File"):
        texte = f"[[{prefixe}:x.jpg|vignette|Légende commune]]"
        assert clean_markup(texte) == "Légende commune"


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
    texte = (
        "avec du :Catégorie:Chêne|chêne avec de l'érable avec du "
        ":Catégorie:Platane|platane"
    )
    assert clean_markup(texte) == "avec du chêne avec de l'érable avec du platane"


def test_clean_markup_garde_un_vrai_lien_categorie_sans_alias():
    # [[:Catégorie:Gestion des ravageurs]] (avec ":", sans alias) est un lien
    # visible normal — ce n'est pas le même cas que le résidu sans crochets
    # ci-dessus. strip_code() garde le ":" initial tel quel.
    texte = "sur la [[:Catégorie:Gestion des ravageurs]]"
    assert clean_markup(texte) == "sur la :Catégorie:Gestion des ravageurs"


def test_strip_urls_retire_une_url_en_milieu_de_texte():
    texte = "Voir https://example.com/page pour plus d'infos."
    assert strip_urls(texte) == "Voir pour plus d'infos."


def test_strip_urls_retire_les_parentheses_qui_ne_contenaient_que_l_url():
    # Une parenthèse vide une fois l'URL retirée ne porte aucune information.
    texte = "Cette étude (https://example.com/etude) confirme les résultats."
    assert strip_urls(texte) == "Cette étude confirme les résultats."


def test_strip_urls_garde_la_parenthese_si_autre_chose_y_figure():
    # Ici la parenthèse contient aussi "voir " : elle reste, seule l'URL part.
    texte = "Cette étude (voir https://example.com/etude) confirme les résultats."
    assert strip_urls(texte) == "Cette étude (voir ) confirme les résultats."


def test_strip_urls_retire_plusieurs_urls():
    texte = "Deux sources : https://a.example.com et https://b.example.com/page."
    assert strip_urls(texte) == "Deux sources : et ."


def test_strip_urls_laisse_intact_un_texte_sans_url():
    texte = "Les engrais verts sont implantés après récolte."
    assert strip_urls(texte) == texte


def test_clean_markup_retire_aussi_les_urls():
    texte = "Pour en savoir plus : https://example.com/etude."
    assert clean_markup(texte) == "Pour en savoir plus : ."


def test_strip_chart_blocks_retire_un_bloc_echarts_avec_json_imbrique():
    # {{#echarts: ... }} n'est jamais reconnu comme template par
    # mwparserfromhell (0 détecté, mesuré) — strip_code() le laisse donc
    # passer tel quel. Le JSON interne contient de nombreuses accolades non
    # appariées pour un couple {{ }} : un simple ".*?}}" non gourmand s'arrête
    # à la première fermeture d'objet JSON, bien avant la vraie fin du bloc.
    texte = (
        "Avant.\n"
        "{{#echarts:\n  title=Rotation\n| option = "
        '{"tooltip":{},"series":[{"type":"pie","data":['
        '{"name":"a","value":1},{"name":"b","value":2}]}]}'
        "\n}}\n"
        "Après."
    )
    assert strip_chart_blocks(texte) == "Avant.\n\nAprès."


def test_strip_chart_blocks_laisse_intact_un_texte_sans_graphique():
    texte = "Les engrais verts sont implantés après récolte."
    assert strip_chart_blocks(texte) == texte


def test_clean_markup_retire_aussi_les_blocs_de_graphique():
    texte = (
        "Avant.\n"
        '{{#echarts:\n| option = {"series":[{"data":[{"name":"a"}]}]}\n}}\n'
        "Après."
    )
    assert clean_markup(texte) == "Avant.\n\nAprès."


def test_collapse_repeated_phrases_garde_le_texte_sans_repetition_intact():
    texte = "bonjour tout le monde alors au programme de cette vidéo"
    assert collapse_repeated_phrases(texte) == texte


def test_collapse_repeated_phrases_retire_un_mot_repete():
    # L'effet de fenêtre glissante du sous-titrage automatique répète parfois
    # un seul mot plusieurs fois de suite (interjection, ou un marqueur non
    # verbal comme [Musique]).
    texte = "bonjour bonjour bonjour au programme"
    assert collapse_repeated_phrases(texte) == "bonjour au programme"


def test_collapse_repeated_phrases_retire_une_phrase_repetee():
    texte = (
        "au programme de cette vidéo je vais au programme de cette vidéo je vais "
        "vous montrer"
    )
    assert collapse_repeated_phrases(texte) == (
        "au programme de cette vidéo je vais vous montrer"
    )


def test_collapse_repeated_phrases_converge_au_dela_de_deux_repetitions():
    # Bug trouvé en explorant : une seule passe ne fait que diviser par deux
    # le nombre d'occurrences d'un bloc répété plus de deux fois (10 "x" ->
    # 5, pas 1). Il faut itérer jusqu'à ce que le texte ne change plus.
    texte = " ".join(["musique"] * 10)
    assert collapse_repeated_phrases(texte) == "musique"


def test_collapse_repeated_phrases_sur_une_transcription_tres_longue_ne_bloque_pas():
    # Les transcriptions vidéo de ce wiki vont jusqu'à ~200 000 mots — un
    # garde-fou de performance, pas un comportement fonctionnel à vérifier.
    texte = " ".join(["le chat mange la souris"] * 20000)
    resultat = collapse_repeated_phrases(texte)
    assert resultat == "le chat mange la souris"


@pytest.mark.parametrize(
    "texte, attendu",
    [
        (
            "Il est rappelé que le climat est un assemblage de microclimats.",
            "le climat est un assemblage de microclimats.",
        ),
        (
            "Il est souligné que l'on coupe parfois des arbres.",
            "l'on coupe parfois des arbres.",
        ),
        (
            # Apostrophe d'élision ("qu'") devant une voyelle, pas "que ".
            "Il est rappelé qu'on manque d'arbres dans les territoires agricoles.",
            "on manque d'arbres dans les territoires agricoles.",
        ),
        (
            # Pas en tête de phrase : la locution reste retirée où qu'elle soit,
            # contrairement à strip_introductory_phrase qui n'agit qu'en tête.
            "En fin de débat, il est rappelé que chacun peut agir à son niveau.",
            "En fin de débat, chacun peut agir à son niveau.",
        ),
        (
            "Il est indiqué qu'environ 108 grammes sont de l'eau nouvelle.",
            "environ 108 grammes sont de l'eau nouvelle.",
        ),
    ],
)
def test_strip_reporting_frame_retire_la_tournure_de_rapport(texte, attendu):
    assert strip_reporting_frame(texte) == attendu


def test_strip_reporting_frame_retire_toutes_les_occurrences():
    # Contrairement à strip_introductory_phrase (une seule fois, en tête),
    # cette tournure revient plusieurs fois dans un même résumé long.
    texte = "Il est rappelé que X. Plus loin, il est précisé que Y."
    assert strip_reporting_frame(texte) == "X. Plus loin, Y."


@pytest.mark.parametrize(
    "texte",
    [
        # Tournures modales : portent un vrai sens (possibilité, nécessité,
        # importance), pas une méta-commentaire sur la source. À ne pas toucher.
        "Il est possible de réduire les coûts de production.",
        "Il est essentiel de bien préparer le sol avant le semis.",
        "Il est nécessaire d'attendre la bonne fenêtre météo.",
        "Il est important de respecter la rotation des cultures.",
    ],
)
def test_strip_reporting_frame_laisse_intactes_les_tournures_modales(texte):
    assert strip_reporting_frame(texte) == texte
