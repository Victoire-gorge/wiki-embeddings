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

# Tournure de rapport repérée dans les résumés longs générés pour les pages
# Vidéo : « Il est rappelé que… », « il est souligné que… ». Le contenu réel
# commence juste après — la tournure ne fait qu'habiller une reformulation du
# propos de la vidéo, elle ne porte aucune information en elle-même.
#
# Mesuré sur 1326 résumés longs : 47 % contiennent au moins une tournure
# "il est <verbe> que/de" (1234 occurrences), mais toutes ne se valent pas.
# Les verbes ci-dessous (rappelé, précisé, indiqué, expliqué, souligné,
# répondu, affirmé, dit) sont de purs verbes de rapport — 380 occurrences.
# Volontairement exclus : les tournures modales comme "il est possible",
# "il est essentiel", "il est nécessaire" (228, 44 et 28 occurrences) — elles
# expriment une possibilité ou une nécessité, c'est le message lui-même, pas
# un commentaire sur la source.
#
# Contrairement à `_LOCUTION_INTRODUCTIVE`, cette tournure n'est pas ancrée en
# tête de texte : elle revient à plusieurs endroits d'un même résumé long
# ("En fin de débat, il est rappelé que…"), d'où `count=0` (toutes les
# occurrences) dans `strip_reporting_frame`, plutôt que `count=1`.
_TOURNURE_DE_RAPPORT = re.compile(
    r"\bil (?:est|a été|avait été)\s+"
    r"(?:rappelé|précisé|indiqué|expliqué|souligné|répondu|affirmé|dit)\s+"
    r"(?:que\s+|qu[’\'])",
    re.IGNORECASE,
)


# URL nue (jamais un lien wiki [[...]], juste du texte brut laissé tel quel
# par strip_code()). Mesuré sur ce wiki : 13,0 % des pages en contiennent au
# moins une, mais ça ne représente que 0,166 % du volume total de tokens
# (sections non vides) — une URL ne porte pas de prose, mais le volume
# qu'elle occupe est trop faible pour biaiser sérieusement les mesures de
# taille de section. La vraie raison de la retirer n'est pas le volume :
# c'est le risque de faux positif au dédoublonnage (deux pages sans rapport
# qui citent la même source se retrouveraient avec une similarité gonflée
# par du texte qu'aucun des deux n'a réellement écrit).
_URL = re.compile(r"\(?https?://\S+")

# Mesuré : sur 14 984 URLs, seulement 22 sont précédées de "Source :" — les
# libellés qui reviennent le plus souvent sont en fait des noms propres
# informatifs ("PlantGrape", "INSTAGRAM", "Chaîne you tube MSV"...), pas du
# remplissage. Contrairement aux locutions introductives, aucun préfixe
# générique à retirer ici : pas de règle ajoutée.


def strip_urls(text: str) -> str:
    """Retire les URLs nues du texte, en gardant la ponctuation qui les suit.

    "\\S+" est glouton et avale toute ponctuation collée sans espace à la fin
    d'une URL ("...etude.") — on la restitue après coup, sinon la phrase perd
    sa virgule ou son point final.

    Exception : une parenthèse ouvrante collée juste avant l'URL ("(https://
    ...)") est retirée avec elle si l'URL en est l'unique contenu — une
    parenthèse vide ne porte aucune information. Si autre chose s'y trouve
    aussi ("(voir https://...)"), la parenthèse reste : seule l'URL part.
    """
    def retire(match: re.Match[str]) -> str:
        bloc = match.group(0)
        parenthese_ouvrante = bloc.startswith("(")
        if parenthese_ouvrante:
            bloc = bloc[1:]
        ponctuation = ""
        while bloc and bloc[-1] in ".,;:!?)\"'’»":
            ponctuation = bloc[-1] + ponctuation
            bloc = bloc[:-1]
        if parenthese_ouvrante and ponctuation.endswith(")"):
            ponctuation = ponctuation[:-1]
        return ponctuation

    texte = _URL.sub(retire, text)
    return re.sub(r"[ \t]+", " ", texte)


# Bloc de configuration de graphique {{#echarts: ... | option = {JSON} }}.
# mwparserfromhell ne le reconnaît jamais comme template (0 détecté sur les
# pages mesurées) — strip_code() le laisse donc passer intégralement comme
# texte brut. Mesuré sur 4 pages utilisant {{#echarts:}}, pure mise en forme
# de graphique (couleurs, position des étiquettes), jamais de prose : aucune
# perte démontrable à le retirer, et un vrai risque de faux positif si deux
# fermes différentes partagent le même modèle de graphique (JSON de mise en
# forme quasi identique indépendamment du contenu agricole réel).
_DEBUT_GRAPHIQUE = re.compile(r"\{\{#echarts:")


def strip_chart_blocks(text: str) -> str:
    """Retire les blocs `{{#echarts: ... }}`, JSON de configuration imbriqué compris.

    Un simple ".*?\\}\\}" non gourmand s'arrêterait à la première fermeture
    d'un objet JSON interne, bien avant la vraie fin du bloc : le JSON
    contient de nombreuses accolades qui n'ont rien à voir avec les deux
    accolades du gabarit. On compte donc chaque accolade individuelle
    jusqu'à ce que le compte revienne à zéro — une vraie correspondance de
    parenthésage, pas une expression régulière bornée.

    Limite connue : ce comptage ne comprend pas le JSON, il compte des
    caractères. Une accolade littérale à l'intérieur d'une chaîne JSON
    (non observée sur ce wiki, ces blocs étant générés par un outil, pas
    tapés à la main) ferait dévier le comptage.
    """
    morceaux = []
    i = 0
    while i < len(text):
        debut = _DEBUT_GRAPHIQUE.search(text, i)
        if not debut:
            morceaux.append(text[i:])
            break
        morceaux.append(text[i:debut.start()])

        profondeur = 0
        j = debut.start()
        while j < len(text):
            if text[j] == "{":
                profondeur += 1
            elif text[j] == "}":
                profondeur -= 1
                if profondeur == 0:
                    j += 1
                    break
            j += 1
        i = j
    return "".join(morceaux)


def strip_reporting_frame(text: str) -> str:
    """Retire les tournures de rapport (« il est rappelé que… ») du texte.

    Garde intactes les tournures modales (« il est possible de… ») : elles
    portent un vrai sens, contrairement aux verbes de rapport qui signalent
    seulement que ce qui suit reformule le propos de la source, sans rien
    ajouter en eux-mêmes.
    """
    return _TOURNURE_DE_RAPPORT.sub("", text)


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

    Cinq retraits, tous mesurés sur ce wiki — deux avant `strip_code()`, trois
    après :

    - les balises `<ref>` : `strip_code()` garde leur contenu et le soude au
      mot précédent sans espace ("la parcelleSource : étude X") — une
      citation n'est de toute façon pas la prose de la section ;
    - les liens wiki invisibles sur la page rendue (catégorisation,
      interlangue) : `strip_code()` ne sait pas qu'ils sont invisibles et en
      affiche le titre comme texte ("Category:Anthracnose") ;
    - après `strip_code()`, le résidu d'un lien de catégorie dont les crochets
      ont été oubliés (":Catégorie:Chêne|chêne") : ce n'est pas un nœud wiki,
      donc invisible pour les deux retraits précédents ;
    - les URLs nues (`strip_urls`) ;
    - les blocs de configuration de graphique (`strip_chart_blocks`) : comme
      le résidu de catégorie, invisibles pour mwparserfromhell, donc traités
      après `strip_code()`.

    Les templates restent sinon gérés par `strip_code()` seul : mesuré sur ce
    wiki, ceux qui apparaissent dans le corps d'une section (hors lead/
    infobox) sont structurels (`{{Pages liées}}`, `{{#set:}}`...), jamais
    porteurs de prose.
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
    text = strip_chart_blocks(text)
    text = strip_urls(text)
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


def collapse_repeated_phrases(
    text: str, fenetre_max: int = 12, max_iter: int = 20
) -> str:
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
