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