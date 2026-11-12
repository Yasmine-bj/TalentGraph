"""
search.py — La recherche HYBRIDE d'offres dans Elasticsearch (module M4).

RÔLE :
    À partir des critères du formulaire (CV, métier, région, contrats, salaire),
    trouver les offres les plus pertinentes de l'index "offers".

DEUX (OU TROIS) RECHERCHES, PUIS UNE FUSION :
    1. Recherche par MOTS (BM25) : le métier saisi ("data engineer") est cherché
       dans le titre (poids x3) et la description des offres.
       -> précise sur les mots exacts, mais ne comprend pas les synonymes.
       Faite SEULEMENT si le métier est rempli (il est facultatif).
       (Au M5, elle utilisera aussi les compétences extraites du CV par l'agent.)

    2. Recherche par SENS (kNN) : le texte "métier. CV" est transformé en
       vecteur (embed_query), et Elasticsearch cherche les offres dont le
       vecteur est le plus PROCHE (index HNSW du champ "embedding").
       -> comprend le sens ("analyste de données" ~ "data analyst"), mais
       moins précise sur un mot-clé exact.

    2 bis. Recherche par SENS parmi les offres EXACTES (ajout M4, après tests) :
       la même recherche kNN, mais avec des filtres STRICTS (région exacte,
       contrat exact, sans les "inconnu"). Faite seulement si une région ou
       un contrat est choisi. Voir build_strict_filters.

    3. FUSION RRF (Reciprocal Rank Fusion), calculée ici en Python :
           score(offre) = somme, sur chaque recherche où elle apparaît,
                          de 1 / (RRF_K + rang)
       On fusionne des RANGS (1er, 2e...) et pas des scores : les scores BM25
       (ex. 12,7) et kNN (ex. 0,86) ne sont pas sur la même échelle.
       Une offre bien classée dans les DEUX recherches passe devant.

FILTRES ET BONUS (les critères du formulaire) :
    - FILTRE = condition éliminatoire : l'offre est retirée des résultats.
      Appliqué aux recherches 1 et 2, pour qu'elles cherchent dans le même
      ensemble (la recherche 2 bis a ses propres filtres, stricts).
    - BONUS  = points ajoutés au score : l'offre reste, mais remonte.

    Principe : on n'élimine PAS une offre parce qu'une information lui MANQUE
    (région inconnue, contrat "inconnu", salaire non indiqué) : on l'élimine
    seulement si elle CONTREDIT le critère. Les offres qui correspondent
    EXPLICITEMENT passent devant grâce aux bonus. Résultat, trois groupes :
        1. région ET contrat respectés explicitement   (+0,04)
        2. l'un des deux                               (+0,02)
        3. informations inconnues                      (+0)
    et, dans chaque groupe, la pertinence (RRF) départage.

AJUSTEMENTS APRÈS LES PREMIERS TESTS (M4, 11 novembre) :
    Test : CV data, "data engineer", alternance, Bretagne puis Île-de-France.
    Constat : presque uniquement des offres sans région / contrat inconnu en
    tête ; les 3 vraies alternances aux places 15 à 20.
    1. Bonus région / contrat déplacés APRÈS la fusion RRF (apply_bonuses).
       Avant, ils étaient dans BM25 seulement : la fusion ne garde que les
       RANGS, et le kNN n'avait pas de bonus -> effet presque perdu
       (offre 180 : 1re en BM25 grâce au bonus, 36e en kNN, 13e au final).
    2. 100 candidats par recherche au lieu de 50 (num_candidates 300 au lieu
       de 200) : les offres exactes sont rares (78 alternances "data" sur
       2 203 offres "data engineer"), il faut qu'elles entrent dans la liste
       pour recevoir leur bonus.
    3. Bonus "expression exacte" du métier dans le titre (BM25) : "Data
       Engineer" passe devant "Data Scientist - AI engineer".
    4. Bonus contrat simplifié : un seul bonus si le contrat correspond,
       quelle que soit sa source (contract_source). La source la plus fiable
       a déjà été choisie au chargement (titre > description > mots-clés >
       Adzuna) : pas besoin de refaire ce tri ici.
    5. 3e recherche "par sens parmi les offres exactes" (2 bis ci-dessus).
       Constat (Île-de-France + alternance) : 20 alternances "data" dans
       l'index, 6 seulement dans les résultats. Les 14 autres n'étaient dans
       AUCUNE des deux listes de 100 candidats : la pertinence classe mal les
       alternances (leurs annonces parlent de l'école, du rythme...) face aux
       postes "Senior" ou "Lead". Elles ne recevaient donc jamais leur bonus.
       La 3e recherche garantit que les offres exactes entrent dans la liste.
"""

from elasticsearch import Elasticsearch

from app.embeddings import embed_query

# Nom de l'index (le même que dans worker/index_offers.py).
INDEX_NAME = "offers"

# Constante k du RRF : 60 est la valeur de l'article d'origine (Cormack et al.,
# 2009) et celle d'Elasticsearch. Plus elle est grande, plus l'écart entre le
# 1er et le 10e rang est faible.
RRF_K = 60

# Nombre de candidats récupérés PAR recherche avant la fusion, et nombre
# d'offres renvoyées APRÈS la fusion.
# M4 (après tests) : 50 -> 100, pour que les offres exactes, rares, entrent
# dans la liste et puissent recevoir leur bonus.
CANDIDATES_PER_SEARCH = 100
RESULT_SIZE = 20

# kNN : nombre de voisins examinés dans le graphe HNSW avant de garder les
# CANDIDATES_PER_SEARCH meilleurs. Plus grand = plus précis mais plus lent.
# M4 (après tests) : 200 -> 300 (doit rester >= CANDIDATES_PER_SEARCH).
KNN_NUM_CANDIDATES = 300

# BONUS APRÈS LA FUSION (M4, après tests), ajoutés au score RRF final.
# Échelle : une 1re place dans UNE recherche vaut 1/61 = 0,016 en RRF.
# 0,02 est un peu plus : une offre qui respecte EXPLICITEMENT un critère passe
# devant presque toutes celles où l'information MANQUE.
# Ce sont des RÉGLAGES : à ajuster selon les tests.
BONUS_REGION = 0.02     # région de l'offre = région choisie
BONUS_CONTRACT = 0.02   # l'un des contrats de l'offre = l'un des contrats cochés

# BONUS DANS BM25 (M4, après tests) : le métier écrit tel quel dans le titre
# ("data engineer", mots côte à côte et dans cet ordre). Multiplie le score
# de cette clause par 2 : les vrais "Data Engineer" passent devant les
# "Data Scientist - AI engineer" (qui ont les deux mots, mais séparés).
TITLE_PHRASE_BOOST = 2.0

# Champs renvoyés pour chaque offre (on ne renvoie surtout pas "embedding" :
# 384 nombres inutiles pour l'affichage, ni la description complète).
RESULT_FIELDS = [
    "title", "company", "city", "region", "contract_types",
    "salary_min", "salary_max", "published_at", "url",
]


# ---------------------------------------------------------------------------
# 1. LES FILTRES (souples pour les recherches 1 et 2, stricts pour la 2 bis)
# ---------------------------------------------------------------------------

def build_filters(region: str | None, contract_types: list[str], salary_min: float | None) -> list[dict]:
    """Traduit les critères du formulaire en filtres Elasticsearch.

    Renvoie une LISTE de clauses : une offre doit les respecter TOUTES.
    Liste vide = aucun filtre (toute la France, tous contrats, tout salaire).

    Vocabulaire Elasticsearch utilisé :
      term   : le champ keyword vaut EXACTEMENT cette valeur ;
      terms  : le champ vaut l'UNE de ces valeurs ;
      range  : le nombre est dans un intervalle (gte = >=) ;
      exists : le champ est présent dans le document ;
      bool   : combine des clauses :
                 should   = au moins UNE doit être vraie (un "OU"),
                 must_not = aucune ne doit être vraie (un "NON").
    """
    filters = []

    # RÉGION : l'offre est dans la région demandée, OU sa région est inconnue
    # (offre nationale / télétravail / lieu non précisé). Une offre d'une
    # AUTRE région est éliminée.
    if region:
        filters.append({
            "bool": {
                "should": [
                    {"term": {"region": region}},
                    {"bool": {"must_not": {"exists": {"field": "region"}}}},
                ],
                # Au moins une des deux conditions doit être vraie.
                "minimum_should_match": 1,
            }
        })

    # CONTRATS : l'offre a l'un des contrats cochés, OU un contrat "inconnu"
    # (Adzuna ne l'indique pas toujours). contract_types est une liste dans
    # l'offre : "terms" est vrai si UNE valeur de l'offre est dans la liste.
    if contract_types:
        filters.append({"terms": {"contract_types": [*contract_types, "inconnu"]}})

    # SALAIRE : le salaire MAX de l'offre atteint le minimum demandé, OU le
    # salaire n'est pas indiqué (la majorité des offres).
    # On compare au MAX : une offre "35 000 - 45 000 €" convient à quelqu'un
    # qui demande au moins 40 000 €.
    if salary_min is not None:
        filters.append({
            "bool": {
                "should": [
                    {"range": {"salary_max": {"gte": salary_min}}},
                    {"bool": {"must_not": {"exists": {"field": "salary_max"}}}},
                ],
                "minimum_should_match": 1,
            }
        })

    return filters


def build_strict_filters(region: str | None, contract_types: list[str], salary_min: float | None) -> list[dict]:
    """Filtres STRICTS : seulement les offres qui respectent EXPLICITEMENT
    la région et les contrats choisis (ajout M4, après tests).

    Différence avec build_filters :
      build_filters        : région choisie OU inconnue, contrat coché OU "inconnu" ;
      build_strict_filters : région choisie,            contrat coché.
    Le salaire reste souple (la plupart des offres ne l'indiquent pas) :
    même clause que build_filters.

    Renvoie None si ni région ni contrat n'est choisi : il n'y a alors pas
    d'offres "exactes" à distinguer, et la 3e recherche n'a pas lieu.
    """
    if not region and not contract_types:
        return None

    filters = []
    if region:
        filters.append({"term": {"region": region}})
    if contract_types:
        # Sans "inconnu", contrairement à build_filters.
        filters.append({"terms": {"contract_types": contract_types}})
    # On réutilise la clause salaire souple de build_filters (sans région ni
    # contrat, elle ne renvoie que celle-là, ou rien).
    filters.extend(build_filters(None, [], salary_min))
    return filters


# ---------------------------------------------------------------------------
# 2. LES RECHERCHES
# ---------------------------------------------------------------------------

def search_bm25(es: Elasticsearch, job_title: str, filters: list[dict]) -> list[dict]:
    """Recherche par MOTS : le métier dans le titre (x3) et la description.

    Structure de la requête bool (les 3 "rôles" d'une clause) :
      must   : OBLIGATOIRE et COMPTE dans le score.
               multi_match -> l'offre doit contenir au moins un mot du métier.
      filter : OBLIGATOIRE mais NE COMPTE PAS dans le score.
               Les critères du formulaire (oui/non, pas de "plus ou moins").
      should : FACULTATIF ; s'il est vrai, AJOUTE des points.
               match_phrase -> bonus si le métier est écrit tel quel dans le titre.

    multi_match cherche le même texte dans plusieurs champs ; "title^3"
    multiplie par 3 le score obtenu dans le titre (un métier dans le titre
    compte plus que dans la description). Les deux champs utilisent
    l'analyseur "french" (mapping) : "ingénieurs" trouve "ingénieur".
    Par défaut, multi_match accepte une offre qui contient "data" OU
    "engineer" : d'où le bonus match_phrase pour l'expression exacte.

    M4 (après tests) : les bonus région / contrat ne sont plus ici (voir
    apply_bonuses) ; le "should" contient maintenant le bonus match_phrase.
    """
    response = es.search(
        index=INDEX_NAME,
        query={
            "bool": {
                "must": {"multi_match": {"query": job_title, "fields": ["title^3", "description"]}},
                "filter": filters,
                # match_phrase : les mots côte à côte, dans le même ordre.
                "should": {"match_phrase": {"title": {"query": job_title, "boost": TITLE_PHRASE_BOOST}}},
            }
        },
        size=CANDIDATES_PER_SEARCH,
        source_includes=RESULT_FIELDS,
    )
    return response["hits"]["hits"]


def search_knn(es: Elasticsearch, query_vector: list[float], filters: list[dict]) -> list[dict]:
    """Recherche par SENS : les offres dont le vecteur est le plus proche.

    knn :
      field          : le champ dense_vector (index HNSW, voir le mapping) ;
      query_vector   : le vecteur de la recherche (384 nombres) ;
      k              : nombre de voisins à renvoyer ;
      num_candidates : nombre de voisins examinés dans le graphe HNSW ;
      filter         : les MÊMES filtres que BM25, appliqués PENDANT la
                       recherche (on obtient bien k offres qui respectent les
                       filtres, pas k offres dont certaines seraient retirées après).
    """
    response = es.search(
        index=INDEX_NAME,
        knn={
            "field": "embedding",
            "query_vector": query_vector,
            "k": CANDIDATES_PER_SEARCH,
            "num_candidates": KNN_NUM_CANDIDATES,
            "filter": filters,
        },
        size=CANDIDATES_PER_SEARCH,
        source_includes=RESULT_FIELDS,
    )
    return response["hits"]["hits"]


# ---------------------------------------------------------------------------
# 3. LA FUSION RRF, PUIS LES BONUS
# ---------------------------------------------------------------------------

def rrf_fuse(rankings: dict[str, list[dict]]) -> list[dict]:
    """Fusionne plusieurs classements avec Reciprocal Rank Fusion.

    rankings : {nom du champ de rang -> résultats de cette recherche}, ex.
        {"rank_bm25": [...], "rank_knn": [...], "rank_exact": [...]}
    (M4, après tests : un dictionnaire au lieu de deux paramètres, pour
    accepter la 3e recherche. Le calcul est le même pour 2 ou 3 listes.)

    Exemple avec RRF_K = 60 :
      offre A : 1re en BM25, 3e en kNN -> 1/61 + 1/63 = 0,0323
      offre B : absente de BM25, 1re en kNN -> 1/61  = 0,0164
      -> A passe devant B : elle est bien classée par les DEUX méthodes.

    Renvoie TOUTES les offres trouvées (jusqu'à 300), triées par score
    décroissant, au format de OfferResult (voir schemas.py).
    M4 (après tests) : on ne coupe plus ici à RESULT_SIZE. Les bonus sont
    ajoutés APRÈS (apply_bonuses) : une offre 30e en RRF peut finir 1re
    grâce à eux, il ne faut donc pas l'avoir déjà retirée.
    """
    # Une entrée par offre, indexée par son identifiant (_id).
    fused: dict[str, dict] = {}

    # enumerate(..., start=1) : donne le rang (1, 2, 3...) avec chaque offre.
    for method, hits in rankings.items():
        for rank, hit in enumerate(hits, start=1):
            # setdefault : crée l'entrée si l'offre n'a pas encore été vue
            # (dans une autre recherche), sinon renvoie l'entrée existante.
            entry = fused.setdefault(hit["_id"], {
                "id": int(hit["_id"]),
                **hit["_source"],          # les champs de l'offre (title, company...)
                "score": 0.0,
                "rank_bm25": None,
                "rank_knn": None,
                "rank_exact": None,
            })
            entry[method] = rank
            entry["score"] += 1 / (RRF_K + rank)

    # sorted(..., key=..., reverse=True) : du plus grand score au plus petit.
    return sorted(fused.values(), key=lambda entry: entry["score"], reverse=True)


def apply_bonuses(offers: list[dict], region: str | None, contract_types: list[str]) -> list[dict]:
    """Ajoute les bonus des critères respectés EXPLICITEMENT, puis retrie (M4).

    POURQUOI APRÈS LA FUSION, ET PAS DANS ELASTICSEARCH ?
      Avant (1re version), ces bonus étaient dans la requête BM25. Mais :
        - le kNN n'en avait pas (on ne peut pas ajouter de points à une
          distance entre vecteurs) ;
        - la fusion RRF ne garde que les RANGS : gagner quelques places en
          BM25 ne change le score final que d'environ 0,001.
      -> Effet presque perdu. Ajoutés ICI, sur le score final, ils comptent
         pleinement, quelle que soit la recherche qui a trouvé l'offre.

    Exemple réel (CV data, alternance cochée) :
      offre 6216 "Alternance Chef de projet SI & Data" : RRF 0,0221 + 0,02 = 0,0421
      offre 83   "Data Engineer", contrat inconnu      : RRF 0,0315 + 0    = 0,0315
      -> l'alternance, sûre, passe devant l'offre au contrat inconnu.

    Les offres "inconnu" ne reçoivent rien : elles restent dans les
    résultats, mais APRÈS celles qui correspondent explicitement.
    """
    # set : ensemble Python, pour tester l'intersection de deux listes avec "&".
    wanted_contracts = set(contract_types)

    for offer in offers:
        # Région de l'offre = région choisie (None si l'offre n'en a pas).
        if region and offer.get("region") == region:
            offer["score"] += BONUS_REGION
        # Au moins un contrat en commun : {"cdi","alternance"} & {"alternance"}
        # = {"alternance"}, non vide -> vrai. "inconnu" n'est jamais coché,
        # donc une offre "inconnu" ne reçoit pas ce bonus.
        if wanted_contracts & set(offer.get("contract_types", [])):
            offer["score"] += BONUS_CONTRACT

    ranking = sorted(offers, key=lambda offer: offer["score"], reverse=True)
    return ranking[:RESULT_SIZE]


# ---------------------------------------------------------------------------
# 4. LA FONCTION APPELÉE PAR L'API
# ---------------------------------------------------------------------------

def hybrid_search(
    es: Elasticsearch,
    cv_text: str,
    job_title: str | None = None,
    region: str | None = None,
    contract_types: list[str] | None = None,
    salary_min: float | None = None,
) -> list[dict]:
    """Recherche hybride complète : filtres, BM25, kNN (x1 ou x2), fusion RRF, bonus.

    Utilisée par la route de test POST /api/search/preview, puis (étape 5)
    par le traitement du mode 1 "offres compatibles".
    """
    contract_types = contract_types or []
    # strip() : un métier fait uniquement d'espaces compte comme vide.
    job_title = (job_title or "").strip()

    filters = build_filters(region, contract_types, salary_min)

    # 1) Par MOTS, seulement si le métier est rempli.
    bm25_hits = []
    if job_title:
        bm25_hits = search_bm25(es, job_title, filters)

    # 2) Par SENS : le métier (s'il y en a un) puis le CV, en un seul texte.
    #    Le modèle ne lit que les ~512 premiers "morceaux de mots" : mettre le
    #    métier EN TÊTE garantit qu'il est toujours pris en compte, même si le
    #    CV est long (la fin d'un long CV est ignorée).
    query_text = f"{job_title}. {cv_text}" if job_title else cv_text
    # Le vecteur est calculé UNE fois et servi aux deux recherches par sens.
    query_vector = embed_query(query_text)
    rankings = {
        "rank_bm25": bm25_hits,
        "rank_knn": search_knn(es, query_vector, filters),
    }

    # 2 bis) Par SENS parmi les offres EXACTES (M4, après tests), seulement
    #    si une région ou un contrat est choisi.
    strict_filters = build_strict_filters(region, contract_types, salary_min)
    if strict_filters is not None:
        rankings["rank_exact"] = search_knn(es, query_vector, strict_filters)

    # 3) Fusion des classements, puis 4) bonus des critères respectés
    #    (M4, après tests) et coupe aux RESULT_SIZE meilleures.
    return apply_bonuses(rrf_fuse(rankings), region, contract_types)
