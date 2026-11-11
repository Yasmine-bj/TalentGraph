"""
schemas.py — La forme des données échangées par l'API (module M3).

RÔLE :
    Décrire, avec Pydantic, EXACTEMENT ce que l'API accepte et renvoie.
    FastAPI s'en sert pour :
      1. VALIDER chaque requête AVANT d'appeler notre fonction : une donnée
         invalide est refusée avec le code 422 et le détail du champ en faute ;
      2. CONVERTIR le JSON reçu en objet Python (avec les bons types) ;
      3. DOCUMENTER automatiquement la page /docs (champs, types, exemples).

    Ce sont les mêmes règles que les contraintes CHECK de PostgreSQL
    (infra/postgres/init/02_candidates.sql), appliquées UNE COUCHE PLUS TÔT :
    l'utilisateur reçoit un message clair, et la base ne reçoit que des
    données déjà propres. Les contraintes de la base restent le dernier rempart.

DEUX FAMILLES DE MODÈLES :
    - ce que l'API REÇOIT  (SearchCreate, SearchQuery) : les données envoyées ;
    - ce que l'API RENVOIE (SearchCreated, SearchOut, OfferResult) : les réponses.
"""

from datetime import datetime
from typing import Literal  # Literal["a", "b"] : uniquement ces valeurs exactes

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Les valeurs autorisées (listes fermées), réutilisées dans les modèles.
# Literal[...] : le champ ne peut valoir QUE l'une de ces chaînes.
# ---------------------------------------------------------------------------
# Les 4 modes de TalentGraph :
#   offers = 1. offres compatibles       skills = 2. compétences à travailler
#   cv     = 3. améliorer mon CV         letter = 4. lettre de motivation
Mode = Literal["offers", "skills", "cv", "letter"]

# Contrats que l'utilisateur peut cocher (pas "inconnu" : on ne le coche pas).
ContractType = Literal["cdi", "cdd", "stage", "alternance", "freelance"]

# Cycle de traitement d'une demande.
Status = Literal["pending", "running", "done", "failed"]

# Régions que l'utilisateur peut choisir (ajout M4, après les tests de la
# recherche) : EXACTEMENT les 19 valeurs présentes dans l'index Elasticsearch.
#
# POURQUOI UNE LISTE FERMÉE ?
#   Le filtre région de search.py utilise "term" : égalité EXACTE, caractère
#   par caractère. Avec un texte libre, "ile de france" ne correspondait à
#   aucune offre (l'index contient "Île-de-France") : la recherche ne gardait
#   que les offres SANS région, sans signaler d'erreur. Avec cette liste, une
#   valeur mal écrite est refusée (422) et /docs affiche une liste déroulante.
#
# D'OÙ VIENNENT CES VALEURS ?
#   Les régions des offres sont harmonisées au téléchargement par
#   normalize_region (worker/sources/adzuna.py). Cette liste = OFFICIAL_REGIONS
#   de adzuna.py + "Nouvelle-Calédonie" (pas une région officielle, mais
#   présente dans les données). Vérifié par une agrégation "terms" sur le
#   champ region de l'index (19 valeurs).
#   Si une région VRAIMENT nouvelle apparaît un jour, l'ajouter aux DEUX listes.
#
# Le formulaire React (M7) lira cette liste via la route GET /api/regions :
# elle n'est écrite qu'ICI (source unique).
Region = Literal[
    # Métropole (13)
    "Auvergne-Rhône-Alpes", "Bourgogne-Franche-Comté", "Bretagne",
    "Centre-Val de Loire", "Corse", "Grand Est", "Hauts-de-France",
    "Île-de-France", "Normandie", "Nouvelle-Aquitaine", "Occitanie",
    "Pays de la Loire", "Provence-Alpes-Côte d'Azur",
    # Outre-mer (6)
    "Guadeloupe", "Guyane", "La Réunion", "Martinique", "Mayotte",
    "Nouvelle-Calédonie",
]


# ---------------------------------------------------------------------------
# CE QUE L'API REÇOIT : les données du formulaire
# ---------------------------------------------------------------------------

class SearchCreate(BaseModel):
    """Données envoyées par le formulaire (corps JSON de POST /api/searches).

    Chaque attribut = un champ du formulaire, avec :
      - son TYPE (str, float, list...) : Pydantic convertit ou refuse ;
      - ses RÈGLES, déclarées avec Field(...) :
          min_length / max_length : longueur d'un texte (ou d'une liste)
          ge (greater or equal)   : valeur minimale d'un nombre (>=)
          default                 : valeur si le champ est absent
      - "X | None = None" : champ FACULTATIF (absent = None).
    """

    # --- La personne ---
    full_name: str = Field(min_length=1, max_length=100, description="Nom complet")
    # EmailStr : vérifie le FORMAT d'un email (bibliothèque email-validator).
    email: EmailStr = Field(description="Adresse email (identifie le candidat)")
    # Texte du CV, collé dans le formulaire (le PDF viendra au M3c).
    # OBLIGATOIRE (pas de "| None", pas de default) : les 4 modes partent du CV.
    # min_length=50 : refuse un CV vide ou d'un seul mot (inutilisable).
    # max_length : évite d'enregistrer un texte démesuré par erreur.
    cv_text: str = Field(min_length=50, max_length=20_000, description="Texte du CV (obligatoire)")

    # --- La demande ---
    mode: Mode = Field(description="offers, skills, cv ou letter")
    job_title: str | None = Field(default=None, max_length=100, description="Métier recherché (facultatif)")
    # Region (liste fermée, voir plus haut) au lieu de str : M4, après les tests.
    region: Region | None = Field(default=None, description="Région (vide = toute la France)")
    # default_factory=list : une NOUVELLE liste vide pour chaque requête.
    # (Ne jamais écrire default=[] : une liste partagée entre toutes les
    #  requêtes est un piège classique en Python.)
    contract_types: list[ContractType] = Field(
        default_factory=list, description="Contrats cochés (vide = tous)"
    )
    salary_min: float | None = Field(default=None, ge=0, description="Salaire annuel minimum")

    # Exemple affiché dans /docs (bouton "Try it out" pré-rempli).
    model_config = {
        "json_schema_extra": {
            "example": {
                "full_name": "Léa Martin",
                "email": "lea.martin@example.com",
                "cv_text": "Étudiante en data : Python, SQL, Spark, Airflow. Projet de pipeline de données.",
                "mode": "offers",
                "job_title": "data engineer",
                "region": "Bretagne",
                "contract_types": ["alternance"],
                "salary_min": None,
            }
        }
    }


class SearchQuery(BaseModel):
    """Critères de la recherche hybride seule (POST /api/search/preview, M4).

    Les mêmes champs que SearchCreate, SANS la personne (nom, email) ni le
    mode : cette route sert à TESTER la recherche, elle n'enregistre rien.
    Les règles (longueurs, contrats autorisés...) sont identiques.
    """
    cv_text: str = Field(min_length=50, max_length=20_000, description="Texte du CV (obligatoire)")
    job_title: str | None = Field(default=None, max_length=100, description="Métier recherché (facultatif)")
    region: Region | None = Field(default=None, description="Région (vide = toute la France)")
    contract_types: list[ContractType] = Field(
        default_factory=list, description="Contrats cochés (vide = tous)"
    )
    salary_min: float | None = Field(default=None, ge=0, description="Salaire annuel minimum")

    model_config = {
        "json_schema_extra": {
            "example": {
                "cv_text": "Étudiante en data : Python, SQL, Spark, Airflow. Projet de pipeline de données.",
                "job_title": "data engineer",
                "region": "Bretagne",
                "contract_types": ["alternance"],
                "salary_min": None,
            }
        }
    }


# ---------------------------------------------------------------------------
# CE QUE L'API RENVOIE
# ---------------------------------------------------------------------------

class OfferResult(BaseModel):
    """Une offre trouvée par la recherche hybride.

    Les champs de l'offre (copiés du document Elasticsearch), plus trois
    informations sur son CLASSEMENT :
      - score     : score FINAL = score RRF + bonus des critères respectés
                    (plus il est grand, mieux l'offre est classée) ;
      - rank_bm25  : sa place dans la recherche par MOTS ;
      - rank_knn   : sa place dans la recherche par SENS ;
      - rank_exact : sa place dans la recherche par SENS parmi les offres
                     EXACTES (région et contrat choisis ; ajout M4). None si
                     aucun critère choisi, ou si l'offre n'est pas exacte.
    Garder les deux rangs permet de COMPRENDRE pourquoi une offre est là.

    rank_... = None NE VEUT PAS DIRE que l'offre ne correspond pas : seulement
    qu'elle est HORS DES 100 PREMIÈRES de cette recherche (on ne garde que
    100 candidats par recherche, voir search.py). Exemple réel : l'offre 2082
    contient "data" dans sa description, mais était trop loin en BM25.
    (Commentaire corrigé au M4 : il disait "None = absente".)
    """
    id: int
    title: str
    company: str | None = None
    city: str | None = None
    region: str | None = None
    contract_types: list[str] = Field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    published_at: datetime | None = None
    url: str | None = None
    score: float
    rank_bm25: int | None = None
    rank_knn: int | None = None
    rank_exact: int | None = None   # ajout M4, après tests (3e recherche)

class SearchCreated(BaseModel):
    """Réponse immédiate à POST /api/searches : la demande est enregistrée."""
    id: int
    candidate_id: int
    status: Status


class SearchOut(BaseModel):
    """Réponse de GET /api/searches/{id} : la demande complète."""
    id: int
    candidate_id: int
    mode: Mode
    job_title: str | None
    region: str | None
    contract_types: list[str]
    salary_min: float | None
    # Statut EN DIRECT (lu dans Redis), ou celui de PostgreSQL à défaut.
    status: Status
    results: dict | None
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None
