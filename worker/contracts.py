"""
contracts.py — Détection du type de contrat d'une offre d'emploi.

POURQUOI CE FICHIER ?
    Le champ "contrat" fourni par les sources est peu fiable. Analyse des offres
    Adzuna (octobre 2026, voir docs/learning-log.md) :
      - contract_type vide pour 63 % des offres ;
      - valeurs limitées à "permanent" / "contract" : ni "stage" ni "alternance" ;
      - sur 50 stages, 23 étiquetés "contract" et 1 étiqueté "permanent".
    En revanche, le TITRE mentionne presque toujours le contrat pour les stages
    et les alternances. On déduit donc le contrat du TEXTE de l'offre plutôt
    que du champ officiel.
    Note : les stages et alternances sont aussi ciblés dès la recherche
    (title_only, voir fetch_offers.py). Ce module sert surtout pour les
    recherches générales (CDI, CDD, freelance).

ORDRE DE CONFIANCE (on s'arrête à la première source qui donne un résultat) :
    1. le titre                   -> le plus fiable
    2. la description             -> souvent tronquée chez Adzuna
    3. la recherche d'origine     -> mots-clés de la recherche
    4. le champ brut de la source -> "permanent" = cdi (voir plus bas)
    5. sinon                      -> ["inconnu"]
    La fonction renvoie aussi la SOURCE de l'information (contract_source),
    pour distinguer un contrat ÉCRIT dans l'offre d'un contrat DÉDUIT.

ÉTAPE 4 : POURQUOI "permanent" -> cdi ?
    Mesure sur 7 298 offres (29/10/2026) : parmi les offres dont le texte
    donne le contrat ET qu'Adzuna marque "permanent", 624 sont des CDI et
    28 des stages -> Adzuna a raison dans ~96 % des cas. Le champ est souvent
    VIDE, mais rarement FAUX quand il dit "permanent".
    En revanche "contract" est inutilisable : il regroupe stages (855),
    freelances (327), alternances (67) et CDD (24). On l'ignore.
    Cette étape n'intervient qu'en DERNIER recours : si le texte dit
    "stage", le texte gagne, même si Adzuna dit "permanent".

DEUX JEUX DE MOTIFS : LARGES pour le titre, STRICTS pour la description.
    Un titre est court et parle du poste : "Stage" ou "Apprenti" y désignent
    forcément le contrat. Une description est longue et parle de tout :
    des mots isolés y sont AMBIGUS. Bugs constatés avec un motif unique :
      "l'apprentissage automatique" (= machine learning) -> alternance  ✗
      "our early-stage startup" (anglais)                 -> stage       ✗
      "des solutions alternatives"                        -> alternance  ✗
      "travailler de manière indépendante"                -> freelance   ✗
    Dans la description, on exige donc des EXPRESSIONS non ambiguës :
    "en alternance", "contrat d'apprentissage", "stage de 6 mois", "stagiaire"...

INDÉPENDANT DE TOUTE SOURCE :
    Ce module analyse du texte, pas une API. Il est donc dans worker/ et non
    dans sources/ : Adzuna, Jooble ou France Travail peuvent tous l'utiliser.
    Et comme il ne fait AUCUN appel, on peut l'améliorer à tout moment puis
    le rejouer sur les réponses en cache.
"""

import re  # expressions régulières : rechercher des motifs dans du texte

# ---------------------------------------------------------------------------
# Rappels sur les expressions régulières utilisées :
#   \b        frontière de mot : "\bstage" ne trouve pas "backstage".
#   |         "ou".
#   ?         l'élément précédent est facultatif : "apprentis?" = apprenti(s).
#   (a|b)     groupe : "a" ou "b".
#   [’']      un caractère parmi la liste : apostrophe droite ou typographique.
#   \s+       un ou plusieurs espaces.
#   \d        un chiffre.
#   (?!...)   "NON suivi de" (lookahead négatif) : "apprentissage(?! automatique)"
#             trouve "apprentissage" sauf s'il est suivi de " automatique".
# La recherche ignore les majuscules (re.IGNORECASE, plus bas).
# L'ordre des clés est l'ordre dans le résultat (ex. ["alternance", "stage"]).
# ---------------------------------------------------------------------------

# Le français dit "apprentissage" pour l'alternance ET pour le machine learning
# ("apprentissage automatique / profond / supervisé / par renforcement").
# Ce motif exclut ces cas (utilisé dans les deux jeux de motifs).
_NOT_ML = r"(?!\s+(automatique|profond|supervis|non[- ]supervis|par\s+renforcement|statistique))"

# Motifs LARGES, pour le TITRE (et les mots-clés de la recherche).
TITLE_PATTERNS: dict[str, str] = {
    "alternance": (
        r"\balternan"                       # alternance, alternant(e)
        rf"|\bapprenti(e|s|es)?\b"          # apprenti(e)(s)
        rf"|\bapprentissage\b{_NOT_ML}"     # apprentissage, sauf machine learning
        r"|\bapprenticeship\b|\bwork[- ]study\b"
    ),
    "stage": r"\bstages?\b|\bstagiaires?\b|\binternship\b|\bintern\b",
    "cdi": r"\bcdi\b",
    "cdd": r"\bcdd\b",
    "freelance": r"\bfreelance\b|\bindépendant\b",
}

# Motifs STRICTS, pour la DESCRIPTION : uniquement des expressions non ambiguës.
DESCRIPTION_PATTERNS: dict[str, str] = {
    "alternance": (
        r"\balternance\b|\balternant(e|s|es)?\b"
        r"|\bcontrat\s+d[’']apprentissage\b"
        rf"|\ben\s+apprentissage\b{_NOT_ML}"   # "poste en apprentissage", pas "expert en apprentissage automatique"
        r"|\bapprenti(e|s|es)?\b"
        r"|\bcontrat\s+de\s+professionnalisation\b"
        r"|\bapprenticeship\b|\bwork[- ]study\b"
    ),
    "stage": (
        r"\bstage\s+(de|d[’']|en|pfe|\d)"     # "stage de 6 mois", "stage d'une durée", "stage 6 mois"
        r"|\bstagiaires?\b"
        r"|\boffre\s+de\s+stage\b"
        r"|\bconvention\s+de\s+stage\b"
        r"|\binternship\b"
    ),
    "cdi": r"\bcdi\b",
    "cdd": r"\bcdd\b",
    "freelance": (
        r"\bfreelance\b"
        r"|\bportage\s+salarial\b"
        r"|\btjm\b"                           # taux journalier moyen : propre au freelance
    ),
}

# Valeur utilisée quand aucune information n'est trouvée.
# Dans la recherche, ces offres ne seront PAS exclues : elles seront
# simplement classées après celles dont le contrat est confirmé.
UNKNOWN = "inconnu"


def _find_contracts(text: str, patterns: dict[str, str]) -> list[str]:
    """Renvoie la liste des types de contrat trouvés dans un texte.

    patterns : le jeu de motifs à utiliser (TITLE_PATTERNS ou DESCRIPTION_PATTERNS).
    Liste vide si rien n'est trouvé (ou si le texte est vide).
    Le "_" au début du nom est une convention Python : fonction INTERNE
    à ce module, à ne pas appeler depuis un autre fichier.
    """
    if not text:
        return []
    # Compréhension de liste : on garde chaque nom dont le motif est trouvé.
    return [
        name
        for name, pattern in patterns.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]


def detect_contract(
    title: str,
    description: str = "",
    search_keywords: str | None = None,
    contract_raw: str | None = None,
) -> tuple[list[str], str]:
    """Déduit les types de contrat d'une offre ET la source de cette information.

    Paramètres :
        title           : intitulé de l'offre
        description     : description (éventuellement tronquée)
        search_keywords : mots-clés de la recherche qui a ramené l'offre
        contract_raw    : valeur brute du contrat fournie par la source
                          (Adzuna : "permanent", "contract" ou None)

    Renvoie un TUPLE (deux valeurs à la fois) :
        - la liste des contrats : "cdi", "cdd", "stage", "alternance",
          "freelance", ou ["inconnu"] ;
        - la source : "title", "description", "keywords", "adzuna" ou "none".
    Utilisation :  types, source = detect_contract(...)

    Exemples :
        detect_contract("Stage - Data Analyst")                  -> (["stage"], "title")
        detect_contract("Stage / Alternance - Consultant")       -> (["alternance", "stage"], "title")
        detect_contract("Data Engineer", "Poste en CDI")         -> (["cdi"], "description")
        detect_contract("Data Engineer", "", None, "permanent")  -> (["cdi"], "adzuna")
        detect_contract("Stage Data", "", None, "permanent")     -> (["stage"], "title")
        detect_contract("Data Scientist", "apprentissage automatique") -> (["inconnu"], "none")
    """
    # Chaque source de texte avec SON jeu de motifs, dans l'ordre de confiance.
    # "search_keywords or ''" : si search_keywords vaut None, on prend "".
    # Chaque élément : (nom de la source, texte, jeu de motifs).
    sources = (
        ("title", title, TITLE_PATTERNS),
        ("description", description, DESCRIPTION_PATTERNS),
        ("keywords", search_keywords or "", TITLE_PATTERNS),  # mots-clés courts, comme un titre
    )
    for source_name, text, patterns in sources:
        found = _find_contracts(text, patterns)
        if found:          # liste non vide : on a trouvé, on s'arrête là
            return found, source_name
    # Étape 4 (dernier recours) : le champ brut de la source.
    if contract_raw == "permanent":
        return ["cdi"], "adzuna"
    return [UNKNOWN], "none"


def detect_contract_types(
    title: str,
    description: str = "",
    search_keywords: str | None = None,
    contract_raw: str | None = None,
) -> list[str]:
    """Version simplifiée de detect_contract : renvoie seulement la liste des contrats.

    Gardée pour les scripts d'exploration qui n'ont pas besoin de la source.
    "types, _ = ..." : le "_" signifie "valeur ignorée".
    """
    types, _ = detect_contract(title, description, search_keywords, contract_raw)
    return types
