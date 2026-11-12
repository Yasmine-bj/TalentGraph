"""
contracts_stats.py — Statistiques des types de contrat détectés sur les offres en cache.

Script d'EXPLORATION : il relit les réponses brutes déjà téléchargées
(seed/raw/adzuna/*.json) et applique detect_contract_types().
AUCUN appel API : coût nul, on peut le relancer autant qu'on veut.

LANCEMENT (depuis worker/, venv activé) :
    python -m explore.contracts_stats
"""

import json
from collections import Counter
from pathlib import Path

from contracts import detect_contract

# Dossier du cache Adzuna : <racine du projet>/seed/raw/adzuna/
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "raw" / "adzuna"


def keywords_from_filename(path: Path) -> str:
    """Retrouve les mots-clés de la recherche à partir du nom du fichier de cache.

    Le nom a la forme  <pays>_<mots-clés>_<ville>_p<page>.json
    ex. "fr_stage-data_paris_p1.json" -> "stage data"
    (dans le nom, les espaces ont été remplacés par des tirets)
    """
    parts = path.stem.split("_")       # stem = nom sans ".json"
    return parts[1].replace("-", " ")  # 2e morceau = mots-clés


def main() -> None:
    # On ne garde que les fichiers de RECHERCHE (ils commencent par le code pays),
    # pas categories_fr.json qui contient la liste des catégories.
    files = sorted(p for p in CACHE_DIR.glob("*.json") if not p.name.startswith("categories_"))
    if not files:
        print(f"Aucun fichier de cache dans {CACHE_DIR}")
        return

    # Une offre peut apparaître dans plusieurs recherches : on la compte une seule
    # fois, grâce à un dictionnaire indexé par son identifiant.
    contracts_by_offer: dict[str, tuple[str, ...]] = {}
    source_by_offer: dict[str, str] = {}

    print("=== Par fichier de cache ===")
    for path in files:
        keywords = keywords_from_filename(path)
        offers = json.loads(path.read_text(encoding="utf-8"))
        per_file = Counter()
        for raw in offers:
            types, source = detect_contract(
                title=raw.get("title", ""),
                description=raw.get("description", ""),
                search_keywords=keywords,
                contract_raw=raw.get("contract_type"),
            )
            # tuple(...) : une liste ne peut pas servir de clé de Counter,
            # un tuple (liste non modifiable) si.
            per_file[tuple(types)] += 1
            contracts_by_offer[str(raw.get("id"))] = tuple(types)
            source_by_offer[str(raw.get("id"))] = source
        print(f"{path.name:60} ({len(offers):>3} offres) {dict(per_file)}")

    # Statistiques globales sur les offres uniques.
    total = len(contracts_by_offer)
    stats = Counter(contracts_by_offer.values())
    print(f"\n=== Global : {total} offres uniques ===")
    print(f"{'Contrat détecté':25} {'Offres':>7} {'Part':>6}")
    for contracts, count in stats.most_common():
        label = " + ".join(contracts)
        print(f"{label:25} {count:>7} {100 * count / total:>5.0f} %")

    # D'où vient l'information (niveau de confiance).
    sources = Counter(source_by_offer.values())
    print(f"\n=== Source du contrat ===")
    print(f"{'Source':25} {'Offres':>7} {'Part':>6}")
    for source, count in sources.most_common():
        print(f"{source:25} {count:>7} {100 * count / total:>5.0f} %")


if __name__ == "__main__":
    main()
