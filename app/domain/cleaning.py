"""Nettoyage du texte des unités — transformations pures.

Comme `units.py`, ce module ne lit ni n'écrit rien : il prend du texte et en
renvoie. Il intervient après le découpage structurel et après le nettoyage du
markup, sur du texte déjà normalisé.
"""

from __future__ import annotations

import re

import mwparserfromhell

# Liens wiki invisibles sur la page rendue, à ne jamais garder comme texte :
#   - catégorisation, [[Category:X]] / [[Catégorie:X]] sans ":" initial ;
#   - interlangue, [[en:Titre]] — codes à 2-3 lettres mesurés sur ce wiki :
#     en, de, es, nl, it, pl, hu, pt, fi, el, ar (aucun ne collisionne avec un
#     namespace réel, qui sont tous des mots complets ici : Catégorie, Modèle...).
# Le ":" initial est ce qui distingue ce cas d'un lien de renvoi normal et
# visible, [[:Catégorie:X|alias]], que strip_code() doit garder.
_LIEN_INVISIBLE = re.compile(r"^(cat[ée]gorie|category):|^[a-z]{2,3}:", re.IGNORECASE)

# Résidu d'un lien de catégorie dont les crochets ont été oubliés à l'édition
# ou à l'import : ":Catégorie:Chêne|chêne" en texte brut, pas un nœud wiki
# (pas de "[[" du tout), donc invisible pour mwparserfromhell — strip_code()
# ne peut rien y faire. Mesuré sur 3089 pages, dont 1016 hors d'un template
# Transcription : un problème général de markup mal formé, pas un artefact
# propre aux transcriptions.
_RESIDU_CATEGORIE_SANS_CROCHETS = re.compile(r":?[Cc]at[ée]gorie:[^\s|]+\|")

# Locutions introductives repérées sur le corpus Triple Performance, dans les
# résumés de pages vidéo : « Dans cette conférence, … », « Lors de cette table
# ronde, … ». Elles ouvrent près de la moitié des résumés et ne portent aucune
# information — le format de l'intervention est une métadonnée, pas du contenu.
#
# La virgule finale est OBLIGATOIRE, et c'est le point important. Elle marque la
# fin de la locution : sans elle, ce qui suit le nom lui est rattaché et relève
# du contenu.
#
#     « Dans cette conférence, l'agronome Calegari partage… »
#        └─ ferraille ────────┘ la règle s'applique, gain net
#
#     « Dans cet atelier consacré à l'entretien du jardin, Marceau échange… »
#        └─ ferraille ───┘└─ contenu ──────────────────────┘
#        la règle ne s'applique pas : retirer trois mots de bruit en coupant au
#        milieu d'un groupe nominal ne gagne rien
#
# Mesuré sur 1 398 résumés : 42 % nettoyés avec la virgule obligatoire, 56 % sans
# — les 186 de différence étant précisément les cas sans bénéfice.
_LOCUTION_INTRODUCTIVE = re.compile(
    r"^\s*(?:dans|lors de|au cours de|à l'occasion de)\s+"
    r"(?:cette?|ce|cet|la|le)\s+"
    r"(?:vidéo|conférence|intervention|présentation|webinaire|épisode"
    r"|atelier|entretien|extrait|échange|table ronde|visite|émission)"
    r"\s*,\s*",
    re.IGNORECASE,
)


def strip_introductory_phrase(text: str) -> str:
    """Retire une locution introductive en tête de texte, si elle s'y trouve.

    Renvoie le texte inchangé quand aucune locution n'est reconnue — ce qui est
    le cas de la quasi-totalité des sections d'articles. La règle est générique
    et s'applique à toute unité : elle n'est pas conditionnée au type de page.

    Attention à l'ordre : la normalisation typographique doit précéder cet appel,
    sinon une apostrophe courbe dans « à l'occasion » ou un « é » décomposé en
    Unicode feront échouer la reconnaissance sans erreur visible.
    """
    return _LOCUTION_INTRODUCTIVE.sub("", text, count=1)


def clean_markup(wikitext: str) -> str:
    """Convertit du wikitext (hors tableaux, déjà extraits ailleurs) en texte.

    Trois retraits, tous mesurés sur ce wiki — deux avant `strip_code()`, un
    après :

    - les balises `<ref>` : `strip_code()` garde leur contenu et le soude au
      mot précédent sans espace ("la parcelleSource : étude X") — une
      citation n'est de toute façon pas la prose de la section ;
    - les liens wiki invisibles sur la page rendue (catégorisation,
      interlangue) : `strip_code()` ne sait pas qu'ils sont invisibles et en
      affiche le titre comme texte ("Category:Anthracnose") ;
    - après `strip_code()`, le résidu d'un lien de catégorie dont les crochets
      ont été oubliés (":Catégorie:Chêne|chêne") : ce n'est pas un nœud wiki,
      donc invisible pour les deux retraits précédents.

    Les templates restent gérés par `strip_code()` seul : mesuré sur ce wiki,
    ceux qui apparaissent dans le corps d'une section (hors lead/infobox) sont
    structurels (`{{Pages liées}}`, `{{#set:}}`...), jamais porteurs de prose.
    """
    code = mwparserfromhell.parse(wikitext)

    for tag in code.filter_tags(matches=lambda t: t.tag.lower() == "ref"):
        code.remove(tag)

    for link in code.filter_wikilinks():
        title = str(link.title).strip()
        if not title.startswith(":") and _LIEN_INVISIBLE.match(title):
            code.remove(link)

    text = code.strip_code()
    text = _RESIDU_CATEGORIE_SANS_CROCHETS.sub("", text)
    # Espaces/tabulations en double laissés par un nœud retiré — pas les
    # sauts de ligne, qui séparent des paragraphes et doivent rester.
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def _collapse_once(mots: list[str], fenetre_max: int) -> list[str]:
    """Une seule passe : replie un bloc de mots immédiatement suivi de lui-même."""
    sortie: list[str] = []
    i = 0
    while i < len(mots):
        for n in range(min(fenetre_max, (len(mots) - i) // 2), 0, -1):
            if mots[i:i + n] == mots[i + n:i + 2 * n]:
                sortie.extend(mots[i:i + n])
                i += 2 * n
                break
        else:
            sortie.append(mots[i])
            i += 1
    return sortie


def collapse_repeated_phrases(text: str, fenetre_max: int = 12, max_iter: int = 20) -> str:
    """Replie les répétitions immédiates de mots ou de groupes de mots.

    Le sous-titrage automatique (YouTube) défile par fenêtre glissante : un
    même segment de parole réapparaît souvent deux à trois fois de suite dans
    la transcription brute. Pas un problème de markup — un artefact propre à
    la reconnaissance vocale automatique, donc une fonction à part de
    `clean_markup`, à n'appliquer qu'aux transcriptions.

    Une seule passe ne suffit pas : elle ne divise que par deux le nombre
    d'occurrences d'un bloc répété plus de deux fois (10 répétitions de "x"
    deviennent 5, pas 1), puisqu'elle compare chaque bloc à la copie qui le
    suit immédiatement sans revérifier le résultat. Itérer jusqu'à ce que le
    texte ne change plus fait converger vers une seule occurrence.
    """
    mots = text.split()
    for _ in range(max_iter):
        nouveau = _collapse_once(mots, fenetre_max)
        if nouveau == mots:
            break
        mots = nouveau
    return " ".join(mots)
