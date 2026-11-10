"""
main.py — L'application FastAPI de TalentGraph (module M3).

RÔLE :
    Créer l'application et déclarer ses ROUTES. Une route = une adresse + un
    verbe HTTP + une fonction Python qui produit la réponse.
    Uvicorn (le serveur web) la lance grâce au Dockerfile :
        uvicorn app.main:app   ->  fichier app/main.py, variable "app"

    Uvicorn gère le RÉSEAU (port 8000, requêtes HTTP, connexions simultanées) ;
    FastAPI gère la LOGIQUE (quelle fonction pour quelle adresse, validation).

ROUTES ACTUELLES :
    GET /health : vérifie que l'API joint les trois bases.

DOCUMENTATION AUTOMATIQUE (générée par FastAPI) :
    http://localhost:8000/docs  -> liste des routes, avec un bouton pour les tester
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse  # réponse JSON avec un code HTTP choisi

# Connexions aux bases (voir db.py). "app.db" = le fichier app/db.py.
from app.db import es_client, get_pg_connection, redis_client

# ---------------------------------------------------------------------------
# L'APPLICATION
# ---------------------------------------------------------------------------
# C'est CETTE variable qu'Uvicorn cherche ("app.main:app").
# title, description et version s'affichent en haut de la page /docs.
app = FastAPI(
    title="TalentGraph API",
    description="Copilote carrière : CV ↔ offres d'emploi réelles.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# VÉRIFICATIONS DE SANTÉ : une fonction par base
# ---------------------------------------------------------------------------
# Chacune envoie la requête la PLUS LÉGÈRE possible. Si la base répond, la
# fonction renvoie "ok" ; si elle est injoignable, la bibliothèque lève une
# exception (attrapée dans health() plus bas).

def check_postgres() -> str:
    """SELECT 1 : une requête qui ne lit aucune table, juste pour tester la connexion."""
    with get_pg_connection() as conn:   # "with" : connexion fermée automatiquement
        conn.execute("SELECT 1")
    return "ok"


def check_redis() -> str:
    """PING : Redis répond PONG (ping() renvoie True)."""
    redis_client.ping()
    return "ok"


def check_elasticsearch() -> str:
    """GET / : l'équivalent du « es GET / » du labo (nom et version du serveur)."""
    es_client.info()
    return "ok"


# ---------------------------------------------------------------------------
# ROUTE GET /health
# ---------------------------------------------------------------------------
# @app.get("/health") est un DÉCORATEUR : il "accroche" la fonction health()
# à l'adresse /health avec le verbe GET. Quand Uvicorn reçoit
# "GET /health", FastAPI appelle health() et renvoie son résultat en JSON.

@app.get("/health")
def health():
    """Santé de l'application : chaque base est-elle joignable ?

    Exemple de réponse :
        {"postgres": "ok", "redis": "ok", "elasticsearch": "ok"}           -> code 200
        {"postgres": "ok", "redis": "ok", "elasticsearch": "erreur : ..."} -> code 503
    """
    # En Python, une fonction est un objet comme un autre : on peut la ranger
    # dans un dictionnaire et l'appeler plus tard avec check().
    checks = {
        "postgres": check_postgres,
        "redis": check_redis,
        "elasticsearch": check_elasticsearch,
    }

    status = {}
    for name, check in checks.items():
        try:
            status[name] = check()
        except Exception as error:
            # On note seulement le TYPE de l'erreur (ex. "ConnectionError") :
            # le message complet peut contenir des informations internes
            # (adresses, utilisateur) qu'une route publique ne doit pas exposer.
            # Et on CONTINUE avec les autres bases : on veut savoir lesquelles
            # marchent, pas s'arrêter à la première panne.
            status[name] = f"erreur : {type(error).__name__}"

    # all(...) : True si TOUTES les valeurs valent "ok".
    all_ok = all(value == "ok" for value in status.values())

    # Code HTTP : 200 (OK) si tout va bien, 503 (Service Unavailable) sinon.
    # Les outils automatiques (healthcheck Docker, serveur VPS) ne lisent pas
    # le JSON : ils regardent seulement ce code.
    return JSONResponse(content=status, status_code=200 if all_ok else 503)
