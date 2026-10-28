"""
Récupère des offres d'emploi et les sauvegarde en JSON dans seed/.

Étape d'exploration (M1) : regarder les vraies données avant de
concevoir le schéma PostgreSQL et le mapping Elasticsearch.
"""

import json
from pathlib import Path

from dotenv import load_dotenv

# Charger .env AVANT d'importer les sources, qui lisent os.environ.
load_dotenv()

from sources import adzuna  # noqa: E402  (import après load_dotenv, volontaire)

# Dossier de sortie : seed/ à la racine du projet.
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "seed"


def main() -> None:
    # PREMIER TEST : une seule page = un seul appel sur les 25 disponibles.
    offers = adzuna.fetch_offers(keywords="data", location="Paris", max_pages=2)
    print(f"Total : {len(offers)} offres récupérées.")

    # Sauvegarde au format commun JobOffer, en JSON lisible.
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / "offers_sample.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([o.to_dict() for o in offers], f, ensure_ascii=False, indent=2)
    print(f"Offres sauvegardées dans {output_file}")


if __name__ == "__main__":
    main()