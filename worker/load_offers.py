"""
load_offers.py — Chargement des offres dans PostgreSQL (module M2).

RÔLE :
    Lire un fichier d'offres au format JobOffer (produit par fetch_offers.py)
    et les enregistrer dans la table "offers" de PostgreSQL.
    Chaque exécution est notée dans la table "ingestion_runs" (le journal).

    Collecte et chargement sont SÉPARÉS (voir docs/decisions.md, D10) :
      - fetch_offers.py : Adzuna -> fichier JSON   (chez nous, avec la clé API)
      - load_offers.py  : fichier JSON -> base     (partout, SANS clé API)
    Le correcteur, le serveur et le futur conteneur "loader" n'ont besoin que
    de ce second script.

IDEMPOTENT :
    Le relancer avec le même fichier ne crée AUCUN doublon : les offres déjà
    connues sont mises à jour (UPSERT). 1er lancement : 7 298 insérées ;
    2e lancement : 0 insérée, 7 298 mises à jour.

LANCEMENT (depuis worker/, venv activé, conteneurs démarrés) :
    python load_offers.py                          # charge seed/offers_sample.json
    python load_offers.py ../seed/autre_fichier.json

CONNEXION :
    Les paramètres sont lus dans .env (POSTGRES_USER, POSTGRES_PASSWORD,
    POSTGRES_DB). Hôte et port par défaut : localhost:5432, c'est-à-dire le
    port que docker-compose.yml publie sur ton PC. Dans un conteneur (étape 7),
    on définira POSTGRES_HOST=postgres (nom du service dans le réseau Docker).
"""

import json               # lire le fichier d'offres
import os                 # os.environ : variables d'environnement (.env)
import sys                # sys.argv : arguments de la ligne de commande
from pathlib import Path  # chemins de fichiers

import psycopg                        # le "pilote" Python de PostgreSQL
from psycopg.types.json import Jsonb  # pour envoyer un dict Python dans une colonne JSONB
from dotenv import load_dotenv        # lit le fichier .env

# Lit .env et place ses valeurs dans os.environ (identifiants PostgreSQL).
load_dotenv()

# Fichier chargé par défaut : <racine du projet>/seed/offers_sample.json
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "seed" / "offers_sample.json"


# ---------------------------------------------------------------------------
# 1. CORRESPONDANCE JobOffer -> COLONNES DE LA TABLE
# ---------------------------------------------------------------------------

def offer_to_row(offer: dict) -> dict:
    """Transforme une offre (dictionnaire JobOffer) en ligne de la table offers.

    Les clés du dictionnaire renvoyé sont les NOMS DES COLONNES SQL : elles
    correspondent aux %(nom)s de la requête UPSERT_SQL plus bas.
    La plupart des champs ont le même nom des deux côtés ; deux diffèrent :
        JobOffer.location   -> colonne location_label (libellé d'affichage)
        JobOffer.created_at -> colonne published_at   (date de publication)
    Aucun nettoyage ici : les données arrivent DÉJÀ propres (régions
    harmonisées, outre-mer, Paris...). Ce travail est fait par l'adaptateur
    de chaque source (sources/adzuna.py), qui seul connaît ses bizarreries.
    Ce script ne fait qu'une chose : enregistrer.
    """
    return {
        "source": offer["source"],
        "source_id": offer["source_id"],
        "title": offer["title"],
        "company": offer["company"],
        "description": offer["description"],
        "url": offer["url"],
        "location_label": offer["location"],          # nom différent
        "region": offer["region"],
        "department": offer["department"],
        "city": offer["city"],
        "latitude": offer["latitude"],
        "longitude": offer["longitude"],
        # Liste Python -> tableau PostgreSQL (TEXT[]) : psycopg convertit seul.
        "contract_types": offer["contract_types"],
        "contract_source": offer["contract_source"],
        "contract_raw": offer["contract_raw"],
        "contract_time": offer["contract_time"],
        "category": offer["category"],
        "search_keywords": offer["search_keywords"],
        "salary_min": offer["salary_min"],
        "salary_max": offer["salary_max"],
        # Texte ISO 8601 ("2026-10-22T06:01:47Z") : PostgreSQL le convertit en TIMESTAMPTZ.
        "published_at": offer["created_at"],         # nom différent
        # Jsonb(...) : indique à psycopg d'envoyer ce dictionnaire en JSONB.
        "raw": Jsonb(offer["raw"]),
    }


# ---------------------------------------------------------------------------
# 2. LES REQUÊTES SQL
# ---------------------------------------------------------------------------
# REQUÊTES PARAMÉTRÉES : la requête contient des emplacements %(nom)s, et les
# valeurs sont envoyées À PART. psycopg les transmet à PostgreSQL de façon
# sûre (guillemets, apostrophes, caractères spéciaux...).
# On n'assemble JAMAIS une requête en collant du texte (f"... '{titre}' ..."):
# un titre contenant une apostrophe ("Développeur d'applications") casserait
# la requête, et un texte malveillant pourrait exécuter du SQL (injection SQL).

# UPSERT : insère l'offre ; si (source, source_id) existe déjà (conflit sur
# la contrainte UNIQUE), met à jour la ligne existante au lieu d'échouer.
#   EXCLUDED = la ligne qu'on ESSAYAIT d'insérer (les nouvelles valeurs).
#   On ne touche pas à : id, first_seen_at (date de 1re découverte), status.
#   last_seen_at = now() : on note qu'on vient de revoir l'offre.
UPSERT_SQL = """
INSERT INTO offers (
    source, source_id, title, company, description, url,
    location_label, region, department, city, latitude, longitude,
    contract_types, contract_source, contract_raw, contract_time,
    category, search_keywords, salary_min, salary_max, published_at, raw
) VALUES (
    %(source)s, %(source_id)s, %(title)s, %(company)s, %(description)s, %(url)s,
    %(location_label)s, %(region)s, %(department)s, %(city)s, %(latitude)s, %(longitude)s,
    %(contract_types)s, %(contract_source)s, %(contract_raw)s, %(contract_time)s,
    %(category)s, %(search_keywords)s, %(salary_min)s, %(salary_max)s, %(published_at)s, %(raw)s
)
ON CONFLICT (source, source_id) DO UPDATE SET
    title           = EXCLUDED.title,
    company         = EXCLUDED.company,
    description     = EXCLUDED.description,
    url             = EXCLUDED.url,
    location_label  = EXCLUDED.location_label,
    region          = EXCLUDED.region,
    department      = EXCLUDED.department,
    city            = EXCLUDED.city,
    latitude        = EXCLUDED.latitude,
    longitude       = EXCLUDED.longitude,
    contract_types  = EXCLUDED.contract_types,
    contract_source = EXCLUDED.contract_source,
    contract_raw    = EXCLUDED.contract_raw,
    contract_time   = EXCLUDED.contract_time,
    category        = EXCLUDED.category,
    search_keywords = EXCLUDED.search_keywords,
    salary_min      = EXCLUDED.salary_min,
    salary_max      = EXCLUDED.salary_max,
    published_at    = EXCLUDED.published_at,
    raw             = EXCLUDED.raw,
    last_seen_at    = now()
"""

# Journal : début d'une exécution. RETURNING id renvoie l'identifiant créé,
# pour pouvoir mettre à jour CETTE ligne à la fin.
START_RUN_SQL = """
INSERT INTO ingestion_runs (source, params)
VALUES (%(source)s, %(params)s)
RETURNING id
"""

# Journal : fin d'une exécution (succès ou échec).
FINISH_RUN_SQL = """
UPDATE ingestion_runs SET
    finished_at     = now(),
    status          = %(status)s,
    offers_received = %(received)s,
    offers_inserted = %(inserted)s,
    offers_updated  = %(updated)s,
    error_message   = %(error)s
WHERE id = %(run_id)s
"""


# ---------------------------------------------------------------------------
# 3. CONNEXION
# ---------------------------------------------------------------------------

def connect() -> psycopg.Connection: #psycopg.Connection: connexion à la base de données.
    """Ouvre une connexion à PostgreSQL avec les paramètres de .env.

    os.environ["X"]          : obligatoire (erreur claire si absent du .env)
    os.environ.get("X", "y") : facultatif, "y" par défaut
    autocommit=True : chaque requête est validée immédiatement, SAUF à
    l'intérieur d'un bloc "with conn.transaction():" (voir load()).
    """
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"), #localhost:5432, c'est-à-dire le port que docker-compose.yml publie sur ton PC. Dans un conteneur (étape 7), on définira POSTGRES_HOST=postgres (nom du service dans le réseau Docker).
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=True, #chaque requête est validée immédiatement, SAUF à l'intérieur d'un bloc "with conn.transaction():" (voir load()).
    )

#x: psycopg.Cursor: curseur pour executer les requêtes.
def count_offers(cur: psycopg.Cursor) -> int:
    """Nombre total de lignes dans la table offers."""
    cur.execute("SELECT count(*) FROM offers")
    # fetchone() renvoie la première ligne du résultat, ici un tuple (7298,).
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# 4. LE CHARGEMENT
# ---------------------------------------------------------------------------

def load(path: Path) -> None:
    """Charge le fichier d'offres dans PostgreSQL et remplit le journal."""

    # Lecture du fichier : une liste de dictionnaires au format JobOffer.
    offers = json.loads(path.read_text(encoding="utf-8")) #dictionnaire d'offre au format JobOffer
    rows = [offer_to_row(o) for o in offers] #liste de dictionnaires au format offer_to_row (colonnes de la table offers)
    print(f"{len(rows)} offres lues dans {path.name}") #nombre d'offres lues dans le fichier

    # Source(s) des offres, lue(s) dans les données plutôt qu'écrite(s) en dur :
    #   {... for r in rows} : compréhension d'ENSEMBLE (set), chaque valeur n'y
    #   figure qu'une fois -> {"adzuna"} ; sorted(...) puis ", ".join(...) -> "adzuna".
    #   Avec plusieurs sources un jour : "adzuna, jooble".
    source_label = ", ".join(sorted({r["source"] for r in rows})) or "inconnue"

    # "with" ferme automatiquement la connexion à la fin, même en cas d'erreur.
    with connect() as conn, conn.cursor() as cur: #conn connection à la base de données, cur curseur pour executer les requêtes. Ferme automatiquement la connexion à la fin, même en cas d'erreur.

        # 1) Journal : on note le début, HORS transaction (autocommit) :
        #    même si le chargement échoue, cette ligne reste et dira pourquoi.
        #cur execute la requête START_RUN_SQL avec les paramètres source et params.
        cur.execute(START_RUN_SQL, {"source": source_label, "params": Jsonb({"file": path.name})}) #source: lue dans les données (ex. "adzuna"), params: dictionnaire avec le nom du fichier.
        #fetchone() renvoie la première ligne du résultat, ici un tuple (1,).
        run_id = cur.fetchone()[0] #run_id est le premier élément du tuple renvoyé par fetchone().

        try: #try catch pour gérer les erreurs.
            # 2) TRANSACTION : tout ce bloc est "tout ou rien".
            #    - pas d'erreur : COMMIT à la sortie du bloc, les offres sont enregistrées ;
            #    - une erreur (même à la 5 000e offre) : ROLLBACK, AUCUNE offre n'est
            #      enregistrée. La base n'est jamais à moitié remplie.
            with conn.transaction():
                # Combien d'insertions / de mises à jour ? Un UPSERT ne le dit pas
                # directement. Astuce : compter les lignes AVANT et APRÈS.
                #   insérées     = après - avant   (les seules nouvelles lignes)
                #   mises à jour = reçues - insérées
                # Fiable ici car un seul chargement tourne à la fois.
                before = count_offers(cur)
                # executemany : exécute la même requête pour chaque ligne de "rows",
                # en les envoyant en lot (beaucoup plus rapide qu'une boucle de execute).
                cur.executemany(UPSERT_SQL, rows)
                after = count_offers(cur)

            inserted = after - before
            updated = len(rows) - inserted

            # 3) Journal : succès et compteurs.
            cur.execute(FINISH_RUN_SQL, {
                "run_id": run_id, "status": "success", "received": len(rows),
                "inserted": inserted, "updated": updated, "error": None,
            })
            print(f"Insérées : {inserted} | mises à jour : {updated} | "
                  f"total en base : {after} (journal : ingestion_runs.id = {run_id})")

        except BaseException as error:
            # 4) Échec : la transaction a déjà été annulée (ROLLBACK).
            #    On note l'erreur dans le journal, puis on la relance ("raise")
            #    pour que le script s'arrête avec le message complet.
            #
            #    BaseException (et pas Exception) : attrape AUSSI l'interruption
            #    par Ctrl+C (KeyboardInterrupt), qui n'est pas une "Exception" en
            #    Python. Sans ça, un Ctrl+C laisserait le journal bloqué sur 'running'.
            #
            #    type(error).__name__ : le nom de l'erreur ("KeyboardInterrupt",
            #    "CheckViolation"...), utile car str(error) est vide pour un Ctrl+C.
            message = f"{type(error).__name__}: {error}"[:1000]
            try:
                cur.execute(FINISH_RUN_SQL, {
                    "run_id": run_id, "status": "failed", "received": len(rows),
                    "inserted": 0, "updated": 0, "error": message,
                })
            except Exception as journal_error:
                # La mise à jour du journal peut elle-même échouer (ex. connexion
                # coupée). On le signale SANS lever d'erreur ici : sinon cette
                # seconde erreur masquerait la vraie cause, relancée juste après.
                print(f"(Journal non mis à jour : {type(journal_error).__name__})")
            print(f"Échec du chargement, aucune offre enregistrée (journal : id = {run_id})")
            raise


if __name__ == "__main__":
    # sys.argv : la liste des mots de la commande.
    #   python load_offers.py              -> sys.argv = ["load_offers.py"]
    #   python load_offers.py fichier.json -> sys.argv = ["load_offers.py", "fichier.json"]
    file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    load(file_path)
