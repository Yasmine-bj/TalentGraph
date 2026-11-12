# =============================================================================
# Image du conteneur "frontend" : la page React, servie par nginx.
#
# BUILD EN DEUX ÉTAPES (multi-stage) :
#   1. "build" : Node.js installe les dépendances et Vite construit la page
#      (dossier dist/ : index.html + .js + .css) ;
#   2. image finale : nginx + UNIQUEMENT le dossier dist/.
#      Ni Node.js, ni node_modules, ni le code source .jsx dans l'image finale :
#      elle est petite et ne contient que ce qui sert.
# =============================================================================

# ---- Étape 1 : construire --------------------------------------------------
# Même version majeure de Node que sur le PC de développement (26 LTS).
FROM node:26-alpine AS build
WORKDIR /app

# Dépendances D'ABORD (couche mise en cache tant qu'elles ne changent pas).
# npm ci : installe EXACTEMENT les versions de package-lock.json.
COPY package.json package-lock.json ./
RUN npm ci

# Le code, puis la construction : vite build -> /app/dist
COPY . .
RUN npm run build

# ---- Étape 2 : servir ------------------------------------------------------
FROM nginx:stable-alpine

# Seulement le résultat de l'étape 1 (--from=build).
COPY --from=build /app/dist /usr/share/nginx/html
# Notre configuration (page + proxy /api) remplace celle par défaut.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# (Pas de CMD : celle de l'image nginx démarre déjà le serveur.)
