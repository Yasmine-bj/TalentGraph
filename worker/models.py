"""
models.py — Format interne commun d'une offre d'emploi.

POURQUOI CE FICHIER ?
    Chaque API d'offres nomme ses champs à sa façon : "title" chez Adzuna,
    "intitule" chez France Travail, etc. Plutôt que de laisser ces formats
    se répandre dans tout le projet, chaque source CONVERTIT ses données
    vers une seule classe : JobOffer.

    Le reste du projet (base de données, recherche, agents IA) ne connaît
    que JobOffer. Changer de source ne touche donc que le dossier sources/.
    C'est le principe du patron de conception "adaptateur".

UTILISÉ PAR :
    - sources/adzuna.py  : crée des JobOffer à partir des offres Adzuna
    - fetch_offers.py    : convertit les JobOffer en JSON pour les sauvegarder
"""

# dataclass : outil de la bibliothèque standard pour créer des classes
#             qui servent surtout à stocker des données.
# asdict    : convertit un objet dataclass en dictionnaire Python.
from dataclasses import asdict, dataclass


# ---------------------------------------------------------------------------
# @dataclass est un DÉCORATEUR : il modifie la classe juste en dessous.
# À partir de la liste des attributs, il génère automatiquement :
#   - __init__ : le constructeur, pour écrire JobOffer(source="adzuna", ...)
#   - __repr__ : un affichage lisible quand on fait print(offre)
#   - __eq__   : la comparaison, deux offres aux champs identiques sont égales
# Sans @dataclass, il faudrait écrire ces méthodes à la main (~20 lignes).
#
# Les annotations de type (str, float, str | None) :
#   - documentent ce que contient chaque champ ;
#   - permettent à l'éditeur (Cursor) de détecter des erreurs ;
#   - ne sont PAS vérifiées par Python à l'exécution.
#   "str | None" signifie : une chaîne de caractères, OU None (valeur absente).
#   On l'utilise pour les champs que les API ne remplissent pas toujours.
# ---------------------------------------------------------------------------
@dataclass
class JobOffer:
    # --- Identité de l'offre ---
    source: str              # nom de la source, ex. "adzuna"
    source_id: str           # identifiant de l'offre CHEZ la source.
                             # Le couple (source, source_id) identifie une offre
                             # de façon unique : il sert à supprimer les doublons.

    # --- Contenu principal ---
    title: str               # intitulé du poste, ex. "Data Engineer"
    company: str | None      # nom de l'entreprise (parfois absent)
    location: str | None     # lieu tel qu'affiché par la source, ex. "Brest, Finistère"
    # Lieu NORMALISÉ (découpé), pour les filtres du formulaire.
    # Vide (None) quand la source ne donne que le pays (offre nationale / télétravail).
    region: str | None       # ex. "Bretagne"
    department: str | None   # ex. "Finistère"
    city: str | None         # ex. "Brest" (le niveau le plus précis disponible)
    latitude: float | None   # coordonnées GPS (carte des offres, bonus)
    longitude: float | None
    # Types de contrat NORMALISÉS, déduits par contracts.detect_contract()
    # (texte de l'offre, puis champ brut de la source en dernier recours).
    # Une LISTE, car une offre peut en proposer plusieurs ("Stage / Alternance").
    # Valeurs possibles : "cdi", "cdd", "stage", "alternance", "freelance", "inconnu".
    contract_types: list[str]
    # D'OÙ VIENT ce contrat (niveau de confiance), du plus sûr au moins sûr :
    #   "title"       : écrit dans le titre
    #   "description" : écrit dans la description
    #   "keywords"    : déduit des mots-clés de la recherche
    #   "adzuna"      : déduit du champ brut de la source ("permanent" -> cdi, ~96 % fiable)
    #   "none"        : aucune information (contract_types = ["inconnu"])
    # Servira au M2 à classer : contrat écrit > contrat déduit > inconnu.
    contract_source: str
    # Valeur BRUTE du contrat fournie par la source (ex. "permanent", "contract"
    # chez Adzuna). Souvent vide ; "permanent" est fiable (~96 %) et sert de
    # dernier recours, "contract" est inutilisable (mélange stage/freelance/CDD).
    contract_raw: str | None
    # Temps de travail fourni par la source : "full_time", "part_time" ou None.
    contract_time: str | None
    category: str | None     # catégorie fournie par la source ; servira de "métier"
                             # (chez Adzuna elle est parfois trop vague, ex. "Autres/Général")
    description: str         # description du poste (chez Adzuna : un EXTRAIT tronqué)

    # --- Informations complémentaires ---
    salary_min: float | None # salaire minimum annuel (peut être estimé par la source)
    salary_max: float | None # salaire maximum annuel
    created_at: str | None   # date de publication, au format ISO 8601
                             # ex. "2026-10-22T06:01:47Z" (Z = heure UTC)
    # Recherche qui a ramené l'offre : ses mots-clés, suivis du contrat ciblé
    # entre crochets pour les recherches title_only.
    #   ex. "data engineer" (recherche générale), "data [alternance]" (ciblée).
    # Sert d'indice pour le contrat (dernier recours) et de famille de métier
    # pour les statistiques.
    search_keywords: str | None
    url: str                 # lien vers l'annonce complète sur le site d'origine
    # L'offre BRUTE, telle que renvoyée par la source (dictionnaire complet).
    # Stockée dans PostgreSQL (colonne JSONB "raw") : on peut ainsi retraiter
    # les offres sans le fichier cache ni aucun appel API.
    raw: dict

    def to_dict(self) -> dict:
        """Convertit l'offre en dictionnaire Python.

        Utile pour :
          - l'écrire en JSON (json.dump ne sait pas écrire un objet JobOffer,
            mais sait écrire un dictionnaire) ;
          - plus tard, l'insérer dans PostgreSQL ou l'indexer dans Elasticsearch.

        Exemple de résultat :
            {"source": "adzuna", "source_id": "5937384042", "title": "Data Engineer", ...}
        """
        return asdict(self)
