# =============================================================================
# Image du conteneur "loader" (livraison, D10) : remplit les bases si besoin
# (worker/bootstrap.py), puis s'arrête.
#
# CONTEXTE DE BUILD : la RACINE du projet (voir docker-compose.yml), pour
# copier, en plus du code, le mapping Elasticsearch et le seed de démo.
# L'image est ainsi AUTONOME : elle contient tout ce dont elle a besoin,
# et pourra être publiée telle quelle sur un registre (GitHub Container
# Registry), puis téléchargée par le serveur sans le code du dépôt.
# Ce qui entre dans le contexte : voir le .dockerignore de la racine.
# =============================================================================

# Même image de base que l'API : même version de Python partout.
FROM python:3.11-slim

# Pas de fichiers .pyc ; affichage immédiat des print() dans les logs
# (sinon les messages du loader arriveraient en retard dans "docker compose logs").
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Les dépendances D'ABORD (couche mise en cache) : tant que
#    requirements.txt ne change pas, Docker ne réinstalle pas torch & co
#    à chaque modification du code.
#    Les chemins sont relatifs au CONTEXTE (la racine) : worker/requirements.txt.
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Le code du worker, dans /app.
COPY worker/ /app/

# 3) Les fichiers lus par les scripts, aux chemins qu'ils attendent déjà :
#    Path(__file__).resolve().parent.parent = "/" dans le conteneur, donc
#      index_offers.py cherche /infra/elasticsearch/offers_mapping.json
#      bootstrap.py    cherche /seed/demo_offers.json
#    -> aucun chemin à modifier dans le code.
COPY infra/elasticsearch/ /infra/elasticsearch/
COPY seed/demo_offers.json /seed/demo_offers.json

# Le programme du loader : vérifier, charger si besoin, indexer si besoin.
CMD ["python", "bootstrap.py"]
