# =============================================================================
# infra/postgres/Dockerfile — Image PostgreSQL de TalentGraph (module M8)
#
# POURQUOI UNE IMAGE À NOUS ?
#   Les scripts SQL qui créent les tables (init/01_schema.sql,
#   init/02_candidates.sql) étaient MONTÉS depuis le dossier du projet
#   (./infra/postgres/init). Sur le serveur, il n'y a PAS de dossier du
#   projet : on y télécharge seulement des images (ghcr.io).
#   -> On COPIE les scripts DANS l'image : elle crée ses tables toute seule,
#      sur ton PC, chez le correcteur et sur le serveur.
#
# COMMENT ÇA MARCHE ?
#   L'image officielle exécute les fichiers .sql de /docker-entrypoint-initdb.d/
#   au PREMIER démarrage uniquement (quand le volume de données est vide),
#   par ordre alphabétique (01_ puis 02_). Ensuite, elle ne les relit plus :
#   les données existantes ne sont jamais écrasées.
# =============================================================================

# Même version que jusqu'ici (postgres:16) : rien ne change pour la base.
FROM postgres:16

# Le dossier init/ (à côté de ce Dockerfile) devient le dossier spécial
# d'initialisation de l'image.
COPY init/ /docker-entrypoint-initdb.d/
