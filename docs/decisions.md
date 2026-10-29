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
