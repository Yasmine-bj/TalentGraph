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
    - ce que l'API REÇOIT  (SearchCreate)       : les données du formulaire ;
    - ce que l'API RENVOIE (SearchCreated, SearchOut) : la forme des réponses.
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
    # max_length : évite d'enregistrer un texte démesuré par erreur.
    cv_text: str | None = Field(default=None, max_length=20_000, description="Texte du CV")

    # --- La demande ---
    mode: Mode = Field(description="offers, skills, cv ou letter")
    job_title: str | None = Field(default=None, max_length=100, description="Métier recherché")
    region: str | None = Field(default=None, max_length=100, description="Région (vide = toute la France)")
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


# ---------------------------------------------------------------------------
# CE QUE L'API RENVOIE
# ---------------------------------------------------------------------------

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
