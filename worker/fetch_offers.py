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


# ---------------------------------------------------------------------------
# LISTE DES RECHERCHES
# Chaque recherche est un DICTIONNAIRE :
#   - "what"       : les mots-clés envoyés à Adzuna (obligatoire) ;
#   - "title_only" : (facultatif) mot qui doit apparaître DANS LE TITRE.
# Toutes les clés autres que "what" sont transmises telles quelles à Adzuna
# comme filtres (paramètre extra_params de adzuna.fetch_offers).
#
# Pourquoi title_only seulement pour stage et alternance ?
#   Les recruteurs écrivent presque toujours "Stage" / "Alternance" dans le
#   titre, mais rarement "CDI". Test (worker/explore/explore_filters.py) :
#     what="alternance data"                 -> 27 offres, 70 % d'alternances
#     what="data" + title_only="alternance"  -> 50 offres, 100 % d'alternances
#     ... + category="it-jobs"               -> 4 offres : catégories peu fiables,
#                                               filtre category abandonné
#   CDI / CDD / freelance : recherches générales + détection dans le texte
#   (contracts.py).
#
# Recherches NATIONALES (sans "where") : la ville sera filtrée dans notre base.
# Test (explore/page_size.py) : "data engineer" = 2 277 offres en France,
# dont seulement 839 dans Paris intra-muros -> chercher par ville en ratait 63 %.
# Coût maximal : len(SEARCHES) x PAGES_PER_SEARCH = 26 x 8 = 208 appels
# (moins en réalité, grâce à l'arrêt anticipé sur page incomplète).
# Abonnement : 500 appels/jour, 2 000/semaine -> ne lancer qu'une fois par semaine.
# ---------------------------------------------------------------------------
# ---- Recherches GÉNÉRALES : tous types de contrats, 5 familles de métiers ----
# Règle d'écriture : avec "what", TOUS les mots doivent être dans l'offre.
#   -> mots-clés courts, sans "engineer" imposé : "devops" trouve à la fois
#      "Ingénieur DevOps" et "DevOps Engineer" ; "DevOps engineer" raterait
#      les offres rédigées en français.
#   -> pas de quasi-doublons (ex. "AI engineer" / "ingénieur IA" / "ML engineer") :
#      chaque doublon consomme des places sans apporter d'offre nouvelle.
GENERAL_SEARCHES = [
    # Data & IA
    {"what": "data engineer"},
    {"what": "data scientist"},
    {"what": "data analyst"},
    {"what": "data architect"},
    {"what": "business intelligence"},
    {"what": "machine learning"},
    {"what": "mlops"},
    {"what": "intelligence artificielle"},
    # Développement
    {"what": "développeur python"},
    {"what": "développeur java"},
    {"what": "développeur javascript"},
    {"what": "développeur full stack"},
    {"what": "développeur mobile"},
    {"what": "systèmes embarqués"},
    # Cloud & infra
    {"what": "devops"},
    # "cloud" est cité dans énormément d'offres (ex. "environnement cloud") :
    # on l'exige dans le TITRE pour ne garder que les vrais postes cloud.
    {"what": "cloud", "title_only": "cloud"},
    {"what": "administrateur système"},
    {"what": "ingénieur réseau"},
    # Cybersécurité
    {"what": "cybersécurité"},
    {"what": "pentest"},
]

# ---- Recherches CIBLÉES par contrat : le contrat est garanti par le titre ----
# "data" couvre déjà data engineer / scientist / analyst : inutile de les
# cibler un par un (ce seraient des doublons).
CONTRACT_SEARCHES = [
    {"what": "data", "title_only": "alternance"},
    {"what": "data", "title_only": "stage"},
    {"what": "développeur", "title_only": "alternance"},
    {"what": "développeur", "title_only": "stage"},
    {"what": "cybersécurité", "title_only": "alternance"},
    {"what": "cybersécurité", "title_only": "stage"},
]

# Liste complète parcourue par main() : "+" met les deux listes bout à bout.
SEARCHES = GENERAL_SEARCHES + CONTRACT_SEARCHES
PAGES_PER_SEARCH = 8  # 8 pages x 50 = jusqu'à 400 offres par recherche

# Filtres appliqués à TOUTES les recherches (ajoutés à ceux de chaque ligne).
#   max_days_old=30 : uniquement les offres publiées depuis moins de 30 jours.
#     Les plus anciennes sont souvent déjà pourvues (règle d'expiration prévue :
#     45 jours), inutile de les télécharger.
#   Pas de sort_by : on garde le tri par PERTINENCE (défaut d'Adzuna). Avec
#     8 pages seulement, on veut les 400 offres qui correspondent le MIEUX à la
#     recherche ; la fraîcheur est déjà garantie par max_days_old.
#     (sort_by=date servira pour la mise à jour quotidienne.)
COMMON_FILTERS = {"max_days_old": 30}


def main() -> None:
    """Lance toutes les recherches, supprime les doublons, sauvegarde le résultat."""

    # 1) Récupération : une recherche NATIONALE par ligne de SEARCHES.
    #    Pas de ville : la localisation de chaque offre est conservée et
    #    servira à filtrer dans NOTRE base (M2), au moment de la recherche.
    all_offers = []
    for search in SEARCHES:
        # On sépare les mots-clés ("what") des filtres (tout le reste).
        #   {k: v for ...} : compréhension de dictionnaire qui garde toutes
        #   les clés sauf "what". Ex. {"title_only": "alternance"}, ou {}.
        keywords = search["what"]
        filters = {k: v for k, v in search.items() if k != "what"}
        # On ajoute les filtres communs. {**a, **b} fusionne deux dictionnaires
        # (en cas de clé commune, la valeur de b l'emporte).
        filters = {**COMMON_FILTERS, **filters}
        print(f"\n=== {keywords} {filters} / France ===")
        all_offers.extend(
            adzuna.fetch_offers(
                keywords=keywords,
                location=None,  # None = toute la France
                max_pages=PAGES_PER_SEARCH,
                extra_params=filters,
            )
        )
    print(f"\nTotal brut : {len(all_offers)} offres")

    # 2) Suppression des doublons : une même offre peut être ramenée par
    #    plusieurs recherches (ex. "data engineer" et "développeur python").
    #    {clé: valeur for ...} est une COMPRÉHENSION DE DICTIONNAIRE.
    #    Un dictionnaire ne peut pas avoir deux fois la même clé : une offre
    #    déjà vue est simplement remplacée. La clé (source, source_id)
    #    identifie une offre de façon unique, même avec plusieurs sources.
    #    Remarque : on garde la DERNIÈRE occurrence vue, donc son search_keywords.
    unique = {(o.source, o.source_id): o for o in all_offers}
    offers = list(unique.values())
    print(f"Après suppression des doublons : {len(offers)} offres")

    # 3) Sauvegarde au format commun JobOffer.
    #    mkdir(exist_ok=True) : crée seed/ si besoin, sans erreur s'il existe.
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / "offers_sample.json"

    # open(..., "w") : mode ÉCRITURE -> le fichier est EFFACÉ puis réécrit.
    #   (le mode "a" ajouterait à la fin, ce qui casserait le format JSON :
    #    on obtiendrait [ ... ][ ... ], qui n'est plus un JSON valide)
    # "with" ferme automatiquement le fichier à la fin du bloc, même en cas d'erreur.
    with open(output_file, "w", encoding="utf-8") as f:
        # [o.to_dict() for o in offers] : COMPRÉHENSION DE LISTE qui convertit
        # chaque JobOffer en dictionnaire (json.dump ne sait pas écrire un objet).
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
