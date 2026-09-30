"""Nettoyage du texte des unités — transformations pures.

Comme `units.py`, ce module ne lit ni n'écrit rien : il prend du texte et en
renvoie. Il intervient après le découpage structurel et après le nettoyage du
markup, sur du texte déjà normalisé.
"""

from __future__ import annotations

import re

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
