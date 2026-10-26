# TalentGraph
AI career copilot: matches CVs with live job offers using hybrid search (BM25 + fine-tuned embeddings), multi-agent orchestration (LangGraph) and LLMs. Stack: FastAPI, PostgreSQL, Elasticsearch, Redis, PyTorch, Docker.

## Lancer le projet

Prérequis : Docker Desktop (moteur démarré).

```bash
git clone https://github.com/Yasmine-bj/TalentGraph.git
cd TalentGraph
cp .env.example .env      # puis remplir les valeurs
docker compose up -d
docker compose ps         # attendre que les services soient "healthy"
```

## Vérifier la persistance

| Base | Commande |
| --- | --- |
| PostgreSQL | `docker compose exec postgres psql -U talentgraph -d talentgraph` |
| Redis | `docker compose exec redis redis-cli` |
| Elasticsearch | `curl http://localhost:9200` |

`docker compose down` supprime les conteneurs mais conserve les données (volumes nommés).
`docker compose down -v` supprime aussi les données.
