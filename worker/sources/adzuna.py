"""
sources/adzuna.py — Adaptateur pour l'API Adzuna.

RÔLE :
    Tout ce qui est propre à Adzuna est isolé dans ce fichier :
      1. appeler l'API (URL, clés, paramètres, gestion des erreurs) ;
      2. mettre en CACHE chaque réponse sur le disque ;
      3. TRADUIRE chaque offre Adzuna vers notre format commun JobOffer.
    Le reste du projet ne sait pas qu'Adzuna existe : il ne voit que des JobOffer.
    Pour ajouter une autre source (Jooble, France Travail...), on crée un
    fichier voisin (sources/jooble.py) qui fournit la même fonction fetch_offers().

DOCUMENTATION DE L'API : https://developer.adzuna.com

RAPPEL SUR L'API ADZUNA :
    - Une recherche = une requête GET sur une URL du type :
        https://api.adzuna.com/v1/api/jobs/fr/search/1?app_id=...&app_key=...&what=data&where=Paris
    - 1 page = 1 appel = 50 offres au maximum. Pour 100 offres : 2 pages, donc 2 appels.
    - Abonnement : 500 appels par jour, 5 000 par mois.

POURQUOI UN CACHE ?
    Chaque appel est compté. Pendant le développement, on relance le script
    des dizaines de fois : sans cache, on paierait plusieurs fois les mêmes offres.
    Avec le cache, chaque page n'est téléchargée qu'UNE fois, puis relue sur le disque.
    Le terminal indique "(API)" quand un appel est consommé, "(cache)" sinon.
"""

import json             # lire / écrire du JSON (format des réponses et du cache)
import os               # os.environ : les variables d'environnement (nos clés)
import time             # time.sleep : faire une pause entre deux appels
from pathlib import Path  # manipuler des chemins de fichiers, quel que soit l'OS

import requests         # bibliothèque de référence pour les requêtes HTTP

from models import JobOffer  # notre format commun (voir models.py)


# ---------------------------------------------------------------------------
# CONSTANTES (en MAJUSCULES par convention : valeurs qui ne changent pas)
# ---------------------------------------------------------------------------

# Modèle d'URL : {country} et {page} sont remplacés plus bas avec .format().
# Exemple : BASE_URL.format(country="fr", page=1)
#        -> "https://api.adzuna.com/v1/api/jobs/fr/search/1"
BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Si Adzuna ne répond pas en 30 secondes, on abandonne la requête.
# Sans timeout, le programme pourrait rester bloqué indéfiniment.
TIMEOUT = 30

# Nombre d'offres demandées par page. Adzuna plafonne à 50 :
# demander plus ne renvoie pas plus. Pour avoir plus d'offres,
# on augmente le NOMBRE DE PAGES, pas leur taille.
RESULTS_PER_PAGE = 50

# Pause (en secondes) entre deux appels, pour respecter la limite de débit
# de l'API et ne pas être bloqué (erreur HTTP 429 "Too Many Requests").
PAUSE_BETWEEN_CALLS = 3

# Dossier du cache : <racine du projet>/seed/raw/adzuna/
#   Path(__file__)          -> le chemin de CE fichier (worker/sources/adzuna.py)
#   .resolve()              -> le transforme en chemin absolu
#   .parent                 -> worker/sources/
#   .parent.parent          -> worker/
#   .parent.parent.parent   -> la racine du projet
#   / "seed" / "raw" / ...  -> l'opérateur / assemble des morceaux de chemin
# Ce dossier est dans .gitignore : les réponses brutes ne vont pas sur GitHub.
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "raw" / "adzuna"


# ---------------------------------------------------------------------------
# 1. RÉCUPÉRER UNE PAGE (avec cache)
# ---------------------------------------------------------------------------

def fetch_page(keywords: str, location: str, page: int, country: str = "fr") -> list[dict]:
    """Récupère UNE page de résultats bruts (format Adzuna), depuis le cache si possible.

    Paramètres :
        keywords : mots-clés recherchés, ex. "data engineer"
        location : lieu, ex. "Paris"
        page     : numéro de page (Adzuna commence à 1)
        country  : code pays dans l'URL ("fr" par défaut)

    Renvoie :
        une liste de dictionnaires, chacun étant une offre au format Adzuna.
    """
    # Crée le dossier du cache s'il n'existe pas.
    #   parents=True  : crée aussi les dossiers parents manquants (seed/, seed/raw/)
    #   exist_ok=True : pas d'erreur si le dossier existe déjà
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Nom de fichier unique pour CETTE recherche et CETTE page.
    # f"..." est une f-string : les {variables} sont remplacées par leur valeur.
    # .lower() met en minuscules ; .replace(" ", "-") remplace les espaces.
    # Exemple : ("data engineer", "Paris", 2) -> "fr_data-engineer_paris_p2.json"
    # Attention : RESULTS_PER_PAGE ne fait pas partie du nom. Changer cette
    # constante ne déclenche donc PAS de nouveau téléchargement des pages en cache.
    safe_name = f"{country}_{keywords}_{location}_p{page}".lower().replace(" ", "-")
    cache_file = CACHE_DIR / f"{safe_name}.json"

    # --- Cas 1 : la page est déjà en cache -> on la relit, AUCUN appel consommé ---
    if cache_file.exists():
        print(f"(cache) {cache_file.name}")
        # read_text lit le fichier ; json.loads transforme le texte JSON
        # en objets Python (listes, dictionnaires).
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # --- Cas 2 : la page n'est pas en cache -> on appelle l'API ---
    # requests.get envoie une requête HTTP GET.
    #   params  : requests les ajoute à l'URL sous la forme ?clé=valeur&...
    #             en encodant correctement espaces et caractères spéciaux.
    #   headers : en-têtes HTTP ; "Accept" indique qu'on veut du JSON.
    #   timeout : délai maximal d'attente (voir TIMEOUT).
    # Les clés sont lues dans os.environ, rempli depuis .env par load_dotenv()
    # (dans fetch_offers.py). Elles ne sont JAMAIS écrites dans le code.
    response = requests.get(
        BASE_URL.format(country=country, page=page),
        params={
            "app_id": os.environ["ADZUNA_APP_ID"],    # identifiant de l'application
            "app_key": os.environ["ADZUNA_APP_KEY"],  # clé secrète
            "what": keywords,                         # mots-clés
            "where": location,                        # lieu
            "results_per_page": RESULTS_PER_PAGE,     # taille de la page
        },
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )

    # Gestion des erreurs HTTP.
    # response.ok vaut True pour les codes 2xx (succès), False sinon.
    # Codes fréquents : 401 = clé invalide, 400 = paramètre refusé,
    #                   429 = trop de requêtes, 5xx = problème côté Adzuna.
    if not response.ok:
        # On affiche le code et le début de la réponse (qui explique l'erreur),
        # mais JAMAIS l'URL : elle contient la clé secrète en clair.
        print(f"Erreur {response.status_code} : {response.text[:300]}")
    # raise_for_status() lève une exception si le code est une erreur (4xx, 5xx) :
    # le programme s'arrête au lieu de continuer avec des données invalides.
    response.raise_for_status()

    # --- On sauvegarde la réponse brute dans le cache, puis on la renvoie ---
    # response.json() transforme la réponse en dictionnaire Python.
    # .get("results", []) : la liste des offres, ou une liste vide si la clé manque.
    results = response.json().get("results", [])
    # json.dumps fait l'inverse de json.loads (objets Python -> texte JSON).
    #   ensure_ascii=False : garde les accents lisibles (é au lieu de é)
    #   indent=2           : met en forme le fichier pour qu'il soit lisible
    cache_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"(API) {cache_file.name} : {len(results)} offres, appel consommé")
    return results


# ---------------------------------------------------------------------------
# 2. TRADUIRE UNE OFFRE ADZUNA VERS NOTRE FORMAT
# ---------------------------------------------------------------------------

def to_job_offer(raw: dict) -> JobOffer:
    """Convertit UNE offre au format Adzuna vers notre format commun JobOffer.

    C'est le cœur de l'adaptateur : la seule fonction qui connaît les noms
    de champs d'Adzuna.

    Exemple d'offre brute Adzuna (simplifiée) :
        {
          "id": "5937384042",
          "title": "Data Engineer, Data Core",
          "company": {"display_name": "Vibe.co"},
          "location": {"display_name": "Paris, Ile-de-France"},
          "category": {"label": "Emplois Autres/Général"},
          "description": "Join Vibe's Data Platform team...",
          "salary_min": 88000, "salary_max": 120000,
          "created": "2026-10-22T06:01:47Z",
          "redirect_url": "https://www.adzuna.fr/details/5937384042?..."
        }

    Robustesse : les données d'une API externe sont souvent INCOMPLÈTES.
      - raw.get("cle") renvoie None si la clé est absente, au lieu de planter
        comme raw["cle"] le ferait (KeyError).
      - raw.get("title", "") renvoie "" (et non None) si le titre manque.
      - Pour les sous-objets (company, location, category) :
            (raw.get("company") or {}).get("display_name")
        * raw.get("company") -> le sous-objet, ou None s'il manque
        * or {}              -> si c'est None, on prend un dictionnaire vide
        * .get("display_name") -> le nom, ou None
        Sans ce "or {}", None.get(...) ferait planter tout le programme
        à cause d'UNE seule offre incomplète.
    """
    return JobOffer(
        source="adzuna",
        source_id=str(raw.get("id")),   # str() : on stocke l'identifiant en texte
        title=raw.get("title", ""),
        company=(raw.get("company") or {}).get("display_name"),
        location=(raw.get("location") or {}).get("display_name"),
        contract_type=raw.get("contract_type"),
        category=(raw.get("category") or {}).get("label"),
        description=raw.get("description", ""),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        created_at=raw.get("created"),          # Adzuna l'appelle "created"
        url=raw.get("redirect_url", ""),        # Adzuna l'appelle "redirect_url"
    )


# ---------------------------------------------------------------------------
# 3. FONCTION PUBLIQUE : récupérer plusieurs pages et renvoyer des JobOffer
# ---------------------------------------------------------------------------

def fetch_offers(keywords: str, location: str, max_pages: int = 1) -> list[JobOffer]:
    """Récupère jusqu'à max_pages pages et renvoie la liste des JobOffer.

    C'est la seule fonction que le reste du projet appelle.
    Toute future source devra fournir une fonction avec cette même signature.

    Nombre d'offres  = 50 x nombre de pages (au maximum)
    Nombre d'appels  = nombre de pages qui ne sont pas déjà en cache
    """
    # Annotation : offers est une liste de JobOffer, vide au départ.
    offers: list[JobOffer] = []

    # range(1, max_pages + 1) produit 1, 2, ..., max_pages
    # (le +1 car range s'arrête AVANT la borne de fin ; Adzuna commence à la page 1).
    for page in range(1, max_pages + 1):
        raw_results = fetch_page(keywords, location, page)
        print(f"Page {page} : {len(raw_results)} offres")

        # Une page vide signifie qu'il n'y a plus de résultats : inutile
        # de demander les pages suivantes (on économise des appels).
        if not raw_results:
            break

        # On convertit chaque offre brute en JobOffer et on les ajoute à la liste.
        #   to_job_offer(r) for r in raw_results  -> un GÉNÉRATEUR : applique
        #   to_job_offer à chaque offre, une par une.
        #   .extend(...) ajoute tous ces éléments à la fin de la liste.
        offers.extend(to_job_offer(r) for r in raw_results)

        # Pause avant la page suivante, pour respecter la limite de débit.
        # (Remarque : la pause a lieu même si la page venait du cache ;
        #  on pourra l'optimiser plus tard.)
        time.sleep(PAUSE_BETWEEN_CALLS)

    return offers
