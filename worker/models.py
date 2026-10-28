"""
Format interne commun d'une offre d'emploi.

Chaque source (Adzuna aujourd'hui, d'autres demain) convertit ses données
vers ce format. Le reste du projet ne dépend que de JobOffer.
"""

from dataclasses import asdict, dataclass


# @dataclass génère automatiquement __init__, __repr__ et __eq__
# à partir des attributs déclarés : moins de code répétitif.
@dataclass
class JobOffer:
    source: str              # nom de la source, ex. "adzuna"
    source_id: str           # identifiant de l'offre chez la source
    title: str
    company: str | None      # "| None" : la valeur peut être absente
    location: str | None
    contract_type: str | None
    category: str | None     # catégorie de la source (sert de "métier")
    description: str
    salary_min: float | None
    salary_max: float | None
    created_at: str | None   # date de publication (format ISO)
    url: str                 # lien vers l'annonce complète

    def to_dict(self) -> dict:
        """Convertit l'offre en dictionnaire (pour le JSON ou la base)."""
        return asdict(self)