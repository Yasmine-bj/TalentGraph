# Mapping Elasticsearch de l'index `offers`

Ce dossier contient le **schéma** de l'index `offers` d'Elasticsearch :
`offers_mapping.json` est à Elasticsearch ce que `infra/postgres/init/01_schema.sql`
est à PostgreSQL.

> Le format JSON **n'accepte pas les commentaires** (Elasticsearch refuserait le
> fichier). Les explications sont donc dans ce README, champ par champ.

## Rôle de l'index

- **PostgreSQL** est la **source de vérité** (table `offers`).
- **Elasticsearch** est un **index de recherche** reconstruit à partir de PostgreSQL
  par `worker/index_offers.py` : recherche par pertinence, filtres, comptages
  (agrégations), et plus tard recherche par le sens (vecteurs).
- Il ne contient donc **que ce qui sert à chercher, filtrer, compter ou afficher**.
- Seules les offres **actives** sont indexées ; une offre expirée est retirée
  (voir `docs/decisions.md`, D12).
- Identifiant de chaque document (`_id`) = **`id` de la table PostgreSQL**
  (`/offers/_doc/42` = ligne 42). Les deux bases sont reliées, et réindexer une
  offre **remplace** son document (pas de doublon, équivalent de l'UPSERT).

## Partie `settings` : réglages de l'index

| Réglage | Valeur | Pourquoi |
|---|---|---|
| `number_of_shards` | `1` | Un *shard* est un morceau de l'index, réparti sur plusieurs serveurs pour les gros volumes. Un seul serveur et ~7 300 offres : un morceau suffit. |
| `number_of_replicas` | `0` | Une *réplique* est une copie de secours placée sur **un autre** serveur. Avec un seul serveur, elle ne peut aller nulle part et l'état resterait **jaune**. À 0, il est **vert**. La sécurité des données repose sur PostgreSQL. |

## Partie `mappings` : le schéma

### `"dynamic": "strict"`

Un document contenant un champ **non déclaré** ici est **refusé** (au lieu d'un
champ deviné automatiquement). Une faute de frappe dans le code (`titel`) devient
une erreur claire. Équivalent des contraintes PostgreSQL.

### Les types utilisés

| Type | Comportement | Usage |
|---|---|---|
| `text` | découpé en mots par un **analyseur**, cherchable par **pertinence** (score BM25) | titre, description |
| `keyword` | gardé **tel quel**, en un bloc : égalité exacte, filtres, tris, comptages | région, contrat, identifiants |
| `float` | nombre à virgule : intervalles (`>=`), tris, moyennes | salaires |
| `date` | date ISO 8601 : tris, filtres par période | date de publication |
| `geo_point` | un point sur la carte (latitude + longitude) : distance, « à moins de 30 km » | localisation GPS |

**Tableaux** : il n'existe pas de type « tableau ». **Tout champ peut contenir
plusieurs valeurs** (`"contract_types": ["alternance", "stage"]` est un `keyword`
à deux valeurs). L'index inversé indexe chaque valeur : pas besoin d'index GIN.

### Les options `index` et `doc_values`

| Option | Sert à | Si `false` |
|---|---|---|
| `index` | **chercher** et filtrer sur le champ | impossible de chercher dedans |
| `doc_values` | **trier** et **compter** (agrégations) | impossible de trier ou compter dessus |

Le document complet reste toujours disponible pour l'**affichage**, dans le
`_source` (copie du JSON envoyé). Désactiver ce qui ne sert pas économise de la
place et du temps d'indexation.

## Les champs

### Identification

| Champ | Type | Contenu | Rôle |
|---|---|---|---|
| `source` | `keyword` | `"adzuna"` | source de l'offre ; filtres et statistiques |
| `source_id` | `keyword` | `"5937384042"` | identifiant chez la source ; débogage |

### Texte cherchable

| Champ | Type | Rôle |
|---|---|---|
| `title` | `text`, analyseur `french` | recherche par pertinence ; le champ le plus important |
| `description` | `text`, analyseur `french` | recherche par pertinence ; extrait de ~500 caractères |

- **Analyseur `french`** (intégré à Elasticsearch) : minuscules, suppression des
  mots vides français (« le », « de », « et »…), élisions (« l'équipe » → « équipe »),
  racinisation (pluriels et variations ramenés à une racine commune).
  Il s'applique **aussi au texte tapé par l'utilisateur** : les deux côtés sont
  transformés de la même façon.
- **Deux champs séparés** plutôt qu'un seul texte : pour donner plus de **poids**
  au titre qu'à la description au moment de la recherche (M4).

### Entreprise

| Champ | Type | Contenu | Rôle |
|---|---|---|---|
| `company` | `text` (analyseur standard) | `dassault` · `systemes` | trouver l'offre en tapant « Dassault » |
| `company.keyword` | sous-champ `keyword` | `DASSAULT SYSTEMES` | **compter** les offres par entreprise (top recruteurs) |

- `fields` déclare un **sous-champ** : une deuxième version du même texte.
- Analyseur **standard** (pas `french`) : un nom d'entreprise n'est pas du
  français à raciniser.
- `ignore_above: 256` : un nom de plus de 256 caractères n'est pas copié dans la
  version `keyword` (sécurité).

### Localisation

| Champ | Type | Contenu (exemple) | Rôle |
|---|---|---|---|
| `region` | `keyword` | `"Île-de-France"` | **filtre** région du formulaire, comptages |
| `department` | `keyword` | `"Yvelines"` | filtre plus fin |
| `city` | `keyword` | `"Vélizy-Villacoublay"` | filtre et affichage ; vide si l'offre n'est localisée qu'au département |
| `location` | `geo_point` | `{ "lat": 48.78, "lon": 2.19 }` | recherche par **distance** (bonus) ; absent si pas de coordonnées |
| `location_label` | `keyword`, `index: false`, `doc_values: false` | `"Vélizy-Villacoublay, Versailles"` | **affichage uniquement** |

- `region`, `department` et `city` sont **normalisés** par `worker/sources/adzuna.py`
  (noms officiels, outre-mer, Paris) : ce sont eux qui servent aux **filtres**.
- `location_label` est le **libellé d'affichage** d'Adzuna (`location.display_name`),
  stocké dans PostgreSQL sous ce nom. Il est **montré** à l'utilisateur sous le titre
  de l'offre, mais on ne cherche, ne trie et ne compte jamais dessus : d'où
  `index: false` et `doc_values: false`. Il reste disponible dans le `_source`.
- `location` réunit les colonnes PostgreSQL `latitude` et `longitude` en un seul
  point.

### Contrat

| Champ | Type | Contenu | Rôle |
|---|---|---|---|
| `contract_types` | `keyword` (plusieurs valeurs) | `["alternance", "stage"]` | **filtre** (retirer les contrats incompatibles) et **boost** |
| `contract_source` | `keyword` | `"title"`, `"description"`, `"adzuna"`, `"none"`… | **boost** selon la fiabilité : contrat écrit > déduit > inconnu |
| `contract_time` | `keyword` | `"full_time"`, `"part_time"` | filtre temps plein / partiel (bonus) |

Voir `docs/decisions.md`, D8 (détection du contrat et principe du boost).

### Classement

| Champ | Type | Contenu | Rôle |
|---|---|---|---|
| `category` | `keyword` | `"Emplois Informatique"` | information (catégorie Adzuna, peu fiable) |
| `search_keywords` | `keyword` | `"data engineer"`, `"data [alternance]"` | **famille de métier** pour les statistiques du mode 2 |

### Salaire et date

| Champ | Type | Rôle |
|---|---|---|
| `salary_min`, `salary_max` | `float` | filtre « salaire minimum », moyennes ; absents si non indiqués (~63 % des offres) |
| `published_at` | `date` | tri par date, filtre « offres récentes » |

Pourquoi `float` et pas un nombre exact comme le `NUMERIC` de PostgreSQL : ici on
filtre et on calcule des moyennes, pas de comptabilité. Le salaire exact reste
dans PostgreSQL.

### Lien vers l'annonce

| Champ | Type | Rôle |
|---|---|---|
| `url` | `keyword`, `index: false`, `doc_values: false` | **affichage uniquement** (bouton « Voir l'offre ») |

## Colonnes PostgreSQL volontairement absentes

| Colonne | Raison |
|---|---|
| `id` | devient l'identifiant du document (`_id`) |
| `raw` | JSON brut d'Adzuna : inutile pour la recherche, reste dans PostgreSQL |
| `contract_raw` | traçabilité, propre à PostgreSQL |
| `first_seen_at`, `last_seen_at` | historique de collecte, propre à PostgreSQL |
| `status` | seules les offres actives sont indexées |
| `latitude`, `longitude` | réunies dans `location` |

## Évolutions prévues

Le champ **vecteur** de la recherche par le sens (étape 6) sera **ajouté** :

```json
"embedding": { "type": "dense_vector", "dims": 384, "similarity": "cosine" }
```

(`dims` dépendra du modèle choisi.) **Ajouter** un champ à un mapping est
autorisé ; **changer le type** d'un champ existant ne l'est pas : il faut alors
recréer l'index et tout réindexer (quelques secondes, à partir de PostgreSQL).

## Tester le mapping à la main

Dans Postman (Body raw, JSON) :

1. `PUT http://localhost:9200/offers_test` avec tout le contenu de `offers_mapping.json`
   → réponse `{"acknowledged": true, ...}`
2. `GET http://localhost:9200/offers_test/_mapping` pour le relire
3. `DELETE http://localhost:9200/offers_test` pour nettoyer
