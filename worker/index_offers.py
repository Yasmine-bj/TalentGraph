"""
index_offers.py — Indexation des offres dans Elasticsearch (module M2).

RÔLE :
    Copier les offres ACTIVES de PostgreSQL vers l'index "offers"
    d'Elasticsearch, pour pouvoir les RECHERCHER (pertinence, filtres,
    comptages, et plus tard recherche par le sens).

    PostgreSQL reste la SOURCE DE VÉRITÉ (docs/decisions.md, D1) :
    Elasticsearch n'est qu'une copie organisée pour la recherche. Ce script
    peut donc toujours RECONSTRUIRE l'index entièrement à partir de PostgreSQL.

LA CHAÎNE COMPLÈTE :
    fetch_offers.py   Adzuna      -> offers_sample.json   (collecter)
    load_offers.py    JSON        -> PostgreSQL           (enregistrer)
    index_offers.py   PostgreSQL  -> Elasticsearch        (rendre cherchable)  <- CE FICHIER

CE QU'IL FAIT, DANS L'ORDRE :
    1. lire les offres actives dans PostgreSQL ;
    2. SUPPRIMER l'index "offers" s'il existe, puis le RECRÉER avec le mapping
       infra/elasticsearch/offers_mapping.json (reconstruction complète) ;
    3. transformer chaque ligne PostgreSQL en DOCUMENT Elasticsearch ;
    4. envoyer les documents EN LOTS (API _bulk) ;
    5. vérifier : nombre de documents dans l'index = nombre de lignes lues.

POURQUOI RECRÉER L'INDEX À CHAQUE FOIS ?
    - Simple et sûr : l'index est toujours EXACTEMENT le reflet de PostgreSQL
      (une offre expirée ou supprimée disparaît d'elle-même) ;
    - le mapping peut avoir changé (ajout du vecteur à l'étape 6) ;
    - c'est rapide : ~7 300 offres en quelques secondes.
    Inconvénient : pendant ces quelques secondes, l'index est vide ou partiel.
    Acceptable pour notre projet (une technique "d'alias" l'éviterait en production).

LANCEMENT (depuis worker/, venv activé, conteneurs démarrés, offres déjà
chargées dans PostgreSQL par load_offers.py) :
    python index_offers.py

CONNEXIONS :
    - PostgreSQL : même fonction connect() que load_offers.py (paramètres de .env).
    - Elasticsearch : variable ES_URL, par défaut http://localhost:9200 (le port
      publié sur ton PC). Dans un conteneur, on définira ES_URL=http://elasticsearch:9200
      (nom du service dans le réseau Docker), comme POSTGRES_HOST pour PostgreSQL.
"""

import json               # lire le fichier de mapping
import os                 # os.environ : variables d'environnement
from pathlib import Path  # chemins de fichiers

from elasticsearch import Elasticsearch, helpers  # client officiel + outils (bulk)
from psycopg.rows import dict_row                 # lignes PostgreSQL sous forme de dictionnaires

# On RÉUTILISE la connexion PostgreSQL de load_offers.py, plutôt que de la
# réécrire : un seul endroit à modifier si les paramètres changent.
# (Importer load_offers exécute aussi son load_dotenv() : .env est donc lu.
#  Son chargement, lui, ne se lance pas : il est protégé par
#  "if __name__ == '__main__'".)
from load_offers import connect

# Le modèle d'embeddings (voir embeddings.py) : transforme un texte en vecteur de sens.
from embeddings import EMBEDDING_DIMS, embed_passages

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

# Nom de l'index Elasticsearch (l'équivalent du nom de la table).
INDEX_NAME = "offers"

# Fichier du mapping : <racine du projet>/infra/elasticsearch/offers_mapping.json
#   Path(__file__).resolve().parent        -> worker/
#   .parent                                -> racine du projet
MAPPING_FILE = (
    Path(__file__).resolve().parent.parent / "infra" / "elasticsearch" / "offers_mapping.json"
)

# Nombre de documents envoyés par requête _bulk.
# Trop petit : beaucoup d'allers-retours réseau (lent).
# Trop grand : des requêtes énormes en mémoire (nos documents font ~1 Ko,
# 500 documents ~ 0,5 Mo par requête : un bon compromis).
BULK_CHUNK_SIZE = 500

# Colonnes lues dans PostgreSQL : uniquement celles utiles à Elasticsearch
# (voir infra/elasticsearch/README.md). raw, contract_raw, first_seen_at...
# restent dans PostgreSQL.
SELECT_SQL = """
SELECT
    id, source, source_id, title, description, company,
    region, department, city, latitude, longitude, location_label,
    contract_types, contract_source, contract_time,
    category, search_keywords, salary_min, salary_max, published_at, url
FROM offers
WHERE status = 'active'
ORDER BY id
"""


# ---------------------------------------------------------------------------
# 1. CONNEXION À ELASTICSEARCH
# ---------------------------------------------------------------------------

def connect_es() -> Elasticsearch:
    """Crée le client Elasticsearch et vérifie que le serveur répond.

    Elasticsearch(url) ne se connecte pas tout de suite : il prépare le client.
    es.info() envoie une vraie requête (GET /, notre "es GET /" du labo) :
    si le serveur ne répond pas, l'erreur arrive ICI, avec un message clair,
    plutôt qu'au milieu de l'indexation.
    """
    url = os.environ.get("ES_URL", "http://localhost:9200")
    es = Elasticsearch(url)
    info = es.info()
    print(f"Elasticsearch {info['version']['number']} joint sur {url}")
    return es


# ---------------------------------------------------------------------------
# 2. LECTURE DANS POSTGRESQL
# ---------------------------------------------------------------------------

def read_offers() -> list[dict]:
    """Lit les offres actives dans PostgreSQL.

    row_factory=dict_row : chaque ligne est renvoyée sous forme de
    DICTIONNAIRE ({"id": 42, "title": "..."}) au lieu d'un tuple
    ((42, "...")). On accède ainsi aux colonnes par leur NOM, ce qui est
    plus lisible et ne dépend pas de l'ordre des colonnes.

    fetchall() : toutes les lignes du résultat (fetchone() n'en lit qu'une).
    ~7 300 offres sans la colonne raw : quelques Mo en mémoire, sans problème.
    """
    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(SELECT_SQL)
        rows = cur.fetchall()
    print(f"{len(rows)} offres actives lues dans PostgreSQL")
    return rows


# ---------------------------------------------------------------------------
# 3. (RE)CRÉATION DE L'INDEX
# ---------------------------------------------------------------------------

def recreate_index(es: Elasticsearch) -> None:
    """Supprime l'index s'il existe, puis le recrée avec notre mapping.

    Équivalent de ce qu'on a fait à la main dans le labo :
        DELETE /offers
        PUT    /offers   + le contenu de offers_mapping.json
    """
    # Lecture du mapping : un dictionnaire {"settings": {...}, "mappings": {...}}
    body = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))

    # es.indices : la partie du client qui gère les INDEX (créer, supprimer...).
    # ignore_unavailable=True : pas d'erreur si l'index n'existe pas encore
    # (premier lancement).
    es.indices.delete(index=INDEX_NAME, ignore_unavailable=True)

    # settings=... et mappings=... : les deux parties du fichier, passées
    # séparément (c'est ce qu'attend le client Python).
    es.indices.create(index=INDEX_NAME, settings=body["settings"], mappings=body["mappings"])
    print(f"Index '{INDEX_NAME}' (re)créé avec {MAPPING_FILE.name}")


# ---------------------------------------------------------------------------
# 4. TRANSFORMATION : ligne PostgreSQL -> document Elasticsearch
# ---------------------------------------------------------------------------

def offer_text(row: dict) -> str:
    """Texte d'une offre utilisé pour son embedding : titre + description.

    Le titre seul est trop court ("Data Engineer F/H") ; la description apporte
    les technologies et le contexte. ~500 caractères au total, bien en dessous
    de la limite du modèle (512 tokens) : tout le texte est lu.
    Le préfixe "passage: " est ajouté par embed_passages(), pas ici.
    Isolé dans une fonction : un seul endroit à modifier si on veut un jour
    y ajouter l'entreprise ou la ville.
    """
    return f"{row['title']}. {row['description']}"


def row_to_document(row: dict) -> dict:
    """Transforme une ligne de la table offers en document pour l'index offers.

    Trois adaptations par rapport à la ligne PostgreSQL :
      1. latitude + longitude -> UN champ "location" de type geo_point
         ({"lat": ..., "lon": ...}), seulement si les deux sont connues ;
      2. salary_min / salary_max : PostgreSQL renvoie des Decimal (NUMERIC,
         nombres exacts) -> convertis en float (type du mapping) ;
      3. les valeurs vides (None) sont RETIRÉES du document : un champ absent
         est plus propre qu'un champ "null" (et prend moins de place).
    L'id PostgreSQL n'est PAS dans le document : il devient l'identifiant
    du document (_id), voir build_actions().
    published_at est un objet datetime Python : le client Elasticsearch le
    convertit seul en texte ISO 8601 ("2026-10-22T06:01:47+00:00").
    """
    document = {
        "source": row["source"],
        "source_id": row["source_id"],
        "title": row["title"],
        "description": row["description"],
        "company": row["company"],
        "region": row["region"],
        "department": row["department"],
        "city": row["city"],
        "location_label": row["location_label"],
        # Liste Python (tableau PostgreSQL) -> champ keyword à plusieurs valeurs.
        "contract_types": row["contract_types"],
        "contract_source": row["contract_source"],
        "contract_time": row["contract_time"],
        "category": row["category"],
        "search_keywords": row["search_keywords"],
        # "x if condition else y" : expression conditionnelle sur une ligne.
        "salary_min": float(row["salary_min"]) if row["salary_min"] is not None else None,
        "salary_max": float(row["salary_max"]) if row["salary_max"] is not None else None,
        "published_at": row["published_at"],
        "url": row["url"],
    }

    # geo_point : seulement si latitude ET longitude sont connues
    # (~9 % des offres n'ont pas de coordonnées).
    if row["latitude"] is not None and row["longitude"] is not None:
        document["location"] = {"lat": row["latitude"], "lon": row["longitude"]}

    # Compréhension de dictionnaire : on garde uniquement les champs non vides.
    return {key: value for key, value in document.items() if value is not None}


def build_actions(rows: list[dict], vectors: list[list[float]]):
    """Produit les "actions" à envoyer à l'API _bulk, une par offre.

    Une action dit à Elasticsearch : "range CE document, dans CET index,
    sous CET identifiant". Format attendu par helpers.bulk :
        {"_index": "offers", "_id": 42, "_source": {...le document...}}

    _id = id PostgreSQL : le document 42 d'Elasticsearch EST la ligne 42 de
    PostgreSQL. Réindexer remplace le document au lieu d'en créer un doublon.

    "yield" fait de cette fonction un GÉNÉRATEUR : elle produit les actions
    UNE PAR UNE, au fur et à mesure que helpers.bulk les demande, au lieu de
    construire d'abord une liste de 7 300 actions en mémoire.

    vectors : les embeddings, DANS LE MÊME ORDRE que rows (vectors[i] est le
    vecteur de rows[i]). zip(rows, vectors) parcourt les deux listes ENSEMBLE,
    élément par élément, comme une fermeture éclair :
        (offre 1, vecteur 1), (offre 2, vecteur 2), ...
    """
    for row, vector in zip(rows, vectors):
        document = row_to_document(row)
        # Champ dense_vector du mapping : 384 nombres, le sens de l'offre.
        document["embedding"] = vector
        yield {
            "_index": INDEX_NAME,
            "_id": row["id"],
            "_source": document,
        }
    
    """Une action dit à Elasticsearch : « range ce document (_source), dans cet index (_index),
     sous cet identifiant (_id) ». C’est l’équivalent de ton PUT /demo/_doc/123.
    """

# ---------------------------------------------------------------------------
# 5. LE PROGRAMME PRINCIPAL
# ---------------------------------------------------------------------------

def main() -> None:
    """Reconstruit l'index offers à partir de PostgreSQL."""
    es = connect_es()
    rows = read_offers()

    # Embeddings de toutes les offres, en une fois (par lots de 64, avec une
    # barre de progression). C'est le plus long du script : quelques minutes
    # sur CPU. On les calcule AVANT de recréer l'index : si le calcul échoue
    # (mémoire, modèle introuvable...), l'ancien index reste intact au lieu
    # d'être supprimé pour rien.
    print(f"Calcul des embeddings ({EMBEDDING_DIMS} dimensions) de {len(rows)} offres...")
    vectors = embed_passages([offer_text(row) for row in rows])

    recreate_index(es)

    # helpers.bulk : envoie les actions par paquets de BULK_CHUNK_SIZE à l'API
    # _bulk (une requête HTTP = 500 documents, au lieu d'une requête par
    # document : environ 15 requêtes au lieu de 7 300).
    #   raise_on_error=False : ne pas s'arrêter au premier document refusé,
    #   mais renvoyer la liste des erreurs, pour les afficher toutes.
    # Renvoie un tuple (nombre de succès, liste des erreurs) : on le "déballe".
    success, errors = helpers.bulk(
        es,
        build_actions(rows, vectors),
        chunk_size=BULK_CHUNK_SIZE,
        raise_on_error=False,
    )

    # Rafraîchir l'index : rendre les documents CHERCHABLES tout de suite.
    # Par défaut, Elasticsearch ne le fait qu'environ une fois par seconde
    # (le "presque temps réel" vu dans le labo) : sans ça, le comptage
    # ci-dessous pourrait renvoyer moins que le total.
    es.indices.refresh(index=INDEX_NAME)

    # Vérification : combien de documents dans l'index ? (API _count)
    count = es.count(index=INDEX_NAME)["count"]
    print(f"Indexés : {success} | refusés : {len(errors)} | "
          f"documents dans '{INDEX_NAME}' : {count} / {len(rows)}")

    # Afficher les 5 premières erreurs, s'il y en a (ex. un champ non déclaré
    # dans le mapping, refusé à cause de "dynamic": "strict").
    for error in errors[:5]:
        print("  Erreur :", error)

    # Code de sortie non nul si quelque chose ne va pas : utile plus tard,
    # quand ce script tournera automatiquement dans un conteneur.
    if errors or count != len(rows):
        raise SystemExit("Indexation incomplète : voir les erreurs ci-dessus.")


if __name__ == "__main__":
    main()
