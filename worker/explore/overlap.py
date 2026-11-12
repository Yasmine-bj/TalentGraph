"""
overlap.py — Mesure des DOUBLONS entre nos recherches Adzuna.

QUESTION :
    Nos recherches (SEARCHES dans fetch_offers.py) se chevauchent-elles ?
    Ex. une offre "Data Scientist" qui cite "data engineers" dans sa
    description est ramenée à la fois par "data engineer" et "data scientist".
    Chaque doublon = une place perdue dans nos pages (et donc des appels
    qui ne rapportent pas d'offre nouvelle).

MÉTHODE :
    On relit le cache (seed/raw/adzuna/*.json), SANS appel API, et on regroupe
    les identifiants d'offres par recherche (toutes villes confondues).
    Pour chaque recherche on calcule :
      - total     : nombre d'offres ramenées ;
      - exclusive : offres que AUCUNE autre recherche n'a ramenées ;
      - partagées : le reste (doublons).
    Puis les paires de recherches qui se chevauchent le plus.

LANCEMENT (depuis worker/, venv activé) :
    python -m explore.overlap
"""

import json
from itertools import combinations  # toutes les paires (A, B) d'une liste
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "raw" / "adzuna"


def search_label(path: Path) -> str:
    """Nom lisible de la recherche à partir du nom du fichier de cache.

    "fr_data_france_p1__max_days_old-30__title_only-alternance.json" -> "data [title_only-alternance]"
    "fr_data-engineer_france_p2__max_days_old-30.json"            -> "data engineer"
    La ville et la page sont ignorées : on regroupe toutes les villes.
    """
    base, _, extra = path.stem.partition("__")  # coupe au premier "__"
    keywords = base.split("_")[1].replace("-", " ")
    # On retire les filtres communs à toutes les recherches (max_days_old),
    # qui n'aident pas à les distinguer.
    filters = [f for f in extra.split("__") if f and not f.startswith("max_days_old")]
    return f"{keywords} [{', '.join(filters)}]" if filters else keywords


def main() -> None:
    files = sorted(p for p in CACHE_DIR.glob("*.json") if not p.name.startswith("categories_"))
    if not files:
        print(f"Aucun fichier de cache dans {CACHE_DIR}")
        return

    # recherche -> ensemble (set) des identifiants d'offres.
    # Un set ne contient chaque élément qu'une fois et permet les opérations
    # d'ensembles : intersection (&), union (|), différence (-).
    ids_by_search: dict[str, set[str]] = {}
    for path in files:
        offers = json.loads(path.read_text(encoding="utf-8"))
        ids = ids_by_search.setdefault(search_label(path), set())
        ids.update(str(o.get("id")) for o in offers)

    all_ids = set().union(*ids_by_search.values())
    total_raw = sum(len(ids) for ids in ids_by_search.values())
    print(f"Offres ramenées (somme des recherches) : {total_raw}")
    print(f"Offres uniques                         : {len(all_ids)}")
    print(f"Doublons entre recherches              : {total_raw - len(all_ids)}"
          f" ({100 * (total_raw - len(all_ids)) / total_raw:.0f} %)\n")

    print(f"{'Recherche':40} {'Total':>6} {'Exclusives':>11} {'Partagées':>10}")
    for label, ids in sorted(ids_by_search.items()):
        # Union de toutes les AUTRES recherches
        others = set().union(*(v for k, v in ids_by_search.items() if k != label))
        exclusive = len(ids - others)
        shared = len(ids) - exclusive
        print(f"{label:40} {len(ids):>6} {exclusive:>11} {shared:>6} ({100 * shared / len(ids):.0f} %)")

    print("\nPaires qui se chevauchent le plus :")
    pairs = [
        (len(ids_by_search[a] & ids_by_search[b]), a, b)
        for a, b in combinations(sorted(ids_by_search), 2)
    ]
    for count, a, b in sorted(pairs, reverse=True)[:8]:
        if count:
            print(f"  {count:>4} offres communes : {a}  <->  {b}")


if __name__ == "__main__":
    main()
