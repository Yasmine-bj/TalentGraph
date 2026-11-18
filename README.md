# TalentGraph

Copilote carrière : l'utilisateur colle son CV, choisit ses critères, et TalentGraph
trouve les offres d'emploi réelles les plus proches de son profil, grâce à une
**recherche hybride** (mots-clés BM25 + recherche par le sens avec des embeddings),
et explique pour chaque offre **pourquoi** elle est proposée.

Projet BigData / NoSQL (ENSIIE) — **PostgreSQL**, **Redis**, **Elasticsearch**,
FastAPI, React, Docker.

## Lancer le projet

Prérequis : **Docker Desktop** (moteur démarré). Aucune configuration nécessaire.

```bash
git clone https://github.com/Yasmine-bj/TalentGraph.git
cd TalentGraph
docker compose up -d --build
```

Le **premier démarrage** prend quelques minutes : construction des images, puis le
conteneur `loader` charge 1 794 offres de démonstration dans PostgreSQL et calcule
leurs embeddings pour Elasticsearch (téléchargement du modèle, ~470 Mo, une seule fois).

```bash
docker compose ps -a        # attendre : loader "Exited (0)", les autres "healthy"
docker compose logs loader  # suivre le chargement
```

Puis ouvrir **http://localhost:3000**.

## Utiliser l'application

1. Sur l'accueil, cliquer sur **« Commencer »**.
2. **Étape 1 — Vous** : cliquer sur **« Remplir avec un exemple »**, ou saisir son nom,
   son email et coller le texte de son CV (50 caractères minimum).
3. **Étape 2 — Objectif** : « Trouver des offres ».
4. **Étape 3 — Critères** (tous facultatifs) : métier, région, salaire minimum, contrats.
5. **Étape 4 — Récapitulatif** : **« Lancer la recherche »**.
6. La demande est enregistrée, la recherche tourne en arrière-plan, et la page suit son
   avancement, puis affiche les offres :
   - un **pourcentage de compatibilité** par offre ;
   - les **raisons** (mots-clés, proximité avec le parcours, région, contrat) ;
   - **« Pourquoi cette offre ? »** : sa place dans chaque recherche et les points gagnés ;
   - le filtre **« Vos critères uniquement »**.

Le **numéro de la demande** est affiché à gauche des résultats (« Demande n° 42 »).

Prochainement : comptes utilisateurs, import du CV en PDF/Word, et les modes
« Compétences à développer », « Booster mon CV », « Lettre de motivation » (agents IA).

## Comment sont classées les offres

1. Jusqu'à **3 recherches** dans Elasticsearch : par **mots-clés** (BM25, sur le métier),
   par **sens** (kNN sur les embeddings du CV), et par sens **parmi les offres qui
   respectent exactement** la région et le contrat choisis.
2. **Fusion RRF** : chaque offre gagne `1 / (60 + rang)` dans chaque recherche où elle apparaît.
3. **Bonus** : +0,02 si la région est respectée, +0,02 si le contrat l'est.
4. **Compatibilité** = score de l'offre ÷ meilleur score possible pour cette recherche.

Détails : [`docs/api.md`](docs/api.md) et [`docs/decisions.md`](docs/decisions.md).

## Vérifier la persistance

Chaque demande est enregistrée dans **PostgreSQL** (source de vérité) et son statut
en direct dans **Redis**. Remplacer `42` par le numéro affiché sur la page.

**Terminal 1 — PostgreSQL**
```bash
docker compose exec postgres psql -U talentgraph -d talentgraph
```
```sql
SELECT * FROM candidates;
SELECT id, mode, job_title, region, status, finished_at - created_at AS duree,
       jsonb_array_length(results->'offers') AS nb_offres
FROM searches ORDER BY id DESC LIMIT 5;
SELECT count(*) FROM offers;
-- Les 3 premières offres de la dernière recherche, avec leur compatibilité
SELECT o->>'title' AS offre, o->>'match_percent' AS compatibilite
FROM searches, jsonb_array_elements(results->'offers') AS o
WHERE id = (SELECT max(id) FROM searches)
LIMIT 3;
```

**Terminal 2 — Redis**
```bash
docker compose exec redis redis-cli
```
```
HGETALL search:42
LRANGE searches:recent 0 -1
GET stats:searches_total
```

**Elasticsearch**
```bash
curl http://localhost:9200/offers/_count
```

Les données sont dans des **volumes Docker** : elles survivent à un redémarrage.
`docker compose down` arrête les conteneurs et **conserve** les données ;
`docker compose down -v` **supprime** aussi les données.

## Architecture

| Conteneur | Rôle | Adresse |
|---|---|---|
| `frontend` | interface React + Mantine, servie par nginx (qui transmet `/api` à l'API) | http://localhost:3000 |
| `api` | API FastAPI : enregistre les demandes, lance la recherche en arrière-plan | http://localhost:8000/docs |
| `postgres` | candidats, demandes, résultats, offres (source de vérité) | port 5433 |
| `redis` | statut en direct des demandes, demandes récentes, compteur | port 6379 |
| `elasticsearch` | index des offres : recherche par mots (BM25) et par le sens (kNN) | http://localhost:9200 |
| `loader` | au démarrage : remplit PostgreSQL et Elasticsearch si besoin, puis s'arrête | — |

Documentation détaillée : [`docs/api.md`](docs/api.md) (routes, parcours d'une demande,
recherche hybride), [`docs/decisions.md`](docs/decisions.md) (choix techniques),
[`docs/learning-log.md`](docs/learning-log.md).

## Développer

```bash
docker compose up -d                          # bases + API
cd frontend && npm install && npm run dev     # http://localhost:5173 (rechargement à chaud)
```
Vite transmet les appels `/api` à `localhost:8000` (voir `frontend/vite.config.js`) ;
en production, c'est nginx qui le fait (`frontend/nginx.conf`).

## Configuration (facultatif)

Sans fichier `.env`, des valeurs par défaut sont utilisées (utilisateur, mot de passe
et base `talentgraph`) : elles conviennent **uniquement à une démonstration locale**.
Pour les changer : `cp .env.example .env`, puis remplir les valeurs.

## Données

Offres d'emploi fournies par [Adzuna](https://www.adzuna.fr) (voir [`seed/README.md`](seed/README.md)).
