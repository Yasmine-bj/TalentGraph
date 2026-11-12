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
    GET  /health             : vérifie que l'API joint les trois bases.
    POST /api/searches       : enregistre le formulaire (candidat + demande)
                               dans PostgreSQL, et le statut dans Redis,
                               puis lance le traitement en arrière-plan (M4).
    GET  /api/searches/{id}  : relit une demande (PostgreSQL) et son statut
                               en direct (Redis).
    POST /api/search/preview : TESTE la recherche hybride (Elasticsearch),
                               sans rien enregistrer (M4).
    GET  /api/regions        : liste des régions acceptées (liste déroulante
                               du formulaire, M4).

DOCUMENTATION AUTOMATIQUE (générée par FastAPI) :
    http://localhost:8000/docs  -> liste des routes, avec un bouton pour les tester
"""

from datetime import datetime, timezone
from typing import get_args  # get_args(Literal["a", "b"]) -> ("a", "b")

from fastapi import BackgroundTasks, FastAPI, HTTPException  # BackgroundTasks : M4, étape 5
from fastapi.responses import JSONResponse  # réponse JSON avec un code HTTP choisi
from psycopg.rows import dict_row           # lignes PostgreSQL en dictionnaires
from psycopg.types.json import Jsonb        # dict Python -> JSON pour une colonne JSONB (M4)

# Connexions aux bases (voir db.py). "app.db" = le fichier app/db.py.
from app.db import es_client, get_pg_connection, redis_client
# Forme des données reçues et renvoyées (voir schemas.py).
from app.schemas import OfferResult, Region, SearchCreate, SearchCreated, SearchOut, SearchQuery
# Recherche hybride BM25 + kNN + RRF (voir search.py).
from app.search import hybrid_search

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


# ---------------------------------------------------------------------------
# REDIS : noms des clés et durée de vie
# ---------------------------------------------------------------------------
# Convention de nommage Redis : "objet:identifiant", avec des ":".
#   search:12          -> HASH  : statut en direct de la demande 12
#   searches:recent    -> LIST  : identifiants des dernières demandes (récentes en tête)
#   stats:searches_total -> STRING (compteur) : nombre total de demandes reçues
RECENT_SEARCHES_KEY = "searches:recent"
SEARCHES_TOTAL_KEY = "stats:searches_total"
RECENT_SEARCHES_MAX = 50                 # on ne garde que les 50 dernières
SEARCH_STATUS_TTL = 7 * 24 * 3600        # le statut en direct expire après 7 jours


def search_key(search_id: int) -> str:
    """Nom de la clé Redis du statut d'une demande, ex. "search:12"."""
    return f"search:{search_id}"


# ---------------------------------------------------------------------------
# REQUÊTES SQL (paramétrées, jamais de valeurs collées dans le texte)
# ---------------------------------------------------------------------------

# UPSERT du candidat : même email = même personne -> on met à jour sa fiche.
#   COALESCE(a, b) : a s'il n'est pas NULL, sinon b. Si le formulaire n'envoie
#   pas de CV, on GARDE l'ancien au lieu de l'effacer.
#   RETURNING id : PostgreSQL renvoie l'identifiant (nouveau ou existant).
UPSERT_CANDIDATE_SQL = """
INSERT INTO candidates (full_name, email, cv_text)
VALUES (%(full_name)s, %(email)s, %(cv_text)s)
ON CONFLICT (email) DO UPDATE SET
    full_name  = EXCLUDED.full_name,
    cv_text    = COALESCE(EXCLUDED.cv_text, candidates.cv_text),
    updated_at = now()
RETURNING id
"""

# Nouvelle demande. status, created_at... prennent leur valeur par défaut.
INSERT_SEARCH_SQL = """
INSERT INTO searches (candidate_id, mode, job_title, region, contract_types, salary_min)
VALUES (%(candidate_id)s, %(mode)s, %(job_title)s, %(region)s, %(contract_types)s, %(salary_min)s)
RETURNING id, status
"""

SELECT_SEARCH_SQL = """
SELECT id, candidate_id, mode, job_title, region, contract_types, salary_min,
       status, results, error_message, created_at, finished_at
FROM searches
WHERE id = %(id)s
"""


# ---------------------------------------------------------------------------
# MISE À JOUR DU STATUT D'UNE DEMANDE (M4, étape 5)
# ---------------------------------------------------------------------------
# Une demande avance : pending -> running -> done (ou failed).
# À chaque changement, on écrit PostgreSQL PUIS Redis, comme dans
# create_search (même règle qu'au M3) :
#   - PostgreSQL d'abord : c'est la source de vérité ;
#   - Redis ensuite : statut "en direct", relu souvent par la page web.

# Mise à jour de la demande dans PostgreSQL.
#   COALESCE(%(results)s, results) : si on n'envoie pas de résultats (None,
#     ex. passage à "running"), on GARDE la valeur actuelle au lieu de l'effacer.
#   CASE WHEN ... THEN now() ELSE NULL END : finished_at reçoit l'heure
#     actuelle seulement quand la demande est TERMINÉE (done ou failed).
#   RETURNING id : permet de savoir si la demande existait (sinon, aucune ligne).
UPDATE_SEARCH_STATUS_SQL = """
UPDATE searches SET
    status        = %(status)s,
    results       = COALESCE(%(results)s, results),
    error_message = %(error_message)s,
    finished_at   = CASE WHEN %(status)s IN ('done', 'failed') THEN now() ELSE NULL END
WHERE id = %(id)s
RETURNING id
"""


def update_search_status(
    search_id: int,
    status: str,
    results: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Change le statut d'une demande : PostgreSQL, puis Redis.

    status        : "running", "done" ou "failed" ;
    results       : les résultats (pour "done"), ex. {"offers": [...]} ;
    error_message : l'explication (pour "failed").

    Jsonb(results) : indique à psycopg d'envoyer le dictionnaire Python
    comme du JSON, pour la colonne JSONB "results". À la lecture, psycopg
    fait l'inverse tout seul (JSONB -> dict Python).
    """
    # 1) POSTGRESQL (la source de vérité).
    with get_pg_connection() as conn:
        row = conn.execute(UPDATE_SEARCH_STATUS_SQL, {
            "id": search_id,
            "status": status,
            "results": Jsonb(results) if results is not None else None,
            "error_message": error_message,
        }).fetchone()

    # Aucune ligne modifiée : la demande n'existe pas (supprimée entre-temps ?).
    # On le signale dans les logs et on s'arrête : rien à écrire dans Redis.
    if row is None:
        print(f"[status] demande {search_id} introuvable, statut {status} ignoré")
        return

    # 2) REDIS (le statut en direct), APRÈS PostgreSQL.
    #    Même règle qu'au M3 : si Redis est en panne, ce n'est pas grave,
    #    GET /api/searches/{id} relira le statut dans PostgreSQL.
    #    EXPIRE à nouveau : la clé vit 7 jours à partir de la DERNIÈRE mise à jour.
    try:
        pipe = redis_client.pipeline(transaction=True)
        pipe.hset(search_key(search_id), mapping={
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        pipe.expire(search_key(search_id), SEARCH_STATUS_TTL)
        pipe.execute()
    except Exception as error:
        print(f"[redis] statut {status} de la demande {search_id} non enregistré : {type(error).__name__}")


# ---------------------------------------------------------------------------
# LA TÂCHE DE FOND : traiter une demande (M4, étape 5)
# ---------------------------------------------------------------------------
# Lancée par POST /api/searches APRÈS l'envoi de la réponse (BackgroundTasks).
# Elle fait avancer la demande : running -> done (ou failed).

def run_search(search_id: int, search: SearchCreate) -> None:
    """Traite une demande en arrière-plan et enregistre son résultat.

    Mode "offers" : recherche hybride (search.py), puis les offres trouvées
    sont enregistrées dans searches.results sous la forme {"offers": [...]}.
    Modes "skills", "cv", "letter" : pas encore disponibles (agents IA, M5).

    Elle reçoit le formulaire déjà validé ("search"), transmis par
    create_search : inutile de relire la demande dans PostgreSQL (une
    jointure candidates + searches). Possible car BackgroundTasks s'exécute
    dans le MÊME programme ; avec un worker séparé (file de tâches), on ne
    transmettrait que search_id et il relirait la base.

    RÈGLE : quoi qu'il arrive, la demande ne doit JAMAIS rester bloquée en
    "running". Toute erreur la fait passer en "failed", avec un message.
    """
    # Modes pas encore faits : on termine tout de suite, avec une explication.
    if search.mode != "offers":
        update_search_status(
            search_id, "failed",
            error_message=f"Le mode « {search.mode} » sera disponible au M5 (agents IA).",
        )
        return

    try:
        update_search_status(search_id, "running")

        offers = hybrid_search(
            es_client,
            cv_text=search.cv_text,
            job_title=search.job_title,
            region=search.region,
            contract_types=search.contract_types,
            salary_min=search.salary_min,
        )

        # OfferResult(**offer) : vérifie chaque offre (même format que la
        # route preview). model_dump(mode="json") : la retransforme en
        # dictionnaire dont les valeurs sont toutes compatibles JSON (les
        # dates deviennent du texte), sinon Jsonb ne saurait pas l'écrire.
        results = {"offers": [OfferResult(**offer).model_dump(mode="json") for offer in offers]}
        update_search_status(search_id, "done", results=results)

    except Exception as error:
        # Erreur pendant la recherche (Elasticsearch en panne, modèle...) :
        # détail complet dans les logs, message court dans la base.
        print(f"[run_search] demande {search_id} en échec : {error!r}")
        try:
            update_search_status(
                search_id, "failed",
                error_message=f"Erreur pendant la recherche : {type(error).__name__}",
            )
        except Exception as error2:
            # Même PostgreSQL est injoignable : on ne peut que le noter.
            print(f"[run_search] statut failed non enregistré : {error2!r}")


# ---------------------------------------------------------------------------
# ROUTE POST /api/searches : enregistrer le formulaire
# ---------------------------------------------------------------------------
# status_code=201 : "Created", le code HTTP standard quand on CRÉE quelque chose.
# response_model=SearchCreated : la réponse aura exactement cette forme
# (et elle est documentée dans /docs).
# "search: SearchCreate" : FastAPI VALIDE le corps JSON avec ce modèle AVANT
# d'appeler la fonction. Données invalides -> réponse 422 automatique,
# et cette fonction n'est jamais exécutée.

@app.post("/api/searches", status_code=201, response_model=SearchCreated)
def create_search(search: SearchCreate, background_tasks: BackgroundTasks):
    """Enregistre une demande : candidat + demande dans PostgreSQL, statut dans
    Redis, puis programme son traitement en arrière-plan (M4)."""
    # background_tasks (M4, étape 5) : ne vient PAS du formulaire. En voyant
    # le type BackgroundTasks, FastAPI fournit automatiquement une liste de
    # tâches à exécuter APRÈS l'envoi de la réponse.

    # 1) POSTGRESQL (la source de vérité), dans UNE transaction :
    #    candidat ET demande sont enregistrés ensemble, ou pas du tout.
    with get_pg_connection() as conn, conn.cursor() as cur:
        with conn.transaction():
            cur.execute(UPSERT_CANDIDATE_SQL, {
                "full_name": search.full_name.strip(),
                "email": search.email.lower(),   # même email, quelle que soit la casse
                "cv_text": search.cv_text,
            })
            candidate_id = cur.fetchone()[0]

            cur.execute(INSERT_SEARCH_SQL, {
                "candidate_id": candidate_id,
                "mode": search.mode,
                "job_title": search.job_title,
                "region": search.region,
                "contract_types": search.contract_types,
                "salary_min": search.salary_min,
            })
            search_id, status = cur.fetchone()

    # 2) REDIS (le rapide et le temporaire), APRÈS la validation PostgreSQL.
    #    Un "pipeline" envoie toutes les commandes en UN aller-retour réseau ;
    #    transaction=True : elles sont appliquées ensemble (MULTI / EXEC).
    #    Si Redis est indisponible, la demande est QUAND MÊME enregistrée
    #    (PostgreSQL fait foi) : on le signale dans les logs sans faire
    #    échouer la requête. La lecture retombera sur le statut PostgreSQL.
    now = datetime.now(timezone.utc).isoformat()
    try:
        pipe = redis_client.pipeline(transaction=True)
        # HSET : écrit plusieurs champs d'un hash -> statut en direct de la demande.
        pipe.hset(search_key(search_id), mapping={
            "status": status,
            "mode": search.mode,
            "candidate_id": candidate_id,
            "updated_at": now,
        })
        # EXPIRE : la clé disparaîtra d'elle-même après 7 jours.
        pipe.expire(search_key(search_id), SEARCH_STATUS_TTL)
        # LPUSH : ajoute l'identifiant EN TÊTE de la liste des demandes récentes...
        pipe.lpush(RECENT_SEARCHES_KEY, search_id)
        # ...LTRIM : puis ne garde que les 50 premiers éléments (indices 0 à 49).
        pipe.ltrim(RECENT_SEARCHES_KEY, 0, RECENT_SEARCHES_MAX - 1)
        # INCR : ajoute 1 au compteur total (créé à 0 s'il n'existe pas).
        pipe.incr(SEARCHES_TOTAL_KEY)
        pipe.execute()
    except Exception as error:
        print(f"[redis] statut de la demande {search_id} non enregistré : {type(error).__name__}")

    # 3) TÂCHE DE FOND (M4, étape 5) : la recherche est PROGRAMMÉE, pas
    #    exécutée tout de suite. FastAPI envoie d'abord la réponse 201
    #    ("pending") au navigateur, PUIS exécute run_search(search_id, search).
    #    La page web suit l'avancement avec GET /api/searches/{id}.
    #    Placé APRÈS l'enregistrement : si PostgreSQL a échoué, on n'arrive
    #    jamais ici, et aucune tâche n'est lancée pour une demande inexistante.
    background_tasks.add_task(run_search, search_id, search)

    return SearchCreated(id=search_id, candidate_id=candidate_id, status=status)


# ---------------------------------------------------------------------------
# ROUTE GET /api/searches/{search_id} : relire une demande
# ---------------------------------------------------------------------------
# {search_id} dans l'adresse est un PARAMÈTRE DE CHEMIN : pour
# GET /api/searches/12, FastAPI appelle get_search(search_id=12).
# L'annotation "int" fait vérifier que c'est bien un nombre
# (/api/searches/abc -> 422 automatique).

@app.get("/api/searches/{search_id}", response_model=SearchOut)
def get_search(search_id: int):
    """Renvoie une demande : données de PostgreSQL + statut en direct de Redis."""

    # 1) PostgreSQL : la demande elle-même (dict_row : colonnes par leur nom).
    with get_pg_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(SELECT_SEARCH_SQL, {"id": search_id})
        row = cur.fetchone()

    # fetchone() renvoie None si aucune ligne : la demande n'existe pas.
    # HTTPException(404) : FastAPI répond "404 Not Found" avec ce message.
    if row is None:
        raise HTTPException(status_code=404, detail=f"Demande {search_id} introuvable")

    # 2) Redis : le statut EN DIRECT, s'il existe (HGET lit un champ du hash).
    #    Sinon (clé expirée, Redis indisponible), on garde celui de PostgreSQL.
    try:
        live_status = redis_client.hget(search_key(search_id), "status")
        if live_status:
            row["status"] = live_status
    except Exception as error:
        print(f"[redis] statut de la demande {search_id} non lu : {type(error).__name__}")

    # NUMERIC (Decimal) -> float, comme déclaré dans SearchOut.
    if row["salary_min"] is not None:
        row["salary_min"] = float(row["salary_min"])

    # SearchOut(**row) : crée le modèle à partir du dictionnaire ("déballé").
    return SearchOut(**row)


# ---------------------------------------------------------------------------
# ROUTE POST /api/search/preview : tester la recherche hybride (M4)
# ---------------------------------------------------------------------------
# Une route de TEST : elle renvoie directement les offres trouvées, sans
# enregistrer de candidat ni de demande. Elle sert à vérifier et régler la
# recherche depuis /docs. (À l'étape 5, le mode 1 de POST /api/searches
# appellera la même fonction hybrid_search, puis enregistrera le résultat.)
#
# Le verbe est POST et non GET : on envoie un CORPS JSON (le CV peut faire
# des milliers de caractères, trop long pour une adresse).
# response_model=list[OfferResult] : la réponse est une LISTE d'offres.

@app.post("/api/search/preview", response_model=list[OfferResult])
def preview_search(query: SearchQuery):
    """Recherche hybride (mots + sens) dans les offres, sans enregistrement."""
    try:
        results = hybrid_search(
            es_client,
            cv_text=query.cv_text,
            job_title=query.job_title,
            region=query.region,
            contract_types=query.contract_types,
            salary_min=query.salary_min,
        )
    except Exception as error:
        # Elasticsearch indisponible, index absent... : 503 avec le TYPE de
        # l'erreur seulement (même règle que /health), le détail dans les logs.
        print(f"[search] recherche impossible : {error!r}")
        raise HTTPException(status_code=503, detail=f"Recherche indisponible : {type(error).__name__}")

    # Chaque dictionnaire devient un OfferResult (validé et documenté).
    return [OfferResult(**offer) for offer in results]


# ---------------------------------------------------------------------------
# ROUTE GET /api/regions : les régions du formulaire (M4)
# ---------------------------------------------------------------------------
# Ajoutée au M4, après les tests : la région est maintenant une LISTE FERMÉE
# (Region, dans schemas.py). Le formulaire React (M7) appellera cette route
# pour construire sa liste déroulante, au lieu de recopier les 19 régions
# en JavaScript : la liste n'existe qu'à UN endroit (schemas.py), et le
# formulaire ne peut pas proposer une région que l'API refuserait.
# Pas de base de données ici : la liste est dans le code.

@app.get("/api/regions", response_model=list[str])
def list_regions():
    """Régions acceptées par le champ "region" (pour la liste déroulante)."""
    # get_args(Region) lit les valeurs écrites dans Literal[...] (un tuple) ;
    # list(...) le transforme en liste, renvoyée en JSON.
    return list(get_args(Region))
