"""
explore_filters.py — Test : les filtres de l'API Adzuna améliorent-ils la précision
des recherches ciblées par contrat ?

Comparaison sur la recherche "alternance" à Paris :
    A. what="alternance data"                     (déjà en cache : 0 appel)
    B. what="data" + title_only="alternance"      (le mot DOIT être dans le titre)
    C. B + category=<catégorie informatique>      (on reste dans l'informatique)

Script d'EXPLORATION. COÛT : au plus 3 appels (catégories + B + C),
puis 0 à chaque relance grâce au cache.

LANCEMENT (depuis worker/, venv activé) :
    python -m explore.explore_filters
"""

from collections import Counter

from dotenv import load_dotenv

load_dotenv()

from sources import adzuna  # noqa: E402

LOCATION = "Paris"


def report(name: str, offers: list) -> None:
    """Affiche la part d'offres dont le contrat détecté contient "alternance"."""
    n = len(offers)
    alternance = sum(1 for o in offers if "alternance" in o.contract_types)
    in_title = sum(1 for o in offers if "altern" in o.title.lower() or "apprenti" in o.title.lower())
    pct = lambda x: f"{100 * x // n} %" if n else "-"   # petite fonction anonyme
    print(f"\n=== {name} ===")
    print(f"Offres                         : {n}")
    print(f"Alternance détectée            : {alternance} ({pct(alternance)})")
    print(f"  dont 'alternance' dans titre : {in_title} ({pct(in_title)})")
    print(f"Catégories Adzuna              : {dict(Counter(o.category for o in offers))}")
    print("Exemples de titres :")
    for o in offers[:6]:
        print(f"  - {o.title}")


# 1) Catégories : trouver le code ("tag") de la catégorie informatique.
categories = adzuna.fetch_categories()
print("\nCatégories disponibles :")
for c in categories:
    print(f"  {c.get('tag'):30} {c.get('label')}")
it_tags = [c["tag"] for c in categories if c.get("tag") == "it-jobs"]
it_tag = it_tags[0] if it_tags else None
print(f"\nCatégorie informatique retenue : {it_tag}")

# 2) Les trois variantes de la recherche.
a = adzuna.fetch_offers("alternance data", LOCATION, max_pages=1)
b = adzuna.fetch_offers("data", LOCATION, max_pages=1, extra_params={"title_only": "alternance"})

report("A. what='alternance data'", a)
report("B. what='data' + title_only='alternance'", b)

if it_tag:
    c = adzuna.fetch_offers(
        "data", LOCATION, max_pages=1,
        extra_params={"title_only": "alternance", "category": it_tag},
    )
    report(f"C. B + category='{it_tag}'", c)
else:
    print("\nPas de catégorie 'it-jobs' trouvée : regarde la liste ci-dessus "
          "et adapte it_tag à la main.")
