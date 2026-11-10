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


## M2 — Schéma, chargement et indexation (octobre – novembre 2026)

### Notions apprises — PostgreSQL
- Clé primaire interne vs identifiant métier ; clé composée `(source, source_id)`.
- UPSERT (`INSERT ... ON CONFLICT ... DO UPDATE`, `EXCLUDED`) et **idempotence**.
- Contraintes : `NOT NULL`, `UNIQUE`, `CHECK`, `DEFAULT`, clé étrangère ; la base protège la qualité des données.
- Types : `TEXT`, `NUMERIC` (exact, pour l'argent), `DOUBLE PRECISION`, `TIMESTAMPTZ`, `TEXT[]`, `JSONB`.
- Index : rôle (éviter de lire toute la table), coût (écritures plus lentes, place) ; **B-tree** (égalité, tri, intervalles), **B-tree unique** (vitesse + interdiction des doublons), **GIN** (index inversé : « contient ») ; `EXPLAIN ANALYZE`.
- Tableau dans la ligne vs table de liaison (jointure), normalisation et exception assumée.
- Scripts d'initialisation (`/docker-entrypoint-initdb.d`), exécutés seulement sur un volume vide ; montage (*bind mount*) vs volume nommé.
- psycopg : connexion, **curseur**, `execute` / `executemany` / `fetchone` / `fetchall`, lignes en tuples ou en dictionnaires (`dict_row`).
- **Requêtes paramétrées** (`%(nom)s`) et **injection SQL**.
- **Transactions** (COMMIT / ROLLBACK), `autocommit`, isolation (une transaction voit ses propres modifications avant le COMMIT).
- Python : docstring, tuple (et virgule du tuple à un élément), déballage, `try / except / raise`, `Exception` vs `BaseException`, générateur avec `yield`, compréhension d'ensemble, `unicodedata` pour retirer les accents.
- Variables d'environnement : obligatoires (`os.environ["X"]`) ou avec valeur par défaut (`os.environ.get("X", "y")`) ; ce qui change selon l'environnement va dans la configuration, pas dans le code.
- Docker : `up -d`, `stop`, `down`, `down -v` (supprime les données), `ps`, `logs`, `exec` ; `up -d` ne recrée que ce qui a changé ; healthchecks (« le conteneur tourne » vs « le service est prêt ») ; client / serveur.

### Notions apprises — Elasticsearch
- Moteur de recherche : résultats **classés par pertinence** (score BM25 : fréquence du mot, rareté, longueur du champ) ; vocabulaire cluster / index / document / champ / mapping.
- **Index inversé** (même principe que GIN) et **analyseurs** (découpage, minuscules, mots vides, racinisation) ; analyseur `standard` vs `french`.
- `text` (analysé, pertinence) vs `keyword` (valeur exacte, filtres, comptages) ; sous-champs (`fields`) ; tout champ peut contenir plusieurs valeurs.
- Mapping dynamique (deviné) vs mapping écrit, `dynamic: strict` ; options `index` et `doc_values` ; `_source`.
- API REST : verbe HTTP (quoi faire) + adresse (sur quoi) ; actions réservées commençant par `_` (`_doc`, `_search`, `_mapping`, `_analyze`, `_count`, `_bulk`).
- Requêtes : `match` (OU par défaut, `operator: and`), `bool` (`must` compte dans le score, `filter` est un oui/non sans effet sur le score), `term`, agrégations `terms` (`size: 0`).
- Shards et répliques ; état vert / jaune.
- « Presque temps réel » : un document n'est cherchable qu'après le *refresh* (~1 s).
- Client Python : `Elasticsearch(url)`, `info()`, `indices.delete / create / refresh`, `helpers.bulk`, `count`.
- Recherche par le sens (vecteurs, `dense_vector`) et recherche hybride : principe, pour l'étape suivante.

### Mesures
| Mesure | Résultat |
|---|---|
| Offres chargées dans PostgreSQL | 7 298 |
| Relance du chargement | 0 insérée, 7 298 mises à jour (idempotent) |
| Valeurs de région après nettoyage | 19 (13 métropole + 5 outre-mer + Nouvelle-Calédonie) + 602 sans région |
| Variantes de régions corrigées | « Pays de la Loire » 478 → 481, « Centre-Val de Loire » 119 → 124 |
| Paris | 708 offres département + 438 arrondissements ramenés à la ville « Paris » |
| Documents dans l'index `offers` | 7 298 / 7 298 |
| Tests de robustesse du chargement | rollback sur offre invalide, `Ctrl+C` et connexion coupée (23 520 offres) |

### Problèmes rencontrés et solutions
- Script SQL d'initialisation ignoré : le volume existait déjà → `docker compose down -v` (sans risque tant que la base est vide).
- « authentification par mot de passe échouée » : un PostgreSQL installé sur Windows écoutait aussi sur le port 5432 (diagnostic `netstat`, `Get-Process`) → Docker publié sur 5433 (D16).
- `POSTGRES_PORT` oublié dans `.env` : le script utilisait encore le port par défaut 5432.
- `offers_sample.json` pas régénéré : régions encore brutes → relancer `fetch_offers.py` (0 appel, depuis le cache) avant le chargement.
- `docker compose` lancé depuis le mauvais dossier (« no configuration file provided ») → toujours depuis la racine du projet.
- Accents cassés dans PowerShell (`DÃ©veloppeuse`) : affichage seulement, la réponse UTF-8 était lue avec un autre encodage → Postman, ou décodage explicite en UTF-8.
- Postman : bouton « Send » grisé dans un espace d'équipe en lecture seule → espace de travail personnel.
- `no handler found for uri` : faute de frappe (`_analyse` au lieu de `_analyze`), puis retour à la ligne copié dans l'adresse (`%0A`).
- Recherche vide sur `demo_fr` : les documents n'avaient pas été ajoutés à ce nouvel index.
- Même score pour deux offres : analyseur `standard` (« développeuse » ≠ « développeur ») et critères BM25 identiques → mapping avec l'analyseur `french`.
- Connexion refusée sur `localhost:9200` : Elasticsearch encore en démarrage (`health: starting`) → attendre `healthy`.
- Verrou Git `.git/index.lock` laissé par une commande lancée depuis un environnement qui ne peut pas supprimer de fichiers → suppression manuelle du verrou.
