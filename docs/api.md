# API TalentGraph — référence (M3, M4)

Ce document décrit l'API FastAPI (`api/`) : ses routes, ce qu'elle enregistre
dans PostgreSQL et Redis, et le parcours complet d'une demande.
Documentation interactive (générée par FastAPI) : http://localhost:8000/docs

## Les routes

| Verbe | Adresse | Rôle | Codes de réponse |
|---|---|---|---|
| `GET` | `/health` | vérifie que l'API joint PostgreSQL, Redis et Elasticsearch | 200 tout va bien · 503 une base injoignable |
| `POST` | `/api/searches` | enregistre le formulaire : candidat + demande | 201 créée · 422 données invalides |
| `GET` | `/api/searches/{id}` | relit une demande (PostgreSQL) et son statut en direct (Redis) | 200 · 404 introuvable · 422 id non numérique |
| `POST` | `/api/search/preview` | **teste** la recherche hybride, sans rien enregistrer (M4) | 200 · 422 · 503 Elasticsearch indisponible |
| `GET` | `/api/regions` | liste des 19 régions acceptées (liste déroulante du formulaire, M4) | 200 |

Convention REST : `/api/searches` désigne la **collection** des demandes
(`POST` = ajouter un élément), `/api/searches/{id}` **un élément** (`GET` = le lire).

## Ce qui est enregistré

### PostgreSQL (source de vérité) — `infra/postgres/init/02_candidates.sql`

| Table | Contenu | Particularités |
|---|---|---|
| `candidates` | une ligne par personne : nom, email, texte du CV | email **unique** (même email = même personne, fiche mise à jour par UPSERT) |
| `searches` | une ligne par demande : mode, critères, statut, résultat | **clé étrangère** `candidate_id` → `candidates.id`, `ON DELETE CASCADE` |

Statut d'une demande : `pending` (reçue) → `running` (en cours) → `done` / `failed`.
La valeur `pending` est mise par PostgreSQL (`DEFAULT 'pending'`) et récupérée
avec `RETURNING id, status`.

### Redis (rapide et temporaire)

Convention de nommage des clés : `objet:identifiant`. Le `:` n'a aucun sens pour
Redis ; la clé entière (ex. `search:1`) est un seul texte.

| Clé | Type Redis | Contenu | Combien | Durée de vie |
|---|---|---|---|---|
| `search:{id}` | **hash** | `status`, `mode`, `candidate_id`, `updated_at` : le statut **en direct** | une par demande | 7 jours (`EXPIRE`) |
| `searches:recent` | **list** | identifiants des 50 dernières demandes, la plus récente en tête | une seule | permanente |
| `stats:searches_total` | **string** (compteur) | nombre total de demandes reçues | une seule | permanente |

Pourquoi le statut aussi dans Redis : pendant un traitement (M4/M5), la page web
relit le statut toutes les secondes ; ces lectures fréquentes vont dans Redis
plutôt que dans PostgreSQL. La demande elle-même reste pour toujours dans PostgreSQL.

## Parcours complet d'une demande

```
1. Léa envoie le formulaire
   POST /api/searches  {"full_name": "Léa Martin", "email": "Lea@Example.com", "mode": "offers", ...}
        │
2. FastAPI valide avec SearchCreate (api/app/schemas.py) ──── invalide ? → 422, fin
        │ valide
3. create_search()  (api/app/main.py)
        ├── PostgreSQL (transaction : tout ou rien)
        │     ├── UPSERT candidates  → candidat 5 (email en minuscules)
        │     └── INSERT searches    → demande 5, status 'pending' (valeur par défaut)
        │     COMMIT ✔
        ├── Redis (pipeline MULTI/EXEC : 5 commandes, un seul aller-retour)
        │     ├── HSET search:5 {status: pending, mode: offers, ...}
        │     ├── EXPIRE search:5 604800                (7 jours)
        │     ├── LPUSH searches:recent 5  +  LTRIM 0 49  (liste plafonnée à 50)
        │     └── INCR stats:searches_total → 1
        └── réponse 201  {"id": 5, "candidate_id": 5, "status": "pending"}

4. Plus tard : GET /api/searches/5
        ├── PostgreSQL : SELECT ... WHERE id = 5  (introuvable ? → 404)
        ├── Redis : HGET search:5 status → "pending"   (absent ? statut de PostgreSQL)
        └── réponse 200 : la demande complète
```

### Règles importantes

- **PostgreSQL d'abord, Redis ensuite** : on écrit toujours d'abord dans la base
  qui fait foi. Si PostgreSQL échoue, rien n'est écrit dans Redis.
- **Redis est un accélérateur, pas une dépendance obligatoire** : si Redis est en
  panne, la demande est quand même enregistrée (201) et la lecture se rabat sur
  le statut de PostgreSQL (erreur seulement notée dans les logs).
- **Validation en deux couches** : Pydantic (`schemas.py`) refuse tôt avec un
  message clair (422) ; les contraintes `CHECK` de PostgreSQL restent le dernier
  rempart.

## Champs du formulaire (M4)

- `cv_text` **obligatoire** (50 à 20 000 caractères) ; `job_title` facultatif.
- `region` : une des 19 valeurs de `GET /api/regions`, écrites exactement (ex. `Île-de-France`) ; sinon 422.
- `contract_types` : `cdi`, `cdd`, `stage`, `alternance`, `freelance` (vide = tous).

## Recherche hybride (M4) — `api/app/search.py`

```
critères du formulaire
   │
   ├── filtres SOUPLES : région choisie OU absente, contrat coché OU « inconnu », salaire OK OU absent
   ├── filtres STRICTS : région choisie, contrat coché (si l'un des deux est choisi)
   │
   ├── 1.     par mots (BM25) : métier dans title^3 + description,
   │          bonus expression exacte dans le titre ──────────────────► 100 offres (rank_bm25)
   ├── 2.     par sens (kNN)  : vecteur de « métier. CV », filtres souples ─► 100 offres (rank_knn)
   └── 2 bis. par sens (kNN)  : même vecteur, filtres STRICTS ─────────────► 100 offres (rank_exact)
                    │
       fusion RRF : score = Σ 1 / (60 + rang)
                    │
       bonus : région exacte +0,02, contrat correspondant +0,02
                    │
       20 meilleures offres
```

Chaque résultat contient `score`, `rank_bm25`, `rank_knn`, `rank_exact`
(`null` = hors des 100 premières de cette recherche). Choix et tests : D19 à D24.

## Évolution prévue (M4/M5)

Une fonction `update_search_status(id, status, results=None, error_message=None)`
mettra à jour **PostgreSQL puis Redis** à chaque étape du traitement, lancé en
arrière-plan (`BackgroundTasks`) pour que `POST /api/searches` réponde tout de suite :

```
pending ──► running ──► done   (results rempli, finished_at)
                    └─► failed (error_message rempli)
```

## Vérifier la persistance (ce que fera le correcteur)

Terminal 1 — PostgreSQL :
```
docker compose exec postgres psql -U talentgraph -d talentgraph
SELECT * FROM candidates;
SELECT id, candidate_id, mode, job_title, region, contract_types, status FROM searches;
```

Terminal 2 — Redis :
```
docker compose exec redis redis-cli
KEYS *
HGETALL search:1
LRANGE searches:recent 0 -1
GET stats:searches_total
TTL search:1
```

Limite connue : pas de comptes utilisateurs en V1 ; toute personne connaissant
un identifiant de demande peut la lire. Comptes (mots de passe hachés, JWT)
prévus après le rendu.
