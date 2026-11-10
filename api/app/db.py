"""
db.py — Connexions de l'API aux trois bases de données (module M3).

RÔLE :
    Un seul endroit pour savoir COMMENT joindre PostgreSQL, Redis et
    Elasticsearch. Les routes de l'API (main.py) importent ces fonctions et
    clients au lieu de créer elles-mêmes leurs connexions : si un paramètre
    change, il n'y a qu'un seul fichier à modifier.

PARAMÈTRES LUS DANS L'ENVIRONNEMENT :
    Dans le conteneur "api", docker-compose.yml les définit avec les NOMS DES
    SERVICES du réseau Docker :
        POSTGRES_HOST=postgres, REDIS_HOST=redis, ES_URL=http://elasticsearch:9200
    Les valeurs par défaut (localhost) ne servent que si on lance l'API sur
    le PC, hors Docker.

DEUX FAÇONS DE GÉRER LES CONNEXIONS :
    - PostgreSQL : une FONCTION qui ouvre une connexion à chaque utilisation
      (simple et sûr ; fermée automatiquement avec "with").
    - Redis, Elasticsearch : un CLIENT UNIQUE créé au démarrage et PARTAGÉ par
      toutes les requêtes. Ces clients gèrent en interne un ensemble de
      connexions réutilisées (un "pool") : en recréer un par requête serait
      du gaspillage.
"""

import os  # os.environ : variables d'environnement

import psycopg                     # pilote PostgreSQL
import redis                       # client Redis
from elasticsearch import Elasticsearch  # client Elasticsearch


# ---------------------------------------------------------------------------
# POSTGRESQL : une connexion par utilisation
# ---------------------------------------------------------------------------

def get_pg_connection() -> psycopg.Connection:
    """Ouvre une connexion à PostgreSQL.

    À utiliser avec "with", pour qu'elle soit fermée automatiquement :
        with get_pg_connection() as conn:
            conn.execute("SELECT 1")

    os.environ["X"]          : obligatoire (erreur claire si la variable manque)
    os.environ.get("X", "y") : facultatif, "y" par défaut
    autocommit=True : chaque requête est validée immédiatement, sauf dans un
    bloc "with conn.transaction():" (plusieurs écritures en "tout ou rien").

    Amélioration possible plus tard : un "pool" de connexions (psycopg_pool),
    pour réutiliser les connexions au lieu d'en ouvrir une par requête.
    Inutile pour notre volume.
    """
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=True,
    )


# ---------------------------------------------------------------------------
# REDIS : un seul client, partagé
# ---------------------------------------------------------------------------
# Créer le client NE SE CONNECTE PAS encore : la connexion n'a lieu qu'à la
# première vraie commande. L'API peut donc démarrer même si Redis est
# momentanément indisponible ; la route /health le signalera.
# decode_responses=True : Redis renvoie du texte (str, ex. "en cours") au lieu
# d'octets (bytes, ex. b"en cours"), plus simple à manipuler et à renvoyer en JSON.
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    decode_responses=True,
)


# ---------------------------------------------------------------------------
# ELASTICSEARCH : un seul client, partagé
# ---------------------------------------------------------------------------
# Même principe : le client est préparé ici, la connexion se fait à la
# première requête.
es_client = Elasticsearch(os.environ.get("ES_URL", "http://localhost:9200"))
