"""
fetch_offers.py — Point d'entrée de l'ingestion des offres (module M1).

RÔLE :
    Le "chef d'orchestre" : il demande des offres à une source
    (aujourd'hui Adzuna) puis sauvegarde le résultat en JSON.
    Il ne sait PAS comment fonctionne l'API : c'est le rôle de sources/adzuna.py.

LANCEMENT (depuis le dossier worker/, avec le venv activé) :
    cd worker
    python fetch_offers.py

FICHIERS PRODUITS :
    - seed/raw/adzuna/*.json   : réponses brutes de l'API (cache, une par page)
    - seed/offers_sample.json  : les offres au format JobOffer, RÉÉCRIT à chaque lancement
    Ces deux emplacements sont dans .gitignore (non versionnés).

ÉTAPE SUIVANTE (M2) :
    Ces offres seront chargées dans PostgreSQL puis indexées dans Elasticsearch.
"""

import json               # écrire le résultat au format JSON
from pathlib import Path  # construire le chemin du dossier de sortie

from dotenv import load_dotenv  # lit le fichier .env

# ---------------------------------------------------------------------------
# Chargement des secrets
# ---------------------------------------------------------------------------
# load_dotenv() lit le fichier .env (cherché en remontant depuis le dossier
# courant jusqu'à la racine du projet) et place chaque ligne NOM=valeur
# dans os.environ. Les clés Adzuna ne sont donc jamais écrites dans le code,
# ni envoyées sur GitHub (.env est dans .gitignore).
# On l'appelle AVANT d'importer les sources, qui lisent os.environ.
load_dotenv()

# Import de l'adaptateur Adzuna (le dossier sources/ est un package
# grâce à son fichier __init__.py).
# "# noqa: E402" : indique aux outils de vérification (linters) que cet import
# placé après du code est VOLONTAIRE (il doit venir après load_dotenv).
from sources import adzuna  # noqa: E402

# Dossier de sortie : <racine du projet>/seed/
#   Path(__file__).resolve() -> chemin absolu de ce fichier (worker/fetch_offers.py)
#   .parent                  -> worker/
#   .parent.parent           -> la racine du projet
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "seed"


def main() -> None:
    """Récupère les offres puis les sauvegarde dans seed/offers_sample.json."""

    # 1) Récupération : "data" à Paris, 2 pages = jusqu'à 100 offres.
    #    Chaque page non encore en cache consomme 1 appel API (50 offres max par page).
    offers = adzuna.fetch_offers(keywords="data", location="Paris", max_pages=1)
    print(f"Total : {len(offers)} offres récupérées.")

    # 2) Sauvegarde au format commun JobOffer.
    #    mkdir(exist_ok=True) : crée seed/ si besoin, sans erreur s'il existe.
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / "offers_sample.json"

    # open(..., "w") : mode ÉCRITURE -> le fichier est EFFACÉ puis réécrit.
    #   (le mode "a" ajouterait à la fin, ce qui casserait le format JSON :
    #    on obtiendrait [ ... ][ ... ], qui n'est plus un JSON valide)
    # "with" ferme automatiquement le fichier à la fin du bloc, même en cas d'erreur.
    with open(output_file, "w", encoding="utf-8") as f:
        # [o.to_dict() for o in offers] est une COMPRÉHENSION DE LISTE :
        # elle construit une nouvelle liste en convertissant chaque JobOffer
        # en dictionnaire (json.dump ne sait pas écrire un objet JobOffer).
        #   ensure_ascii=False : accents lisibles ; indent=2 : fichier mis en forme.
        json.dump([o.to_dict() for o in offers], f, ensure_ascii=False, indent=2)
    print(f"Offres sauvegardées dans {output_file}")


# ---------------------------------------------------------------------------
# Python donne à chaque fichier une variable __name__ :
#   - "__main__" si le fichier est LANCÉ directement (python fetch_offers.py) ;
#   - le nom du module ("fetch_offers") s'il est IMPORTÉ par un autre fichier.
# Ce test permet donc de lancer main() uniquement quand on exécute ce fichier,
# sans déclencher de téléchargement si un autre module l'importe un jour.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
