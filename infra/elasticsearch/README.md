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
  (agrégations), et recherche par le sens (vecteurs, champ `embedding`).
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

## Recherche par le sens : le champ `embedding` (M4)

| Champ | Type | Contenu | Rôle |
|---|---|---|---|
| `embedding` | `dense_vector` | 384 nombres : le **sens** du titre + de la description | recherche **kNN** (offres les plus proches du CV, par le sens) |

```json
"embedding": { "type": "dense_vector", "dims": 384, "index": true, "similarity": "cosine" }
```

| Réglage | Signification |
|---|---|
| `type: dense_vector` | un vecteur de nombres à virgule, de taille fixe (« dense » : toutes les cases sont remplies) |
| `dims: 384` | la taille du vecteur ; **doit être égale** à `EMBEDDING_DIMS` de `embeddings.py` (sinon le document est refusé) |
| `index: true` | construire l'index **HNSW**, pour une recherche kNN rapide |
| `similarity: cosine` | comparer deux vecteurs par le **cosinus** de leur angle (1 = même direction = même sens) |

- **Texte vectorisé** : `"passage: " + titre + ". " + description`, par le modèle
  `intfloat/multilingual-e5-small` (`worker/embeddings.py`, appelé par `worker/index_offers.py`).
  Le CV ou la recherche de l'utilisateur est vectorisé par le **même** modèle,
  avec le préfixe `"query: "` (`api/app/embeddings.py`).
- **Même modèle et mêmes `dims` des deux côtés** : deux modèles différents produisent
  des vecteurs dans des « espaces » différents, incomparables. Changer de modèle
  impose de réindexer toutes les offres.
- **HNSW** (*Hierarchical Navigable Small World*) : un graphe où chaque vecteur est
  relié à ses voisins proches. La recherche part d'un point et « saute » de voisin
  en voisin vers la zone la plus proche du vecteur cherché, sans comparer les
  ~7 300 vecteurs un par un. Résultat **approximatif** (on peut rater un voisin de
  temps en temps) mais très rapide.
- **kNN** (*k-Nearest Neighbors*) : trouver les *k* vecteurs les plus proches.
  Paramètres d'une requête : `k` (combien de résultats) et `num_candidates`
  (combien de candidats examiner : plus il est grand, plus le résultat est
  précis et plus c'est lent).
- Les scores cosinus de ce modèle sont « tassés » (souvent entre 0,7 et 0,9) :
  seul l'**ordre** compte, d'où la fusion par rangs (RRF) dans la recherche hybride.
- Taille : 384 nombres × 4 octets ≈ 1,5 Ko par offre, ~11 Mo pour 7 300 offres
  (plus l'index HNSW).

## L'index HNSW en détail

Avec `"index": true`, Elasticsearch construit **par défaut** un index **HNSW**
pour chaque champ `dense_vector` : on n'a pas besoin de le demander
explicitement. Les réglages réellement appliqués (dont une éventuelle
**quantification**, voir plus bas) sont visibles avec
`GET /offers/_mapping` (clé `index_options`).

### Le principe : un graphe de voisins, à plusieurs étages

HNSW = *Hierarchical Navigable Small World* (« petit monde navigable hiérarchique »).

- **Graphe** : chaque vecteur (chaque offre) est un **point**, relié par des
  « routes » à quelques-uns de ses **voisins les plus proches** (paramètre `m`,
  16 par défaut).
- **Étages** : tous les points sont dans l'étage du bas (étage 0) ; une petite
  partie, tirée au hasard, monte aussi à l'étage 1 ; une partie encore plus
  petite à l'étage 2, etc. Les étages du haut ont **peu de points, reliés de
  loin en loin** (des « autoroutes ») ; l'étage du bas a **tous les points,
  reliés de proche en proche** (des « rues »).

```
étage 2 :   A ─────────────────────── F                     (quelques points, grands sauts)
étage 1 :   A ───── C ────── E ────── F ───── H             (plus de points)
étage 0 :   A ─ B ─ C ─ D ─ E ─ F ─ G ─ H ─ I ─ J ...       (tous les points, petits pas)
```

### La recherche : descendre les étages

Pour trouver les offres les plus proches du vecteur du CV :

1. on part d'un **point d'entrée** à l'étage le plus haut ;
2. on regarde ses voisins : on se déplace vers celui qui est **plus proche** du
   CV, et on recommence tant qu'on se rapproche (grands sauts) ;
3. quand on ne se rapproche plus, on **descend d'un étage** et on recommence
   (sauts plus petits) ;
4. à l'étage 0, on explore plus largement autour de la meilleure zone : on garde
   une liste de `num_candidates` candidats, et on renvoie les `k` meilleurs.

Comme pour trouver une adresse : l'avion jusqu'à la bonne région, l'autoroute
jusqu'à la bonne ville, puis les rues jusqu'à la bonne maison, au lieu de
visiter toutes les maisons du pays.

### La construction : à chaque document indexé

Quand `index_offers.py` envoie une offre, Elasticsearch l'**insère** dans le
graphe : il tire au hasard son étage le plus haut, cherche ses voisins les plus
proches à chaque étage (en explorant `ef_construction` candidats, 100 par
défaut), puis crée les « routes ». C'est pourquoi l'indexation avec vecteurs est
un peu plus lente que sans.

### Le compromis : approximatif mais rapide

| | Comparer tous les vecteurs (force brute) | HNSW |
|---|---|---|
| Résultat | **exact** | **approximatif** (peut rater un voisin de temps en temps) |
| Vitesse | proportionnelle au nombre d'offres | quasi constante, même avec des millions de vecteurs |

Réglages qui jouent sur ce compromis :

| Réglage | Où | Plus grand = |
|---|---|---|
| `m` | mapping (`index_options`) | plus de routes par point : plus précis, plus de mémoire |
| `ef_construction` | mapping (`index_options`) | graphe de meilleure qualité, indexation plus lente |
| `num_candidates` | chaque requête kNN | recherche plus précise, plus lente |

On garde les valeurs par défaut, adaptées à notre volume (~7 300 offres).

### La quantification (selon la version)

Pour économiser la mémoire, les versions récentes d'Elasticsearch peuvent
**compresser** les vecteurs dans l'index HNSW (par exemple chaque nombre sur
1 octet au lieu de 4 : `int8_hnsw`, ou encore plus compact : `bbq_hnsw`). Le
graphe sert alors à trouver vite les candidats, puis les vecteurs complets
(conservés à part) peuvent servir à affiner le classement. Le type appliqué à
notre index est visible dans `index_options` (voir plus haut).

## Comment `worker/index_offers.py` remplit l'index

```
1. connect_es()        Elasticsearch joint (GET /, échoue tout de suite s'il ne répond pas)
2. read_offers()       offres ACTIVES lues dans PostgreSQL (sans la colonne raw)
3. embed_passages()    pour chaque lot de 64 offres (~115 lots pour 7 300 offres) :
                         a. ajouter "passage: " devant chaque texte (titre + description)
                         b. découper en tokens, puis en numéros (le tokenizer)
                         c. PyTorch : passer les numéros dans les 12 couches du modèle,
                            avec ses ~118 millions de poids
                         d. faire la moyenne des vecteurs des tokens -> 1 vecteur par offre
                         e. normaliser (longueur 1)
                       -> un vecteur de 384 nombres par offre, gardé en mémoire
                       (étape la plus longue : quelques minutes sur CPU ; faite AVANT
                        de supprimer l'ancien index, pour qu'un échec le laisse intact)
4. recreate_index()    supprimer "offers", puis le recréer avec offers_mapping.json
5. helpers.bulk()      envoyer les documents (champs + vecteur) par paquets de 500
                       -> Elasticsearch insère chaque vecteur dans le graphe HNSW
6. refresh + count     rendre les documents cherchables, puis vérifier :
                       documents dans l'index = offres lues dans PostgreSQL
```

## Évolutions

- ✅ **Fait (M4)** : champ `embedding` ajouté (recherche par le sens).
  Ajouter un champ à un mapping est permis ; **changer le type** d'un champ
  existant ne l'est pas : il faut recréer l'index et tout réindexer (ce que fait
  `index_offers.py` à chaque lancement, à partir de PostgreSQL).
- Prévu (M6) : réindexer avec le modèle **fine-tuné** (variable d'environnement
  `EMBEDDING_MODEL`), et mesurer le gain.

## Tester le mapping à la main

Dans Postman (Body raw, JSON) :

1. `PUT http://localhost:9200/offers_test` avec tout le contenu de `offers_mapping.json`
   → réponse `{"acknowledged": true, ...}`
2. `GET http://localhost:9200/offers_test/_mapping` pour le relire
3. `DELETE http://localhost:9200/offers_test` pour nettoyer
