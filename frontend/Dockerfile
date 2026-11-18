# frontend/Dockerfile — image du frontend en DEUX ÉTAPES (multi-stage build).
#
# Étape 1 "build" : une image Node complète (~400 Mo) installe les dépendances
#   et lance "npm run build". Vite produit le dossier dist/ : du HTML, du CSS
#   et du JavaScript STATIQUES (plus besoin de Node pour les servir).
# Étape 2 : une image nginx minuscule (~50 Mo) qui ne contient QUE dist/.
#   Node, node_modules et le code source restent dans l'étape 1, jetée à la fin.
# Résultat : une image finale légère, sans outils de développement.

# ---------- Étape 1 : construire l'application ----------
# Même version majeure de Node que sur le PC (26) ; "alpine" = Linux très léger.
FROM node:26-alpine AS build
WORKDIR /app

# On copie D'ABORD package.json + package-lock.json, puis on installe.
# Docker met chaque étape en CACHE : tant que ces deux fichiers ne changent pas,
# "npm ci" n'est pas refait, même si le code de src/ change. Builds bien plus rapides.
COPY package.json package-lock.json ./
# npm ci (et pas npm install) : installe EXACTEMENT les versions du package-lock.json.
RUN npm ci

# Puis le reste du code (voir .dockerignore : node_modules et dist sont exclus).
COPY . .
RUN npm run build

# ---------- Étape 2 : servir les fichiers avec nginx ----------
FROM nginx:stable-alpine

# Notre configuration (fichiers statiques + reverse proxy vers l'API),
# à la place de celle fournie par défaut avec l'image.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# --from=build : on prend dist/ dans l'image de l'étape 1.
COPY --from=build /app/dist /usr/share/nginx/html

# Documentation : nginx écoute sur le port 80 DANS le conteneur
# (docker-compose.yml le publie sur le port 3000 du PC).
EXPOSE 80
# Pas de CMD : celle de l'image nginx (lancer nginx au premier plan) convient.
