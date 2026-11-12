"""
bootstrap.py — Le programme du conteneur "loader" (livraison, D10).

RÔLE :
    Au "docker compose up", remplir les bases SI elles sont vides, puis
    s'arrêter. C'est ce que nous avons fait à la main avec load_offers.py
    et index_offers.py ; chez le correcteur et sur le serveur, ce conteneur
    le fait tout seul.

    1. PostgreSQL : la table offers est-elle vide ?
         oui -> charger seed/demo_offers.json (load_offers.load)
         non -> rien à faire (chez nous : 7 298 offres déjà là)
    2. Elasticsearch : l'index contient-il autant de documents que
       PostgreSQL contient d'offres actives ?
         non -> reconstruire l'index, embeddings compris (index_offers.main)
         oui -> rien à faire
    3. Fin : code de sortie 0 = succès.
       docker-compose.yml démarre l'API seulement APRÈS ce succès
       (condition: service_completed_successfully).

POURQUOI « SEULEMENT CE QUI MANQUE » ?
    Le loader se lance à CHAQUE "docker compose up". Sans ces vérifications,
    il recalculerait à chaque fois les embeddings de toutes les offres
    (plusieurs minutes chez nous). Ici, quand tout est déjà en place, il
    s'arrête en une seconde. On dit qu'il est IDEMPOTENT : le lancer une
    ou dix fois donne le même résultat.

EN CAS D'ERREUR :
    load() et index_offers.main() lèvent une erreur : le programme s'arrête
    avec un code non nul, le conteneur est "exited (1)", et l'API ne démarre
    pas. Le message est visible avec : docker compose logs loader
"""

from pathlib import Path

# On RÉUTILISE nos scripts (pas de copie du code) :
from load_offers import connect, count_offers, load
from index_offers import INDEX_NAME, connect_es
from index_offers import main as rebuild_index   # "as" : on la renomme, plus parlant ici

# L'échantillon versionné. Dans le conteneur, le code est dans /app et
# docker-compose.yml monte le fichier dans /seed/ :
#   Path(__file__).resolve().parent.parent -> "/"  ->  /seed/demo_offers.json
# (Chez nous, hors Docker : <racine du projet>/seed/demo_offers.json.)
DEMO_FILE = Path(__file__).resolve().parent.parent / "seed" / "demo_offers.json"

COUNT_ACTIVE_SQL = "SELECT count(*) FROM offers WHERE status = 'active'"


def count_active_offers() -> int:
    """Nombre d'offres ACTIVES : celles que index_offers.py met dans l'index."""
    with connect() as conn:
        return conn.execute(COUNT_ACTIVE_SQL).fetchone()[0]


def count_indexed(es) -> int:
    """Nombre de documents dans l'index Elasticsearch (0 s'il n'existe pas).

    es.indices.exists : l'index existe-t-il ? (au tout premier démarrage, non)
    es.count          : nombre de documents (API _count).
    """
    if not es.indices.exists(index=INDEX_NAME):
        return 0
    return es.count(index=INDEX_NAME)["count"]


def main() -> None:
    # --- 1) PostgreSQL ---
    with connect() as conn, conn.cursor() as cur:
        total = count_offers(cur)

    if total == 0:
        print(f"[loader] Table offers vide : chargement de {DEMO_FILE.name}")
        load(DEMO_FILE)
    else:
        print(f"[loader] PostgreSQL : {total} offres déjà présentes, rien à charger")

    # --- 2) Elasticsearch ---
    active = count_active_offers()
    indexed = count_indexed(connect_es())

    if indexed != active:
        print(f"[loader] Index incomplet ({indexed} / {active}) : reconstruction")
        rebuild_index()
    else:
        print(f"[loader] Elasticsearch : {indexed} / {active} documents, rien à indexer")

    print("[loader] Terminé : les bases sont prêtes.")


if __name__ == "__main__":
    main()
