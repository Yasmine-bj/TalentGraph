"""
page_size.py — Test : combien d'offres Adzuna renvoie-t-il VRAIMENT par page ?

QUESTION :
    On demande results_per_page=50. Mais :
      1. Adzuna renvoie-t-il bien 50 offres quand il en a beaucoup plus ?
         (sinon notre arrêt "page incomplète = dernière page" serait faux)
      2. Accepte-t-il plus de 50 ? Si results_per_page=100 renvoie 100 offres,
         on pourrait diviser par deux le nombre d'appels.

MÉTHODE :
    Une recherche qui a BEAUCOUP de résultats ("data engineer" en France),
    appelée deux fois : avec 50 puis 100 offres demandées.
    On compare :
      - "count"          : nombre TOTAL d'offres correspondantes chez Adzuna
                           (champ renvoyé dans chaque réponse) ;
      - len(results)     : nombre d'offres réellement présentes dans la page.
    Si count > demandé et len(results) == demandé -> Adzuna respecte la taille.

RÉSULTATS (28/10/2026) :
    "data engineer" à Paris (where=Paris, rayon 5 km) : count = 839
    "data engineer" France entière (sans where)        : count = 2 277
    Demandé 50 -> reçu 50 ; demandé 100 -> reçu 50.
    Conclusions :
      - Adzuna plafonne à 50 offres par page -> RESULTS_PER_PAGE = 50 ;
      - les pages sont pleines tant qu'il reste des offres -> l'arrêt
        "page incomplète = dernière page" est correct ;
      - Paris intra-muros ne représente que 37 % des offres -> on cherche
        désormais dans toute la France (fetch_offers.py).

    PAS DE CACHE ici, volontairement : un ancien fichier en cache fausserait
    le test (c'est ce qui nous avait trompés la première fois avec 100).

COÛT : 2 appels.

LANCEMENT (depuis worker/, venv activé) :
    python -m explore.page_size
"""

import os

from dotenv import load_dotenv

load_dotenv()

from sources.adzuna import BASE_URL, _safe_get  # noqa: E402

# _safe_get commence par "_" (fonction interne) : on l'utilise ici quand même,
# car c'est un script de test et elle garantit que la clé n'apparaît jamais
# dans un message d'erreur.


def main() -> None:
    for requested in (50, 100):
        response = _safe_get(
            BASE_URL.format(country="fr", page=1),
            params={
                "app_id": os.environ["ADZUNA_APP_ID"],
                "app_key": os.environ["ADZUNA_APP_KEY"],
                "what": "data engineer",
                "results_per_page": requested,
            },
        )
        if not response.ok:
            print(f"Demandé {requested:>3} : erreur HTTP {response.status_code}")
            continue
        data = response.json()
        print(
            f"Demandé {requested:>3} -> reçu {len(data.get('results', [])):>3} offres"
            f"  (total disponible chez Adzuna : {data.get('count')})"
        )


if __name__ == "__main__":
    main()
