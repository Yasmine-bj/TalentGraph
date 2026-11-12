"""
explore_contracts.py — Test : les recherches ciblées par contrat ramènent-elles
vraiment des offres de ce type ?

Script d'EXPLORATION (jetable) : il ne fait pas partie du pipeline final.

COÛT : 1 appel API par recherche non encore en cache (ici 3 recherches = 3 appels max).

LANCEMENT (depuis worker/, venv activé) :
    python -m explore.explore_contracts
    (-m lance le fichier comme un module : Python trouve alors sources/ et models.py)
"""

import re
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

from sources import adzuna  # noqa: E402

# Recherches ciblées : le mot du contrat est DANS les mots-clés.
# On note pour chacune le contrat qu'on "espère" obtenir.
SEARCHES = [
    ("alternance data", "alternance"),
    ("stage data", "stage"),
    ("apprentissage developpeur", "alternance"),
]
LOCATION = "Paris"

# Règles de détection dans le titre + la description.
# re.search cherche le motif n'importe où dans le texte.
#   \b = frontière de mot (évite de trouver "stage" dans "backstage")
#   |  = "ou"
PATTERNS = {
    "alternance": r"altern|apprenti",
    "stage": r"\bstage|\bstagiaire|\binternship\b|\bintern\b",
    "cdi": r"\bcdi\b|\bpermanent\b",
    "cdd": r"\bcdd\b",
    "freelance": r"freelance|indépendant",
}


def detect(text: str) -> list[str]:
    """Renvoie la liste des types de contrat repérés dans le texte."""
    text = text.lower()
    return [name for name, pattern in PATTERNS.items() if re.search(pattern, text)]


for keywords, expected in SEARCHES:
    print(f"\n=== Recherche '{keywords}' ({LOCATION}) — contrat espéré : {expected} ===")
    offers = adzuna.fetch_offers(keywords=keywords, location=LOCATION, max_pages=1)

    confirmed = 0               # le texte mentionne le contrat espéré
    found_in_title = 0          # le contrat espéré apparaît dans le TITRE
    other = Counter()           # autres contrats détectés à la place
    for o in offers:
        hits = detect(o.title + " " + o.description)
        if expected in hits:
            confirmed += 1
        if expected in detect(o.title):
            found_in_title += 1
        for h in hits:
            if h != expected:
                other[h] += 1

    n = len(offers) or 1  # évite une division par zéro si aucune offre
    print(f"Offres récupérées            : {len(offers)}")
    print(f"Contrat espéré dans le texte : {confirmed} ({100 * confirmed // n} %)")
    print(f"  dont dans le titre         : {found_in_title} ({100 * found_in_title // n} %)")
    print(f"Autres contrats détectés     : {dict(other)}")
    print(f"Champ Adzuna contract_type   : {dict(Counter(o.contract_type for o in offers))}")

    # Quelques titres pour juger à l'œil.
    print("Exemples de titres :")
    for o in offers[:8]:
        print(f"  - {o.title}")
