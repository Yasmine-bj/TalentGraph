# Journal des décisions

Chaque décision technique importante : ce qui a été choisi, pourquoi, et les alternatives écartées.

## D1 — PostgreSQL, Elasticsearch et Redis (au lieu de Neo4j / MongoDB)
- Décision : trois bases, chacune avec un rôle distinct.
  - PostgreSQL : source de vérité (candidats, CV, offres, compétences, exécutions, résultats).
  - Elasticsearch : index de recherche des offres (recherche hybride BM25 + vecteurs, filtres, agrégations).
  - Redis : données rapides et temporaires (cache des réponses LLM, file de tâches, statut des agents en direct).
- Pourquoi : chaque base fait ce que les autres font mal. PostgreSQL garantit l'intégrité et les relations ; Elasticsearch apporte une recherche de qualité (pertinence, tolérance aux fautes, recherche sémantique) ; Redis répond en quelques microsecondes. Les trois sont très utilisées en entreprise.
- Alternatives écartées :
  - Neo4j : les relations du projet (offres ↔ compétences, prérequis sur peu de niveaux) se traitent en SQL ; une base graphe n'est justifiée que pour des parcours profonds ou des algorithmes de graphe.
  - MongoDB : ferait doublon avec PostgreSQL, qui stocke déjà du JSON flexible avec le type JSONB.

## D2 — Redis en mode AOF
- Décision : `--appendonly yes`.
- Pourquoi : la persistance doit être démontrable ; le mode RDB par défaut peut perdre les dernières écritures.

## D3 — Sécurité Elasticsearch désactivée en local
- Décision : `xpack.security.enabled=false` en développement uniquement.
- À faire au déploiement : réactiver la sécurité ou ne pas exposer le port 9200.

## D4 — Source des offres : Adzuna au lieu de France Travail
- Contexte : l'API Offres d'emploi de France Travail fait l'objet d'une mesure conservatoire et n'est plus ouverte à la souscription, sans date de réouverture (réponse du support, incident INC2769592, octobre 2026). Les identifiants obtenus étaient refusés (`invalid_client`).
- Décision : Adzuna comme source principale (abonnement de 8 £ par mois, 500 appels par jour, 5 000 par mois).
- Conséquences :
  - descriptions tronquées (extraits) : moins de matière pour l'extraction des compétences ;
  - pas de code métier ROME : le métier sera déduit de la catégorie Adzuna ou par le LLM.
- Mesures prises :
  - un adaptateur par source (`worker/sources/`) qui convertit vers un format interne commun (`JobOffer`), pour pouvoir ajouter ou changer de source sans toucher au reste du projet ;
  - un cache des réponses brutes (`seed/raw/`), pour ne jamais payer deux fois le même appel et garder les données si l'API change à nouveau.
- Alternatives envisagées : Jooble, Careerjet (accès à demander, couverture incertaine), jeux de données statiques (offres anciennes), scraping (écarté : contraire aux conditions d'utilisation des sites).

## D5 — Collecte nationale et recherches diversifiées
- Décision : chercher dans **toute la France** (pas de paramètre `where`) avec 26 recherches réparties en 5 familles de métiers (data & IA, développement, cloud & infra, cybersécurité, + recherches ciblées stage/alternance).
- Pourquoi :
  - mesure (`explore/page_size.py`) : « data engineer » = 2 277 offres en France, dont seulement 839 dans Paris intra-muros (rayon par défaut de 5 km) → chercher par ville ratait 63 % des offres ;
  - chaque offre garde sa localisation : le filtre par lieu se fait dans NOTRE base, au moment de la recherche de l'utilisateur ;
  - 26 recherches nationales coûtent moins d'appels que 12 recherches × 5 villes.
- Règles d'écriture des mots-clés (`what` exige TOUS les mots, n'importe où dans l'offre) :
  - mots-clés courts, sans « engineer » imposé : `devops` trouve « Ingénieur DevOps » et « DevOps Engineer » ;
  - pas de quasi-doublons (« AI engineer » / « ingénieur IA » / « ML engineer ») ;
  - `cloud` exigé dans le titre (`title_only`), car le mot est cité dans énormément d'offres.
- Alternatives écartées :
  - 5 grandes villes : couverture trop faible (Bordeaux, Rennes, Marseille… absentes) ;
  - filtre `category=it-jobs` : 50 offres → 4, les catégories Adzuna sont mal remplies (« Unknown », « Emplois Diplômés »…) ;
  - `where` + `distance` ou `location0/1/2` : utiles pour une recherche locale, inutiles avec une collecte nationale.
- Résultat (29/10/2026) : 8 531 offres ramenées, **7 298 uniques**, 14 % de doublons entre recherches, environ 175 appels.

## D6 — Recherches ciblées stage / alternance avec `title_only`
- Décision : pour les stages et alternances, `what` = le domaine (« data », « développeur », « cybersécurité ») et `title_only` = le contrat.
- Pourquoi (test `explore/explore_filters.py`, alternances data à Paris) :

  | Recherche | Offres | Alternance dans le titre |
  |---|---|---|
  | `what="alternance data"` | 27 | 70 % |
  | `what="data"` + `title_only="alternance"` | 50 (page pleine) | 100 % |
  | idem + `category="it-jobs"` | 4 | 100 % |

- Limite : uniquement pour stage et alternance. Les recruteurs écrivent presque toujours ces mots dans le titre, mais rarement « CDI » : `title_only="cdi"` perdrait la plupart des CDI.

## D7 — Paramètres de collecte
- `results_per_page=50` : maximum d'Adzuna, vérifié (demander 100 renvoie 50).
- Arrêt anticipé : une page incomplète (< 50 offres) est la dernière, on ne demande pas la suivante. Vérifié : les pages sont pleines tant qu'il reste des offres.
- `PAGES_PER_SEARCH=8` (400 offres max par recherche) : on privilégie la diversité des métiers plutôt que la profondeur ; 26 × 8 = 208 appels max, dans le quota du jour.
- `max_days_old=30` : les offres plus anciennes sont souvent pourvues.
- Tri par pertinence (défaut) plutôt que `sort_by=date` : avec 8 pages, on veut les offres qui correspondent le MIEUX ; la fraîcheur est assurée par `max_days_old`. `sort_by=date` servira à la mise à jour quotidienne.
- Robustesse : jusqu'à 3 nouvelles tentatives (5 s, 15 s, 30 s) sur erreur réseau, 429 et 5xx ; pas sur 400 / 410 (erreurs définitives). Pause de 3 s uniquement après un vrai appel.
- Sécurité : la clé passe dans l'URL ; aucune erreur ne doit afficher l'URL (`_safe_get`, pas de `raise_for_status()`).
- Quotas de l'abonnement : 50 appels/minute, 500/jour, 2 000/semaine, 5 000/mois.

## D8 — Détection du type de contrat
- Problème : le champ `contract_type` d'Adzuna est vide pour 63 % des offres et ne distingue ni stage ni alternance.
- Décision : `worker/contracts.py` déduit le contrat, dans l'ordre de confiance :
  1. le titre (motifs larges) ;
  2. la description (motifs STRICTS) ;
  3. les mots-clés de la recherche ;
  4. le champ brut `permanent` → cdi ;
  5. sinon « inconnu ».
- Motifs stricts pour la description : des mots isolés y sont ambigus. Bugs trouvés avec un motif unique : « apprentissage automatique » (machine learning) → alternance, « early-stage startup » → stage, « solutions alternatives » → alternance, « de manière indépendante » → freelance. On exige des expressions (« en alternance », « contrat d'apprentissage », « stage de 6 mois », « TJM »…). 22 phrases de test correctes sur 22.
- Étape 4 (mesure sur 7 298 offres) : parmi les offres dont le texte donne le contrat et qu'Adzuna marque `permanent`, 624 sont des CDI et 28 des stages → **~96 % fiable**. `contract` est inutilisable (855 stages, 327 freelances, 67 alternances, 24 CDD). Le texte reste toujours prioritaire.
- Traçabilité : champ `contract_source` (`title`, `description`, `keywords`, `adzuna`, `none`) pour distinguer un contrat ÉCRIT d'un contrat DÉDUIT.
- Résultat : « inconnu » passé de 55 % à **33 %**. Sources : titre 40 %, Adzuna 22 %, description 5 %, aucune 33 %.
- Usage prévu (M4) : boost plutôt que filtre. Contrat écrit > contrat déduit > inconnu ; les offres « inconnu » ne sont pas exclues, seulement classées après.

## D9 — Une base d'offres plutôt que des appels à l'API à chaque recherche
- Décision : collecter les offres à l'avance et les stocker (PostgreSQL + Elasticsearch), au lieu d'interroger Adzuna à chaque demande d'utilisateur.
- Pourquoi :
  - recherche par le SENS : il faut un vecteur (embedding) par offre, calculé à l'avance ; Adzuna ne cherche que par mots (« data engineer » ne trouve pas « Ingénieur Big Data ») ;
  - l'enrichissement (contrat, compétences, région) est fait une fois et stocké ;
  - mode 2 : statistiques sur des milliers d'offres, impossibles avec quelques appels ;
  - quota (500 appels/jour) et temps de réponse (millisecondes au lieu de secondes) ;
  - l'application fonctionne sans clé Adzuna (démo, correction) et même si Adzuna est en panne.
- Principe : le formulaire FILTRE (métier, région, contrat), le CV CLASSE les offres retenues.

## D10 — Jeu de démonstration et conteneur `loader` (prévu, M2)
- Problème : les données vivent dans les volumes Docker de la machine qui les a créées. Chez le correcteur, `docker compose up` crée des bases vides, et il n'a pas de clé Adzuna.
- Décision : versionner un fichier d'offres de démonstration (`seed/`) et ajouter un conteneur `loader` qui, au démarrage, attend les bases (healthchecks), charge les offres (UPSERT, idempotent) puis s'arrête.
- Séparation : `fetch_offers.py` (collecte, chez nous, avec la clé) / `load_offers.py` (chargement, partout, sans clé).
- À vérifier : les conditions d'utilisation d'Adzuna pour la publication d'un échantillon.

## D11 — Sécurité en production (prévu, M8)
- Décision : aucun port de base de données publié sur le serveur. Seul Caddy (80/443, HTTPS) est exposé ; les bases ne sont joignables que par le réseau interne Docker.
- Pourquoi : Elasticsearch (sécurité désactivée) et Redis (sans mot de passe) ouverts sur Internet sont trouvés par des robots en quelques heures.
- Mise en œuvre : ports des bases dans `docker-compose.override.yml` (local uniquement), pare-feu `ufw` (22, 80, 443), secrets dans le `.env` du serveur. Vérification des bases via `docker compose exec`.
- Sauvegarde : `pg_dump` quotidien de PostgreSQL (source de vérité ; Elasticsearch se reconstruit à partir de PostgreSQL).

## D12 — Mise à jour quotidienne et expiration des offres (prévu)
- Décision : chaque matin, relancer les recherches avec `max_days_old=1` et `sort_by=date`, puis charger en UPSERT (aucun doublon).
- Expiration : Adzuna n'indique jamais qu'une offre est pourvue. Règle : plus de 45 jours → `status='expired'` dans PostgreSQL (gardée pour les statistiques) et retirée d'Elasticsearch ; suppression définitive après 6 mois.
- Prérequis : cache daté (`seed/raw/adzuna/<date>/`), sinon la recherche du jour relirait celle de la veille ; journal `ingestion_runs` dans PostgreSQL ; verrou Redis contre les exécutions simultanées.


## D13 — Schéma PostgreSQL de la table `offers` (M2)
- Fichier : `infra/postgres/init/01_schema.sql`, exécuté automatiquement par l'image `postgres` au premier démarrage (volume vide), grâce au montage du dossier dans `/docker-entrypoint-initdb.d/`.
- Identifiants :
  - `id` (`BIGINT GENERATED ALWAYS AS IDENTITY`) : identifiant **interne**, pour les liens entre tables ;
  - `(source, source_id)` **UNIQUE** : identifiant chez la source, stable d'une collecte à l'autre. C'est la clé de l'**UPSERT** (reconnaître une offre déjà connue) ; `source` évite les collisions entre sources.
- Contraintes (la base protège elle-même la qualité des données, même si le code a un bug) :
  - `CHECK` sur `contract_types` (au moins une valeur, uniquement `cdi`, `cdd`, `stage`, `alternance`, `freelance`, `inconnu`), `contract_source`, `status` ;
  - `CHECK` sur les salaires (positifs, min ≤ max ; absents autorisés) ;
  - `NOT NULL` sur les champs indispensables (titre, description, URL, contrat, `raw`).
- `contract_types` en **tableau** (`TEXT[]`) plutôt qu'en table de liaison : 1 ou 2 valeurs par offre, liste fermée, aucune information propre au lien. Les **compétences** (M3) auront au contraire une table `offer_skills` : beaucoup de valeurs, liste ouverte, information sur le lien (obligatoire / souhaitée).
- `raw` en **JSONB** : l'offre brute d'Adzuna est conservée dans la base (retraitement possible sans le cache) ; illustre aussi pourquoi MongoDB serait redondant (D1).
- Index, choisis selon les requêtes réelles (un index ralentit les écritures et prend de la place) :
  - B-tree : `region` (filtre du formulaire), `status` (offres actives), `published_at` (expiration), `ingestion_runs.started_at` ;
  - **GIN** (index inversé) : `contract_types`, pour « le tableau contient `alternance` » (`@>`) ;
  - uniques automatiques : clés primaires et `(source, source_id)`.
  Pas d'index sur le texte : la recherche textuelle est le rôle d'Elasticsearch.
- Cycle de vie : suppression **logique** (`status = 'expired'`) plutôt que `DELETE`, pour garder l'historique des statistiques (D12). Dates `first_seen_at` / `last_seen_at`.
- Table `ingestion_runs` : journal des chargements (début, fin, statut `running` / `success` / `failed`, compteurs, message d'erreur, paramètres).
- Testé sur PostgreSQL 16 : doublon, contrat hors liste, tableau vide et salaire incohérent sont refusés ; l'UPSERT met à jour sans créer de ligne.

## D14 — Chargement des offres dans PostgreSQL (`worker/load_offers.py`)
- Collecte et chargement **séparés** : `fetch_offers.py` (Adzuna → JSON, avec la clé) et `load_offers.py` (JSON → base, sans clé). Le correcteur, le serveur et le futur conteneur `loader` n'ont besoin que du second.
- **UPSERT** (`INSERT ... ON CONFLICT (source, source_id) DO UPDATE`) : le chargement est **idempotent**. 1er lancement : 7 298 insérées ; 2e : 0 insérée, 7 298 mises à jour. On ne touche ni à `id`, ni à `first_seen_at`, ni à `status` ; `last_seen_at = now()`.
- **Transaction** « tout ou rien » pour les offres : une seule offre invalide annule tout (ROLLBACK), la base n'est jamais à moitié remplie.
- **Journal hors transaction** (`autocommit=True`) : la ligne `ingestion_runs` est créée avant le chargement et complétée après (`success` + compteurs, ou `failed` + message), même en cas d'échec.
- Compteurs insérées / mises à jour : comptage des lignes **avant et après** dans la même transaction (fiable car un seul chargement tourne à la fois).
- Robustesse : `BaseException` attrapée (un `Ctrl+C` marque le journal `failed` au lieu de le laisser `running`) ; la mise à jour du journal a son propre `try`, pour que l'erreur d'origine soit toujours celle affichée (connexion coupée). Limite connue : si la connexion est perdue, le journal reste `running` (il faudrait une nouvelle connexion).
- **Requêtes paramétrées** (`%(nom)s`) uniquement : jamais de valeurs collées dans le texte SQL (apostrophes, injection SQL).
- Connexion paramétrée par l'environnement (`POSTGRES_HOST`, `POSTGRES_PORT`…) : le même code fonctionne sur le PC (`localhost`) et dans un conteneur (`postgres`).
- Testé : chargement, relance (idempotence), fichier invalide (rollback + journal `failed`), `Ctrl+C` et connexion coupée pendant un chargement de 23 520 offres.

## D15 — Nettoyage de la localisation dans l'adaptateur Adzuna
- Principe : **chaque adaptateur nettoie les bizarreries de SA source** (`worker/sources/adzuna.py`) et produit un `JobOffer` propre. Le chargement (`load_offers.py`) ne fait qu'enregistrer (responsabilité unique).
- Localisation découpée à partir de `location.area` (liste du plus large au plus précis : pays, région, département, ville), plutôt que du libellé `display_name` au format variable.
- **Régions harmonisées** par une **clé simplifiée** (sans accents, minuscules, lettres seulement) comparée aux 18 noms officiels : reconnaît toute variante de ce type, même nouvelle. Variantes trouvées dans nos données : « Ile-de-France », « Hauts-De-France », « Grand-Est », « Pays-de-la-Loire », « Paysde-la-Loire », « Centre-Val-De-Loire ». Alias manuels : « Centre » (ancien nom) et « DOM-TOM » sans territoire.
- **Outre-mer** : Adzuna insère un niveau « DOM-TOM » ; le territoire (« La Réunion »…) devient la région et le département.
- **Paris** : département et ville ; les arrondissements sont ramenés à « Paris ».
- Ville = dernier élément à partir de 4 niveaux ; une offre localisée au département seulement n'a pas de ville.
- Résultat sur 7 298 offres : 13 régions de métropole + 5 d'outre-mer + Nouvelle-Calédonie, chacune écrite d'une seule façon ; 602 offres sans région (nationales / télétravail), gardées et classées après les offres localisées (boost, pas filtre).

## D16 — PostgreSQL publié sur le port 5433 du PC
- Problème : `load_offers.py` recevait « authentification par mot de passe échouée » (message en français, alors que l'image Docker répond en anglais).
- Diagnostic : `netstat -ano | findstr :5432` montrait deux programmes à l'écoute ; `Get-Process` les a identifiés : un **PostgreSQL installé sur Windows** et Docker. Les connexions vers `localhost:5432` arrivaient au PostgreSQL de Windows.
- Décision : publier le PostgreSQL Docker sur le port **5433** du PC (`"5433:5432"`) et définir `POSTGRES_PORT=5433` dans `.env`. Le PostgreSQL de Windows, utilisé par un autre programme, n'est pas touché.
- Sans effet entre conteneurs : dans le réseau Docker, PostgreSQL reste joignable sur `postgres:5432`.

## D17 — Mapping et indexation Elasticsearch (`infra/elasticsearch/`, `worker/index_offers.py`)
- Mapping écrit à la main (`offers_mapping.json`, expliqué champ par champ dans `infra/elasticsearch/README.md`) plutôt que deviné : le mapping dynamique créait des copies `text` + `keyword` de chaque champ et utilisait l'analyseur standard (« développeuse » ne trouvait pas « développeur »).
- Types selon l'usage :
  - `text` + analyseur `french` : `title`, `description` (recherche par pertinence, poids différents au M4) ;
  - `keyword` : région, département, ville, contrats, source… (filtres, comptages) ;
  - `company` : `text` + sous-champ `keyword` (chercher ET compter) ;
  - `float`, `date`, `geo_point` (latitude + longitude réunies) ;
  - `url` et `location_label` : `index: false`, `doc_values: false` (affichage seul, depuis `_source`).
- `dynamic: strict` : un champ non déclaré fait refuser le document (équivalent des contraintes PostgreSQL).
- `number_of_shards: 1`, `number_of_replicas: 0` : un seul serveur ; sans réplique, l'état est vert.
- Non indexés : `raw`, `contract_raw`, `first_seen_at`, `last_seen_at`, `status` (seules les offres actives sont indexées).
- Indexation : `index_offers.py` lit les offres **actives dans PostgreSQL** (source de vérité, jamais le fichier JSON), **supprime puis recrée** l'index, et envoie les documents par paquets de 500 (API `_bulk`).
  - `_id` du document = `id` PostgreSQL : les deux bases sont reliées, réindexer remplace le document ;
  - reconstruction complète : l'index reflète exactement PostgreSQL et suit les évolutions du mapping ; inconvénient accepté : quelques secondes d'index incomplet (des alias l'éviteraient en production) ;
  - `refresh` puis `_count` pour vérifier : 7 298 / 7 298 documents.
- Connexion par `ES_URL` (par défaut `http://localhost:9200` ; `http://elasticsearch:9200` dans un conteneur).
- Prévu : ajout du champ vecteur `dense_vector` pour la recherche par le sens (ajouter un champ est permis ; changer un type impose de réindexer).

## D18 — Pas de comptes utilisateurs en V1 (M3)
- Décision : le candidat est identifié par son **email** (unique, en minuscules) ; même email = même personne, fiche mise à jour par UPSERT.
- Pourquoi : délai du rendu (13/11) ; l'essentiel du projet est la persistance multi-bases et la recherche.
- Limite connue : toute personne connaissant un identifiant de demande peut la lire.
- Prévu après le rendu : vrais comptes (mots de passe hachés, JWT).

## D19 — Modèle d'embeddings : `intfloat/multilingual-e5-small` (M4)
- Décision : un modèle Hugging Face exécuté avec sentence-transformers, sur CPU, dans le worker (offres) ET dans l'API (CV).
- Pourquoi : multilingue (offres en français, parfois en anglais), entraîné pour la recherche, petit (384 dimensions, ~470 Mo), rapide sans carte graphique.
- Règles : préfixes `passage:` (offres) et `query:` (CV, recherche) ; vecteurs normalisés (cosinus) ; **même modèle des deux côtés** (`embeddings.py` en deux copies identiques), sinon les vecteurs ne sont pas comparables.
- Limite : le modèle ne lit que 512 tokens (~350-400 mots) → le titre (offres) et le métier (CV) sont placés EN TÊTE du texte.
- Image de l'API : torch « CPU seulement » (index PyTorch CPU, ~200 Mo au lieu de plusieurs Go) ; volume `hf_cache` pour ne télécharger le modèle qu'une fois.
- Prévu (M6) : fine-tuning sur des paires CV ↔ offre.

## D20 — Recherche hybride avec fusion RRF calculée en Python (M4, `api/app/search.py`)
- Décision : deux recherches (par mots BM25 sur le métier, par sens kNN sur « métier. CV »), fusionnées par **Reciprocal Rank Fusion** : score = somme de 1 / (60 + rang).
- Pourquoi RRF : les scores BM25 (ex. 12,7) et cosinus (ex. 0,86) ne sont pas sur la même échelle ; RRF fusionne des **rangs**. Une offre bien classée par les deux méthodes passe devant.
- Pourquoi en Python : chaque résultat garde ses rangs (`rank_bm25`, `rank_knn`, `rank_exact`) pour comprendre le classement, et les bonus s'ajoutent après la fusion (D21).
- BM25 : `title^3` + `description`, bonus `match_phrase` dans le titre ; seulement si le métier est rempli. Au M5, il utilisera les compétences extraites du CV.
- 100 candidats par recherche (`num_candidates` 300) avant fusion, 20 résultats.

## D21 — Filtres souples et bonus APRÈS la fusion, plutôt qu'un filtrage strict (M4)
- Décision : on élimine une offre seulement si elle **contredit** un critère (autre région, autre contrat, salaire trop bas) ; une information **manquante** (région absente, contrat « inconnu », salaire absent) ne l'élimine pas. Les offres qui respectent **explicitement** les critères reçoivent un bonus sur le score final : région +0,02, contrat +0,02.
- Pourquoi :
  - un filtrage strict donnait souvent 0 résultat (ex. aucune alternance data en Bretagne) et perdait les 33 % d'offres au contrat inconnu ;
  - avec les bonus, les offres sûres passent quand même en tête (0,02 > 1/61, une 1re place).
- Pourquoi après la fusion : dans BM25, le bonus était dilué (le kNN n'en avait pas, RRF ne garde que les rangs) ; constaté sur l'offre 180 : 1re en BM25, 13e au final.
- Bonus contrat unique, quelle que soit `contract_source` : la source la plus fiable a déjà été choisie au chargement (D8).
- Alternative écartée : seuil de pertinence pour le bonus (rang ≤ 50) : aurait retiré le bonus aux meilleures alternances (« Data Engineer Junior - Alternance » : 57e en BM25).
- Prévu (M7) : champ `match` pour afficher « correspond à vos critères » / « à vérifier ».

## D22 — Troisième recherche « par sens parmi les offres exactes » (M4)
- Constat : Île-de-France + alternance : 20 alternances « data » dans l'index, 6 dans les résultats ; les 14 autres n'étaient dans aucune des deux listes de 100 candidats (les annonces d'alternance, centrées sur l'école et le rythme, ressemblent moins à « data engineer » que les postes Senior).
- Décision : si une région ou un contrat est choisi, une recherche kNN de plus, avec des filtres **stricts** (région exacte, contrat exact) ; ajoutée à la fusion RRF (`rank_exact`).
- Résultat : 19 alternances sur 20, l'offre idéale (« Data Engineer - en alternance ») 1re.
- Le vecteur du CV est calculé une seule fois pour les deux recherches kNN.

## D23 — Régions en liste fermée (M4)
- Constat : `"ile de france"` ne trouvait rien (le filtre `term` compare caractère par caractère, l'index contient `Île-de-France`) ; seules les offres sans région restaient, sans erreur.
- Décision : `Region = Literal[...]` dans `schemas.py`, les 19 valeurs de l'index (vérifiées par agrégation) ; valeur inconnue → 422. Route `GET /api/regions` pour la liste déroulante du formulaire : la liste n'est écrite qu'à un endroit.
- Lien avec D15 : `normalize_region` harmonise les variantes au téléchargement ; une région VRAIMENT nouvelle devra être ajoutée à `OFFICIAL_REGIONS` (worker) et à `Region` (API).

## D24 — CV obligatoire, métier facultatif (M4)
- Décision : `cv_text` obligatoire (50 à 20 000 caractères) ; `job_title` facultatif.
- Pourquoi : les quatre modes partent du CV ; la recherche par sens fonctionne toujours avec le CV seul ; le métier, s'il est donné, active la recherche par mots et passe en tête du texte du kNN.
