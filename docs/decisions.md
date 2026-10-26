# Journal des décisions

## D1 — PostgreSQL, Elasticsearch et Redis (au lieu de Neo4j / MongoDB)
- Décision : ...
- Pourquoi : ...
- Alternatives écartées : Neo4j (relations trop simples pour un graphe), MongoDB (doublon avec PostgreSQL JSONB).

## D2 — Redis en mode AOF
- Décision : `--appendonly yes`.
- Pourquoi : la persistance doit être démontrable ; le mode RDB par défaut peut perdre les dernières écritures.

## D3 — Sécurité Elasticsearch désactivée en local
- Décision : `xpack.security.enabled=false` en développement uniquement.
- À faire au déploiement : réactiver la sécurité ou ne pas exposer le port 9200.