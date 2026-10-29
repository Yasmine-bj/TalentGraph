# Journal d'apprentissage

## M0 — Infrastructure (octobre 2026)

### Notions apprises
- Image vs conteneur : ...
- Volume nommé et persistance : ...
- Healthcheck : ...
- Réseau Docker : un service se joint par son nom (postgres:5432) ...
- Redis AOF vs RDB : ...
- Elasticsearch : single-node, sécurité, heap Java ...

### Problèmes rencontrés et solutions
- Python de MSYS2 au lieu du Python officiel → venv cassé ...
- Authentification Git refusée (mot de passe) → Git Credential Manager ...
- Moteur Docker non démarré → lancer Docker Desktop ...
- Volume non déclaré dans la section volumes ...
- Rôle PostgreSQL introuvable : sensibilité à la casse + variables appliquées seulement sur un volume vide ...
- `curl` sous PowerShell est un alias → utiliser `curl.exe` ...

## M1 — Ingestion des offres (octobre 2026)

### Notions apprises
- Pattern adaptateur : chaque source (`worker/sources/adzuna.py`) convertit ses offres vers un format commun (`JobOffer`, `worker/models.py`) ; le reste du projet ne connaît pas Adzuna.
- Cache des réponses brutes : on garde ce que l'API a répondu, pas notre interprétation. Tout ce qui vient après (détection du contrat, format, champs) se corrige et se rejoue sans appel. La clé du cache doit contenir TOUS les paramètres qui influencent la réponse.
- Paramètres de l'API Adzuna :
  - `what` (tous les mots, n'importe où), `what_or` (au moins un), `what_phrase` (phrase exacte), `what_exclude` ;
  - `title_only` (mots dans le titre), `where` + `distance` (rayon, 5 km par défaut), `location0..7` (zone administrative) ;
  - `max_days_old`, `sort_by`, `category`, `results_per_page` (max 50) ;
  - le pays est dans l'URL (`/jobs/fr/search/1`) : seulement des offres françaises.
- Champs de la réponse non encore exploités : `count` (total disponible), `location.area` (France > région > département > ville, pour normaliser les lieux au M2), `salary_is_predicted` (salaire estimé par Adzuna), `contract_time`, `latitude` / `longitude`.
- Expressions régulières : `\b` (frontière de mot), `|`, `?`, groupes, `(?!...)` (« non suivi de »), `re.IGNORECASE`.
- Python : dataclass, annotations de type (`str | None`), f-strings, compréhensions de liste et de dictionnaire, générateurs, `**dict`, tuple renvoyé et « déballé » (`types, source = ...`), `set` (`&`, `|`, `-`) pour mesurer les doublons, `if __name__ == "__main__"`, `python -m` (lancer depuis `worker/`).
- Robustesse : nouvelles tentatives avec attente croissante (backoff) sur les erreurs passagères (réseau, 429, 5xx), pas sur les erreurs définitives (400, 410).
- Sécurité : une clé dans l'URL peut fuiter via les messages d'erreur (`requests` affiche l'URL complète) → `_safe_get` + `raise ... from None`, jamais `raise_for_status()`.
- Méthode : mesurer avant de décider. Chaque choix vient d'un script d'exploration (`worker/explore/`) à faible coût.

### Mesures

| Test | Résultat | Décision |
|---|---|---|
| Champ `contract_type` d'Adzuna | vide pour 63 % des offres, ni stage ni alternance | détection dans le texte (D8) |
| `title_only="alternance"` vs `what="alternance data"` | 100 % vs 70 % d'alternances | recherches ciblées (D6) |
| filtre `category="it-jobs"` | 50 offres → 4 | abandonné |
| `results_per_page=100` | 50 reçues | 50 max par page |
| pages pleines tant qu'il reste des offres | 50 reçues sur 839 disponibles | arrêt anticipé correct |
| « data engineer » Paris (5 km) vs France | 839 vs 2 277 | collecte nationale (D5) |
| collecte complète (26 recherches × 8 pages) | 8 531 offres, 7 298 uniques, 14 % de doublons, ~175 appels | — |
| recouvrements | data scientist ↔ machine learning : 108 offres communes ; « business intelligence » ↔ « intelligence artificielle » : 88 (`what` cherche des mots, pas une expression) | `what_phrase` à tester pour la mise à jour quotidienne |
| alternances | 87 à 157 par recherche contre 400 pour les stages | biais de saison (fin octobre, 30 derniers jours) |
| `permanent` vs contrat écrit dans le texte | 624 CDI / 28 stages → ~96 % fiable | dernier recours → cdi (D8) |
| contrats après détection | inconnu 33 %, cdi 32 %, stage 22 %, freelance 7 %, alternance 4 % | — |
| longueur des descriptions | 498 caractères en moyenne, même avec le plan payant | limite connue de la source |

### Problèmes rencontrés et solutions
- API France Travail fermée aux nouvelles souscriptions (`invalid_client`, INC2769592) → Adzuna (D4).
- `requirements.txt` illisible : `pip freeze >` sous PowerShell écrit en UTF-16 → fichier réécrit à la main en UTF-8, dépendances directes uniquement.
- `ModuleNotFoundError: dotenv` → venv non activé.
- `ModuleNotFoundError: sources` en lançant un script depuis `worker/explore/` → toujours lancer depuis `worker/` avec `python -m explore.<script>`.
- Erreur DNS (`getaddrinfo failed`) qui affichait l'URL avec la clé → `_safe_get` ; clé régénérée.
- Clé collée dans une conversation → la régénérer et masquer les secrets (`***`) avant tout partage.
- Premier test `results_per_page=100` faussé par le cache (le nom du fichier ne contenait pas ce paramètre) → test refait sans cache.
- Faux positifs de contrat (« apprentissage automatique » → alternance…) → motifs stricts pour la description, tests sur 22 phrases.
- Pause de 3 s même sur le cache → pause uniquement après un vrai appel.
