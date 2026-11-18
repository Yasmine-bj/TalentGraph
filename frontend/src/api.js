// src/api.js — le SEUL fichier du frontend qui parle à l'API FastAPI.
//
// Pourquoi un fichier à part ?
//   Les pages n'ont pas à savoir COMMENT on parle au serveur (URL, méthode HTTP,
//   en-têtes, gestion d'erreurs). Elles appellent juste createSearch(...) ou
//   getSearch(id). Si une route change un jour, on ne modifie QUE ce fichier.
//
// Les URL commencent par /api : en développement, le proxy de Vite les envoie
// vers localhost:8000 ; en production, ce sera nginx (voir vite.config.js).

const BASE_URL = '/api'

// Erreur "enrichie" : en plus du message, on garde le code HTTP (404, 422, 503…)
// pour que la page puisse réagir différemment selon le cas.
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Transforme le "detail" renvoyé par FastAPI en une phrase lisible.
//   - erreur 422 (validation Pydantic) : detail est une LISTE
//     ex. [{ loc: ['body', 'cv_text'], msg: 'String should have at least 50 characters' }]
//   - nos HTTPException (404, 503) : detail est une simple CHAÎNE
function readErrorDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((err) => `${err.loc?.at(-1) ?? 'champ'} : ${err.msg}`) // at(-1) = dernier élément = nom du champ
      .join(' · ')
  }
  return typeof detail === 'string' ? detail : null
}

// Fonction interne commune à tous les appels.
//   path    : la fin de l'URL, ex. '/searches/42'
//   options : les options de fetch (méthode, corps…)
async function request(path, options = {}) {
  let response
  try {
    // fetch() est la fonction du navigateur pour faire une requête HTTP.
    // Elle renvoie une PROMESSE : "await" attend la réponse sans bloquer la page.
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' }, // on envoie / reçoit du JSON
      ...options,
    })
  } catch {
    // fetch n'échoue (throw) QUE si le serveur est injoignable (API éteinte, réseau coupé).
    throw new ApiError("Impossible de joindre le serveur. L'API est-elle démarrée ?", 0)
  }

  // On essaie de lire le corps en JSON (il peut être vide ou ne pas être du JSON).
  const data = await response.json().catch(() => null)

  // response.ok = true pour les codes 200 à 299. Sinon c'est une erreur HTTP :
  // contrairement à ce que beaucoup croient, fetch ne "throw" PAS sur un 404 ou 500 :
  // c'est à nous de le vérifier.
  if (!response.ok) {
    const message = readErrorDetail(data?.detail) ?? `Erreur ${response.status}`
    throw new ApiError(message, response.status)
  }
  return data
}

// ---------------------------------------------------------------------------
// Les fonctions utilisées par les pages
// ---------------------------------------------------------------------------

// POST /api/searches — enregistre la demande (PostgreSQL + Redis) et lance la recherche.
// payload : { full_name, email, cv_text, mode, job_title, region, contract_types, salary_min }
// Réponse (201) : { id, candidate_id, status: 'pending' }
export function createSearch(payload) {
  return request('/searches', {
    method: 'POST',
    body: JSON.stringify(payload), // objet JS → texte JSON
  })
}

// GET /api/searches/{id} — état de la demande, et ses résultats quand status = 'done'.
// Réponse : { id, status, results: { offers: [...] } | null, error_message, ... }
export function getSearch(id) {
  return request(`/searches/${id}`)
}

// GET /api/regions — la liste officielle des régions (pour la liste déroulante).
// Réponse : ['Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', ...]
export function getRegions() {
  return request('/regions')
}
