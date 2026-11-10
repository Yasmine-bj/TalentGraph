# =============================================================================
# api/Dockerfile — La "recette" de l'image du conteneur "api" (module M3)
#
# POURQUOI CE FICHIER ?
#   Pour PostgreSQL, Redis et Elasticsearch, on télécharge des images toutes
#   prêtes (postgres:16, redis:7...). Notre API, elle, est NOTRE code : aucune
#   image n'existe. Ce fichier décrit comment la construire.
#
# VOCABULAIRE :
#   Dockerfile = la recette
#   image      = le résultat de la recette (un "plat emballé", prêt à servir)
#   conteneur  = l'image EN MARCHE (le plat servi)
#
# QUAND EST-IL UTILISÉ ?
#   docker compose up -d --build
#   -> Docker lit ce fichier, exécute les instructions DANS L'ORDRE pour
#      construire l'image, puis démarre un conteneur à partir de cette image.
#   Le même fichier produit la même image chez toi, chez le correcteur et
#   sur le serveur VPS : fini le "ça marche sur ma machine".
#
# LE CACHE (important pour l'ordre des instructions) :
#   Docker construit l'image ÉTAPE PAR ÉTAPE et garde chaque étape en mémoire.
#   Au build suivant, il RÉUTILISE les étapes dont rien n'a changé et ne
#   refait que la suite. On place donc ce qui change RAREMENT (les
#   bibliothèques) AVANT ce qui change SOUVENT (notre code).
# =============================================================================


# -----------------------------------------------------------------------------
# 1. IMAGE DE DÉPART
# -----------------------------------------------------------------------------
# On ne part jamais de zéro : on prend l'image officielle de Python, où
# Python 3.11 est déjà installé (même version que sur ton PC), et on ajoute
# notre code par-dessus.
# "slim" : variante allégée (~150 Mo au lieu de ~1 Go), sans les outils
# superflus.
FROM python:3.11-slim


# -----------------------------------------------------------------------------
# 2. RÉGLAGES DE PYTHON (variables d'environnement fixées dans l'image)
# -----------------------------------------------------------------------------
# PYTHONDONTWRITEBYTECODE=1 : ne pas créer les fichiers .pyc / __pycache__
#                             (inutiles dans un conteneur).
# PYTHONUNBUFFERED=1        : afficher les print() IMMÉDIATEMENT dans les logs
#                             ("docker compose logs api"). Sans ça, Python garde
#                             parfois les messages en mémoire avant de les
#                             afficher : déroutant quand on cherche une erreur.
# Le "\" en fin de ligne signifie : l'instruction continue à la ligne suivante.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# -----------------------------------------------------------------------------
# 3. DOSSIER DE TRAVAIL DANS LE CONTENEUR
# -----------------------------------------------------------------------------
# Équivalent d'un "cd /app" (le dossier est créé s'il n'existe pas) :
# les instructions suivantes (COPY, RUN, CMD) se font dans /app.
WORKDIR /app


# -----------------------------------------------------------------------------
# 4. INSTALLATION DES BIBLIOTHÈQUES (avant le code, pour le cache)
# -----------------------------------------------------------------------------
# COPY <sur ton PC> <dans l'image>
#   Copie api/requirements.txt de ton PC vers /app/ dans l'image
#   ("." = le dossier de travail, donc /app).
COPY requirements.txt .

# RUN : exécute une commande PENDANT LA CONSTRUCTION de l'image.
#   pip install -r requirements.txt : installe les bibliothèques listées.
#   --no-cache-dir : pip ne garde pas ses fichiers temporaires (image plus légère).
# Grâce au cache, cette étape (1 à 2 minutes) n'est refaite QUE si
# requirements.txt change. Modifier main.py ne la relance pas.
RUN pip install --no-cache-dir -r requirements.txt


# -----------------------------------------------------------------------------
# 5. COPIE DE NOTRE CODE
# -----------------------------------------------------------------------------
# Le dossier api/app/ de ton PC devient /app/app/ dans l'image.
# (Les fichiers listés dans api/.dockerignore, comme __pycache__, sont exclus.)
COPY app ./app


# -----------------------------------------------------------------------------
# 6. PORT D'ÉCOUTE (documentation)
# -----------------------------------------------------------------------------
# EXPOSE n'ouvre RIEN : c'est une indication ("ce conteneur écoute sur le
# port 8000"). C'est la ligne ports: "8000:8000" de docker-compose.yml qui
# rend vraiment ce port accessible depuis ton PC.
EXPOSE 8000


# -----------------------------------------------------------------------------
# 7. COMMANDE DE DÉMARRAGE DU CONTENEUR
# -----------------------------------------------------------------------------
# CMD n'est PAS exécutée pendant la construction (contrairement à RUN) :
# elle est lancée À CHAQUE DÉMARRAGE du conteneur.
#
# Elle équivaut à taper dans un terminal :
#     uvicorn app.main:app --host 0.0.0.0 --port 8000
#
#   uvicorn        : le SERVEUR web ; il écoute sur un port et transmet
#                    chaque requête HTTP reçue à notre application FastAPI.
#   app.main:app   : OÙ trouver l'application, au format "module:objet" :
#                      app.main -> le fichier app/main.py
#                      :app     -> la variable nommée "app" dans ce fichier
#                                  (app = FastAPI(...))
#   --host 0.0.0.0 : SUR QUELLES ADRESSES RÉSEAU écouter. 0.0.0.0 = "sur
#                    toutes les interfaces réseau du conteneur", donc accepter
#                    les connexions venant de L'EXTÉRIEUR du conteneur
#                    (ton navigateur, le futur frontend, les autres
#                    conteneurs). Avec 127.0.0.1 (valeur par défaut
#                    d'uvicorn), il n'accepterait que les connexions venant
#                    de l'INTÉRIEUR du conteneur : personne ne pourrait le joindre.
#   --port 8000    : le numéro de port d'écoute.
#
# Format ["...", "..."] (liste) : la commande est lancée directement, sans
# passer par un shell ; c'est la forme recommandée par Docker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
