-- =============================================================================
-- 02_candidates.sql — Tables des candidats et de leurs demandes (module M3)
--
-- RÔLE :
--   Enregistrer ce que l'utilisateur saisit dans le FORMULAIRE de l'application :
--     - candidates : la personne (nom, email, CV) ;
--     - searches   : chaque DEMANDE qu'elle fait (mode, critères, statut, résultat).
--   Un candidat peut faire plusieurs demandes : relation UN-À-PLUSIEURS.
--
-- QUAND CE FICHIER EST-IL EXÉCUTÉ ?
--   Automatiquement au premier démarrage de PostgreSQL (volume VIDE), après
--   01_schema.sql (ordre alphabétique) : chez le correcteur et sur le serveur.
--   Sur un volume déjà rempli (ton PC), il faut l'exécuter UNE FOIS à la main :
--     docker compose exec postgres psql -U talentgraph -d talentgraph
--         -f /docker-entrypoint-initdb.d/02_candidates.sql
-- =============================================================================


-- -----------------------------------------------------------------------------
-- TABLE candidates : une ligne par personne
-- -----------------------------------------------------------------------------
CREATE TABLE candidates (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name   TEXT NOT NULL,
    -- Une personne = un email. Si elle revient avec le même email, l'API met à
    -- jour sa fiche (UPSERT sur cette contrainte) au lieu de créer un doublon.
    email       TEXT NOT NULL,
    -- Texte du CV (collé dans le formulaire, ou extrait d'un PDF au M3c).
    cv_text     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT candidates_email_uk UNIQUE (email),
    -- Garde-fous : nom non vide, email avec un "@" (la vraie vérification
    -- du format est faite par l'API, avec la bibliothèque email-validator).
    CONSTRAINT candidates_full_name_ck CHECK (length(trim(full_name)) > 0),
    CONSTRAINT candidates_email_ck CHECK (position('@' IN email) > 1)
);


-- -----------------------------------------------------------------------------
-- TABLE searches : une ligne par demande faite via le formulaire
-- -----------------------------------------------------------------------------
CREATE TABLE searches (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- CLÉ ÉTRANGÈRE : la demande appartient à un candidat qui DOIT exister.
    --   REFERENCES candidates (id) : PostgreSQL refuse un candidate_id inconnu.
    --   ON DELETE CASCADE : supprimer un candidat supprime aussi ses demandes
    --   (utile pour le droit à l'effacement des données personnelles, RGPD).
    candidate_id    BIGINT NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,

    -- Le mode choisi dans le formulaire :
    --   offers = 1. offres compatibles       skills = 2. compétences à travailler
    --   cv     = 3. améliorer mon CV         letter = 4. lettre de motivation
    mode            TEXT NOT NULL,

    -- Critères de recherche (tous facultatifs sauf le mode).
    job_title       TEXT,                    -- métier recherché, ex. "data engineer"
    region          TEXT,                    -- NULL = toute la France
    contract_types  TEXT[] NOT NULL DEFAULT '{}',  -- contrats cochés ; {} = tous
    salary_min      NUMERIC(10, 2),

    -- Cycle de traitement : pending (reçue) -> running (en cours) -> done / failed.
    -- Le statut EN DIRECT est aussi dans Redis (lu très souvent par la page web) ;
    -- ici, c'est la version durable.
    status          TEXT NOT NULL DEFAULT 'pending',
    results         JSONB,                   -- résultat final (offres, conseils...), M4/M5
    error_message   TEXT,                    -- rempli si status = 'failed'

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,             -- NULL tant que la demande n'est pas terminée

    CONSTRAINT searches_mode_ck CHECK (mode IN ('offers', 'skills', 'cv', 'letter')),
    CONSTRAINT searches_status_ck CHECK (status IN ('pending', 'running', 'done', 'failed')),
    -- Mêmes valeurs que les offres, sans "inconnu" (on ne coche pas "inconnu").
    CONSTRAINT searches_contract_types_ck CHECK (
        contract_types <@ ARRAY['cdi', 'cdd', 'stage', 'alternance', 'freelance']
    ),
    CONSTRAINT searches_salary_ck CHECK (salary_min IS NULL OR salary_min >= 0)
);

-- Index sur la clé étrangère : retrouver vite "toutes les demandes du candidat 3".
-- (PostgreSQL ne le crée PAS automatiquement, contrairement à une clé primaire.)
CREATE INDEX searches_candidate_id_idx ON searches (candidate_id);

-- Les demandes les plus récentes en premier (historique, statistiques).
CREATE INDEX searches_created_at_idx ON searches (created_at);
