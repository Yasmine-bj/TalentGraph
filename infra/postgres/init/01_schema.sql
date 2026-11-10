-- =============================================================================
-- 01_schema.sql — Création des tables de TalentGraph (module M2)
--
-- QUAND CE FICHIER EST-IL EXÉCUTÉ ?
--   Automatiquement par PostgreSQL, au PREMIER démarrage du conteneur,
--   c'est-à-dire quand le volume pg_data est VIDE.
--   docker-compose.yml monte le dossier infra/postgres/init/ dans le dossier
--   spécial /docker-entrypoint-initdb.d/ du conteneur : l'image officielle
--   exécute tous les fichiers .sql qu'elle y trouve, par ordre alphabétique
--   (d'où le préfixe 01_, 02_...).
--   Volume déjà rempli -> fichier IGNORÉ. Pour le rejouer en local :
--       docker compose down -v      (supprime les volumes, donc les données)
--       docker compose up -d
--
-- RÔLE DE POSTGRESQL DANS LE PROJET (voir docs/decisions.md, D1) :
--   la SOURCE DE VÉRITÉ. Elasticsearch, lui, n'est qu'un index de recherche
--   reconstruit à partir de ces tables.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- TABLE offers : une ligne par offre d'emploi
-- -----------------------------------------------------------------------------
CREATE TABLE offers (
    -- Identifiant INTERNE, généré par PostgreSQL (1, 2, 3...).
    -- GENERATED ALWAYS AS IDENTITY : la syntaxe standard SQL moderne
    -- (équivalent de BIGSERIAL, en plus strict : on ne peut pas forcer
    -- une valeur à la main par erreur).
    -- BIGINT : entier sur 8 octets, largement assez pour des millions d'offres.
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Identifiant chez la SOURCE (ex. "adzuna", "5937384042").
    -- Le couple est UNIQUE (contrainte plus bas) : c'est la clé de l'UPSERT,
    -- qui reconnaît une offre déjà connue quand la source nous la renvoie.
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,

    -- Contenu de l'offre
    title            TEXT NOT NULL,
    company          TEXT,                        -- parfois absent
    description      TEXT NOT NULL,               -- extrait (~500 caractères chez Adzuna)
    url              TEXT NOT NULL,               -- lien vers l'annonce

    -- Localisation
    location_label   TEXT,                        -- libellé d'affichage, ex. "Brest, Finistère"
    region           TEXT,                        -- NULL = offre nationale / lieu non précisé
    department       TEXT,
    city             TEXT,
    -- DOUBLE PRECISION : nombre à virgule (environ 15 chiffres significatifs).
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,

    -- Contrat (déduit par worker/contracts.py, voir decisions.md D8)
    -- TEXT[] : un TABLEAU de textes, ex. '{alternance,stage}'.
    contract_types   TEXT[] NOT NULL,
    contract_source  TEXT NOT NULL,               -- d'où vient le contrat
    contract_raw     TEXT,                        -- valeur brute de la source ("permanent"...)
    contract_time    TEXT,                        -- "full_time", "part_time" ou NULL

    -- Classement
    category         TEXT,                        -- catégorie de la source (peu fiable)
    search_keywords  TEXT,                        -- recherche d'origine, ex. "data [alternance]"

    -- Salaire annuel en euros, quand il est indiqué (~37 % des offres).
    -- NUMERIC(10, 2) : nombre EXACT, 10 chiffres dont 2 après la virgule
    -- (pas d'arrondi binaire comme avec DOUBLE PRECISION : adapté à l'argent).
    salary_min       NUMERIC(10, 2),
    salary_max       NUMERIC(10, 2),

    -- Dates. TIMESTAMPTZ = date + heure + fuseau horaire.
    published_at     TIMESTAMPTZ,                 -- date de publication (source)
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),  -- 1re fois qu'on l'a chargée
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),  -- dernière fois qu'on l'a revue

    -- Cycle de vie (decisions.md D12) : suppression LOGIQUE.
    -- Une offre trop ancienne passe à 'expired' au lieu d'être effacée :
    -- on la garde pour les statistiques, mais on ne la propose plus.
    status           TEXT NOT NULL DEFAULT 'active',

    -- L'offre BRUTE complète, telle que renvoyée par la source.
    -- JSONB : JSON stocké en binaire, interrogeable en SQL
    -- (ex. raw->'location'->'area'). Permet de retraiter sans le cache.
    raw              JSONB NOT NULL,

    -- -------------------------------------------------------------------------
    -- CONTRAINTES : la base PROTÈGE elle-même la qualité des données,
    -- même si le code Python a un bug. Une ligne invalide est REFUSÉE.
    -- On les nomme (CONSTRAINT nom ...) pour avoir des messages d'erreur clairs.
    -- -------------------------------------------------------------------------

    -- Pas deux fois la même offre d'une même source.
    -- Crée automatiquement un index unique (recherche rapide + UPSERT).
    CONSTRAINT offers_source_uk UNIQUE (source, source_id),

    -- Contrats : au moins un, et uniquement des valeurs de notre liste fermée.
    --   cardinality(...) : nombre d'éléments du tableau
    --   <@               : "est contenu dans" (chaque élément est dans la liste)
    CONSTRAINT offers_contract_types_ck CHECK (
        cardinality(contract_types) >= 1
        AND contract_types <@ ARRAY['cdi', 'cdd', 'stage', 'alternance', 'freelance', 'inconnu']
    ),
    CONSTRAINT offers_contract_source_ck CHECK (
        contract_source IN ('title', 'description', 'keywords', 'adzuna', 'none')
    ),
    CONSTRAINT offers_status_ck CHECK (status IN ('active', 'expired')),

    -- Salaires cohérents (NULL accepté : un salaire absent n'est pas une erreur).
    CONSTRAINT offers_salary_ck CHECK (
        (salary_min IS NULL OR salary_min >= 0)
        AND (salary_max IS NULL OR salary_max >= 0)
        AND (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max)
    )
);

-- -----------------------------------------------------------------------------
-- INDEX de la table offers
-- Uniquement sur les colonnes souvent FILTRÉES (un index ralentit un peu les
-- écritures et prend de la place : on n'en met pas partout).
-- L'index unique (source, source_id) existe déjà grâce à la contrainte UNIQUE.
-- -----------------------------------------------------------------------------

-- B-tree (index par défaut) : égalité, tri, intervalles.
CREATE INDEX offers_region_idx       ON offers (region);        -- filtre région du formulaire
CREATE INDEX offers_status_idx       ON offers (status);        -- n'afficher que les offres actives
CREATE INDEX offers_published_at_idx ON offers (published_at);  -- expiration (> 45 jours)

-- GIN (index INVERSÉ) : "le tableau CONTIENT 'alternance'".
-- Utilisé par les requêtes du type :  WHERE contract_types @> ARRAY['alternance']
CREATE INDEX offers_contract_types_idx ON offers USING GIN (contract_types);


-- -----------------------------------------------------------------------------
-- TABLE ingestion_runs : le JOURNAL des chargements d'offres
--
-- Une ligne par exécution du chargement (load_offers.py, puis la mise à jour
-- quotidienne). Elle répond à : "quand les offres ont-elles été chargées ?
-- combien de nouvelles ? combien mises à jour ? est-ce que ça a planté ?"
--   - suivi et débogage (une exécution 'failed' avec son message d'erreur) ;
--   - preuve que la mise à jour quotidienne tourne ;
--   - statistiques pour la présentation (offres nouvelles par jour).
-- -----------------------------------------------------------------------------
CREATE TABLE ingestion_runs (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source           TEXT NOT NULL,                    -- ex. "adzuna"
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,                      -- NULL tant que l'exécution tourne
    status           TEXT NOT NULL DEFAULT 'running',

    -- Compteurs (remplis à la fin de l'exécution)
    api_calls        INTEGER,                          -- appels consommés (NULL si chargement depuis un fichier)
    offers_received  INTEGER NOT NULL DEFAULT 0,       -- offres lues
    offers_inserted  INTEGER NOT NULL DEFAULT 0,       -- nouvelles offres
    offers_updated   INTEGER NOT NULL DEFAULT 0,       -- offres déjà connues, mises à jour
    offers_expired   INTEGER NOT NULL DEFAULT 0,       -- passées à 'expired'

    error_message    TEXT,                             -- rempli si status = 'failed'
    params           JSONB,                            -- paramètres utilisés (fichier, recherches...)

    CONSTRAINT ingestion_runs_status_ck CHECK (status IN ('running', 'success', 'failed'))
);

-- Retrouver rapidement les dernières exécutions ("ORDER BY started_at DESC").
CREATE INDEX ingestion_runs_started_at_idx ON ingestion_runs (started_at);
