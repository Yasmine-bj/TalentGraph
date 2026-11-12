"""
embeddings.py — Transformer un texte en vecteur de sens (embedding) (module M4).

RÔLE :
    Un seul endroit pour produire les embeddings, avec LE MÊME modèle partout :
      - worker/index_offers.py : les OFFRES          -> embed_passages(...)
      - api (recherche)        : le CV / la recherche -> embed_query(...)
    Des vecteurs produits par deux modèles différents ne sont pas comparables :
    c'est pourquoi ce fichier existe en deux copies IDENTIQUES
    (worker/embeddings.py et api/app/embeddings.py), une par conteneur.

LE MODÈLE : intfloat/multilingual-e5-small (Hugging Face)
    - multilingue (français + anglais), entraîné pour la RECHERCHE ;
    - 384 dimensions, ~470 Mo, tourne sur un processeur ordinaire (CPU) ;
    - téléchargé au premier usage, puis gardé en cache sur le disque.

QUI FAIT QUOI :
    - le dossier du modèle : poids, plan de l'architecture, vocabulaire, étapes ;
    - transformers : construit le réseau d'après le plan (config.json) ;
    - PyTorch : exécute les calculs ;
    - sentence-transformers : enchaîne les étapes (découper, numéroter,
      calculer, moyenne, normaliser) derrière model.encode().

PRÉFIXES OBLIGATOIRES (particularité des modèles E5) :
    "passage: " pour ce qui est CHERCHÉ (les offres),
    "query: "   pour ce qu'on CHERCHE (le CV, la recherche).
    Le modèle a été entraîné ainsi ; sans préfixe, la qualité baisse.
    Les préfixes sont ajoutés ICI uniquement : le reste du code n'a pas à
    s'en souvenir.

FORMATS D'UN EMBEDDING :
    tenseur PyTorch (pendant le calcul) -> tableau NumPy (sortie de encode())
    -> liste Python (.tolist(), pour l'envoyer en JSON à Elasticsearch).
"""

import os

from sentence_transformers import SentenceTransformer

# Nom du modèle sur le Hub Hugging Face (modifiable par variable d'environnement,
# par exemple pour tester le modèle fine-tuné du M6).
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

# Nombre de dimensions des vecteurs : doit être IDENTIQUE au "dims" du champ
# "embedding" dans infra/elasticsearch/offers_mapping.json, sinon
# Elasticsearch refuse les documents.
EMBEDDING_DIMS = 384

# Le modèle, chargé UNE SEULE FOIS puis réutilisé (voir get_model).
# Le "_" signale une variable interne à ce module.
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Charge le modèle au premier appel, puis renvoie toujours le même.

    Charger le modèle prend quelques secondes (lecture de ~470 Mo, construction
    du réseau) : on ne le fait qu'une fois. C'est un chargement "paresseux"
    (lazy) : il n'a lieu qu'au premier usage, pas à l'import du fichier.
    L'API démarre donc vite, et seul le premier calcul attend le chargement.

    "global _model" : permet de MODIFIER la variable _model du module
    (sans lui, Python créerait une variable locale à la fonction).
    device="cpu" : calculs sur le processeur (suffisant pour notre volume,
    fonctionne sur toutes les machines, sans carte graphique).
    """
    global _model
    if _model is None:
        print(f"Chargement du modèle d'embeddings {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def embed_passages(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Vecteurs de plusieurs textes à CHERCHER (les offres), préfixe "passage: ".

    Renvoie une liste de vecteurs (un par texte), chacun de EMBEDDING_DIMS nombres.

    batch_size=64 : les textes sont traités par paquets de 64. Les calculs
        d'un paquet se font en parallèle (multiplications de matrices) :
        bien plus rapide que 64 appels d'un texte.
    show_progress_bar=True : barre de progression dans le terminal
        (l'indexation des ~7 300 offres prend quelques minutes sur CPU).
    normalize_embeddings=True : vecteurs de longueur 1 (comparaison par cosinus).
    .tolist() : tableau NumPy de forme (nombre de textes, 384) -> listes Python,
        que le client Elasticsearch sait envoyer en JSON.
    """
    vectors = get_model().encode(
        [f"passage: {text}" for text in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Vecteur d'UN texte de recherche (CV, métier...), préfixe "query: ".

    Renvoie un seul vecteur de EMBEDDING_DIMS nombres
    (tableau NumPy de forme (384,) -> liste Python).
    """
    vector = get_model().encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()
