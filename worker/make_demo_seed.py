"""
make_demo_seed.py — Fabriquer le jeu d'offres de démonstration (livraison, D10).

RÔLE :
    Lire toutes nos offres (seed/offers_sample.json, 7 298 offres, NON versionné)
    et en écrire un ÉCHANTILLON (seed/demo_offers.json, VERSIONNÉ dans Git).
    C'est cet échantillon que le conteneur "loader" charge chez le correcteur
    et sur le serveur, qui n'ont ni clé Adzuna ni nos données.

    À lancer UNE fois, chez nous (dans le venv, depuis le dossier worker) :
        python make_demo_seed.py

POURQUOI UN ÉCHANTILLON ?
    - le calcul des embeddings de 7 298 offres prendrait plusieurs minutes
      chez le correcteur ; ~1 800 offres : environ une minute ;
    - un échantillon suffit pour la démonstration ;
    - publier peu de données est plus prudent vis-à-vis d'Adzuna
      (source à citer : voir seed/README.md).

COMMENT LES OFFRES SONT CHOISIES : ÉCHANTILLONNAGE STRATIFIÉ
    1. On range les offres en GROUPES (région × contrats), ex.
       ("Bretagne", ["cdi"]), ("Île-de-France", ["alternance"]), (None, ["inconnu"]).
    2. Dans CHAQUE groupe, on tire 20 % des offres au hasard (au moins 1).
       -> toutes les régions et tous les contrats restent représentés, dans
          les mêmes proportions qu'au départ. Un tirage au hasard sur
          l'ensemble pourrait, par exemple, ne garder aucune offre de Corse.
    3. On ajoute TOUTES les alternances : c'est le scénario de la démo
       (une étudiante qui cherche une alternance).
    Résultat (mesuré) : 1 794 offres, 19 régions, tous les contrats.

    random.Random(42) : générateur au hasard avec une GRAINE fixe. Le "hasard"
    est alors toujours le même : relancer le script donne exactement le
    même fichier (reproductible).
"""

import json
import math                    # math.ceil : arrondi à l'entier supérieur
import random
from collections import defaultdict
from pathlib import Path

# Dossier seed/ à la racine du projet (ce fichier est dans worker/).
SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
SOURCE_FILE = SEED_DIR / "offers_sample.json"   # toutes nos offres (non versionné)
DEMO_FILE = SEED_DIR / "demo_offers.json"       # l'échantillon (versionné)

SAMPLE_RATE = 0.20     # part tirée dans chaque groupe
RANDOM_SEED = 42       # graine fixe : même tirage à chaque exécution


def group_key(offer: dict) -> tuple:
    """Le groupe d'une offre : (région, contrats).

    tuple(...) : une liste ne peut pas servir de clé de dictionnaire
    (elle est modifiable) ; un tuple, si.
    """
    return (offer.get("region"), tuple(offer.get("contract_types") or []))


def main() -> None:
    offers = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    print(f"Offres lues : {len(offers)} ({SOURCE_FILE.name})")

    # 1) Ranger les offres par groupe.
    #    defaultdict(list) : un dictionnaire qui crée tout seul une liste vide
    #    pour une clé encore inconnue (pas besoin de tester "if key in ...").
    groups = defaultdict(list)
    for offer in offers:
        groups[group_key(offer)].append(offer)

    # 2) Tirer 20 % de chaque groupe (au moins 1).
    #    Les groupes et leurs offres sont TRIÉS avant le tirage : sinon l'ordre
    #    du fichier source influencerait le résultat, et le tirage ne serait
    #    plus reproductible.
    rng = random.Random(RANDOM_SEED)
    selected_ids = set()
    for key in sorted(groups, key=str):
        group = sorted(groups[key], key=lambda offer: offer["source_id"])
        size = max(1, math.ceil(len(group) * SAMPLE_RATE))
        # rng.sample(liste, n) : n éléments différents, tirés au hasard.
        selected_ids.update(offer["source_id"] for offer in rng.sample(group, size))

    # 3) Ajouter TOUTES les alternances (scénario de la démo).
    selected_ids.update(
        offer["source_id"] for offer in offers
        if "alternance" in (offer.get("contract_types") or [])
    )

    # On garde l'ordre d'origine du fichier (lisibilité, diff Git stable).
    demo = [offer for offer in offers if offer["source_id"] in selected_ids]

    # ensure_ascii=False : garde les accents lisibles ("Île-de-France"
    # au lieu de "Île-de-France") ; indent=2 : fichier lisible.
    DEMO_FILE.write_text(json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8")

    regions = {offer.get("region") for offer in demo if offer.get("region")}
    print(f"Échantillon écrit : {len(demo)} offres, {len(regions)} régions -> {DEMO_FILE}")


if __name__ == "__main__":
    main()
