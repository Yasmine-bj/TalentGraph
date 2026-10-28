"""
Adaptateur Adzuna : appelle l'API et convertit les offres vers JobOffer.
Documentation : https://developer.adzuna.com

Chaque réponse est mise en cache dans seed/raw/adzuna/ : si la page a déjà
été téléchargée, on la relit sur le disque au lieu de rappeler l'API.
"""

import json
import os
import time
from pathlib import Path

import requests

from models import JobOffer

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
TIMEOUT = 30              # secondes d'attente maximale par requête
RESULTS_PER_PAGE = 50   # maximum autorisé par Adzuna
PAUSE_BETWEEN_CALLS = 3   # rester sous la limite de débit

# Dossier du cache : seed/raw/adzuna/ à la racine du projet.
# __file__ = ce fichier ; parent = sources/ ; parent.parent = worker/ ;
# parent.parent.parent = racine du projet.
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "raw" / "adzuna"


def fetch_page(keywords: str, location: str, page: int, country: str = "fr") -> list[dict]:
    """Récupère une page de résultats bruts (format Adzuna), depuis le cache si possible."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Un nom de fichier unique par recherche, ex. fr_data_paris_p1.json
    safe_name = f"{country}_{keywords}_{location}_p{page}".lower().replace(" ", "-")
    cache_file = CACHE_DIR / f"{safe_name}.json"

    # 1) Déjà téléchargée : on relit le fichier, aucun appel consommé.
    if cache_file.exists():
        print(f"(cache) {cache_file.name}")
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # 2) Sinon, on appelle l'API. Les clés passent en paramètres d'URL.
    response = requests.get(
        BASE_URL.format(country=country, page=page),
        params={
            "app_id": os.environ["ADZUNA_APP_ID"],
            "app_key": os.environ["ADZUNA_APP_KEY"],
            "what": keywords,
            "where": location,
            "results_per_page": RESULTS_PER_PAGE,
        },
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )

    if not response.ok:
        # On affiche le statut et le corps, JAMAIS l'URL : elle contient la clé.
        print(f"Erreur {response.status_code} : {response.text[:300]}")
    response.raise_for_status()

    # 3) On sauvegarde la réponse brute avant de la renvoyer.
    results = response.json().get("results", [])
    cache_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"(API) {cache_file.name} : {len(results)} offres, appel consommé")
    return results


def to_job_offer(raw: dict) -> JobOffer:
    """Convertit une offre au format Adzuna vers notre format commun.

    .get() renvoie None si la clé est absente, au lieu de planter :
    les données d'une API externe sont souvent incomplètes.
    Le "or {}" évite une erreur si un sous-objet (company, location...) vaut None.
    """
    return JobOffer(
        source="adzuna",
        source_id=str(raw.get("id")),
        title=raw.get("title", ""),
        company=(raw.get("company") or {}).get("display_name"),
        location=(raw.get("location") or {}).get("display_name"),
        contract_type=raw.get("contract_type"),
        category=(raw.get("category") or {}).get("label"),
        description=raw.get("description", ""),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        created_at=raw.get("created"),
        url=raw.get("redirect_url", ""),
    )


def fetch_offers(keywords: str, location: str, max_pages: int = 1) -> list[JobOffer]:
    """Récupère plusieurs pages et renvoie des JobOffer."""
    offers: list[JobOffer] = []
    for page in range(1, max_pages + 1):   # Adzuna numérote les pages à partir de 1
        raw_results = fetch_page(keywords, location, page)
        print(f"Page {page} : {len(raw_results)} offres")
        if not raw_results:                # page vide : plus de résultats
            break
        offers.extend(to_job_offer(r) for r in raw_results)
        time.sleep(PAUSE_BETWEEN_CALLS)    # respecter la limite de débit
    return offers