# Déploiement de TalentGraph (module M8)

Le site est en ligne sur **https://talent-graph.cloud**.

Ce document explique comment le serveur est configuré, comment l'application y
arrive, et comment la mettre à jour.

## 1. Vue d'ensemble

```
 Ton PC              GitHub                                    Serveur (VPS OVH)
git push ──▶ dépôt ──▶ GitHub Actions ──▶ ghcr.io      ◀── docker compose pull
                       (construit les     (stocke les       docker compose up -d
                        4 images)          images)

Visiteur ──https (443)──▶ Caddy ──▶ frontend (nginx) ──▶ api ──▶ PostgreSQL / Redis / Elasticsearch
                          (seul service publié)         (réseau Docker privé, invisible depuis Internet)
```

- **Le serveur ne construit rien** : il télécharge des images déjà prêtes. Il
  n'a pas besoin du code source.
- **Une seule porte d'entrée** : Caddy, sur les ports 80 et 443. Tout le reste
  n'est joignable que par les autres conteneurs.

## 2. Le serveur

| | |
|---|---|
| Hébergeur | OVHcloud, VPS-2 (4 vCore, 8 Go de RAM, 75 Go), Canada |
| Système | Ubuntu 26.04 |
| Adresse IPv4 | 148.113.237.246 |
| Utilisateur | `ubuntu` |
| Nom de domaine | `talent-graph.cloud` (OVH), `www` redirigé vers l'adresse sans `www` |

### Sécurité

- **SSH par clé** : la clé publique `id_ed25519_talentgraph.pub` est dans
  `~/.ssh/authorized_keys` du serveur ; la clé privée ne quitte jamais le PC.
  Raccourci dans `~/.ssh/config` du PC : `ssh talentgraph`.
- **Pare-feu `ufw`** : seuls les ports **22** (SSH), **80** (HTTP, redirection)
  et **443** (HTTPS) sont ouverts.
- **Docker contourne `ufw`** : un port publié dans un compose est ouvert sur
  Internet même si le pare-feu le bloque. Le compose de production ne publie
  donc **que** les ports de Caddy.
- **Mots de passe** : le fichier `.env` du serveur contient un mot de passe
  PostgreSQL aléatoire (`openssl rand -hex 32`), lisible seulement par
  `ubuntu` (`chmod 600`). Il n'est ni dans git, ni dans les images.

### Logiciels installés

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2      # Docker + docker compose
sudo usermod -aG docker ubuntu                       # docker sans sudo
echo "vm.max_map_count=262144" | sudo tee /etc/sysctl.d/99-elasticsearch.conf
sudo sysctl --system                                 # réglage requis par Elasticsearch
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable
```

## 3. Les images (GitHub Actions + ghcr.io)

Le workflow `.github/workflows/docker-images.yml` se déclenche à chaque push sur
`main` (ou à la main, bouton « Run workflow »). Il construit et publie 4 images :

| Image | Dockerfile |
|---|---|
| `ghcr.io/yasmine-bj/talentgraph-api` | `api/Dockerfile` |
| `ghcr.io/yasmine-bj/talentgraph-loader` | `worker/Dockerfile` (contexte = racine) |
| `ghcr.io/yasmine-bj/talentgraph-frontend` | `frontend/Dockerfile` |
| `ghcr.io/yasmine-bj/talentgraph-postgres` | `infra/postgres/Dockerfile` |

Chaque image a deux étiquettes : `latest` et `sha-<commit>`. Les packages sont
**publics** : le serveur les télécharge sans se connecter.

Redis, Elasticsearch et Caddy utilisent leurs images officielles.

## 4. Les fichiers sur le serveur

```
~/talentgraph/
├── docker-compose.yml   ← copie de deploy/docker-compose.prod.yml
├── Caddyfile            ← copie de deploy/Caddyfile
└── .env                 ← POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DOMAIN
```

`.env` suit le modèle `deploy/.env.prod.example`.

## 5. Première installation

Sur le PC, à la racine du projet :

```powershell
ssh talentgraph "mkdir -p ~/talentgraph"
scp deploy/docker-compose.prod.yml talentgraph:~/talentgraph/docker-compose.yml
scp deploy/Caddyfile talentgraph:~/talentgraph/Caddyfile
scp deploy/.env.prod.example talentgraph:~/talentgraph/.env
```

Sur le serveur :

```bash
cd ~/talentgraph
sed -i "s/CHANGE_ME/$(openssl rand -hex 32)/" .env   # mot de passe aléatoire, jamais affiché
chmod 600 .env
docker compose config --quiet && echo "configuration OK"
docker compose pull
docker compose up -d
docker compose logs -f loader     # attendre "exited with code 0", puis Ctrl+C
docker compose logs caddy         # chercher "certificate obtained successfully"
```

⚠️ Le DNS du domaine doit **déjà** pointer vers l'IP du serveur (enregistrements
A de `talent-graph.cloud` et `www.talent-graph.cloud`) avant le premier
démarrage de Caddy : Let's Encrypt vérifie le domaine en passant par le port 80.

## 6. Mettre à jour l'application

1. Merger les changements dans `main` et pousser : GitHub Actions publie les
   nouvelles images (onglet **Actions**, attendre les 4 jobs verts).
2. Sur le serveur :

```bash
cd ~/talentgraph
docker compose pull      # télécharge seulement les images qui ont changé
docker compose up -d     # recrée seulement les conteneurs concernés
```

Les données restent dans les volumes (`pg_data`, `redis_data`, `es_data`,
`hf_cache`, `caddy_data`).

Si `deploy/docker-compose.prod.yml` ou `deploy/Caddyfile` ont changé, les
recopier d'abord avec `scp` (voir section 5).

## 7. Vérifier la persistance en production

```bash
cd ~/talentgraph
docker compose exec postgres psql -U talentgraph -d talentgraph
docker compose exec redis redis-cli
```

Mêmes requêtes que dans le README (section « Vérifier la persistance »).
Elasticsearch n'étant pas publié, on l'interroge depuis un conteneur :

```bash
docker compose exec elasticsearch curl -s http://localhost:9200/offers/_count
```

## 8. Commandes utiles

| Commande | Rôle |
|---|---|
| `docker compose ps -a` | état des conteneurs |
| `docker compose logs -f api` | messages de l'API en direct |
| `docker compose restart` | redémarrer tous les conteneurs (les données restent) |
| `docker compose down` | tout arrêter (les données restent) |
| `docker compose down -v` | ⚠️ tout arrêter ET supprimer les données |

## 9. Limites connues

- Le serveur contient les **1 794 offres de démonstration** (`seed/demo_offers.json`).
  Le chargement de toutes les offres et la mise à jour quotidienne sont prévus
  au module M9 (`feature/m9-daily-refresh`).
- L'authentification SSH par mot de passe est encore active (la clé fonctionne) :
  à désactiver.
- Pas encore de sauvegarde automatique de PostgreSQL (prévue dans les finitions).
