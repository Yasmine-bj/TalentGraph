// =============================================================================
// api.js — Les appels à l'API TalentGraph (FastAPI)
//
// Tous les échanges avec le serveur passent par ce fichier : les composants
// appellent getRegions(), createSearch(), getSearch() sans se soucier de HTTP.
//
// Les adresses commencent par /api : la page et l'API ont la MÊME origine.
//   - en développement, Vite transmet /api à localhost:8000 (vite.config.js) ;
//   - en production, nginx transmet /api au conteneur api (nginx.conf).
// =============================================================================

// Noms lisibles des champs, pour les messages d'erreur de validation (422).
const FIELD_LABELS = {
  full_name: 'Nom',
  email: 'Email',
  cv_text: 'CV',
  mode: 'Mode',
  job_title: 'Métier',
  region: 'Région',
  contract_types: 'Contrats',
  salary_min: 'Salaire minimum',
}

// Erreur renvoyée par l'API, avec son code HTTP (404, 422, 503...).
export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// Transforme le "detail" d'une erreur FastAPI en message lisible.
//   422 : detail = [{loc: ["body", "cv_text"], msg: "..."}, ...]
//   autres : detail = "texte"
function formatDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = d.loc?.[d.loc.length - 1]
        return `${FIELD_LABELS[field] ?? field} : ${d.msg}`
      })
      .join(' · ')
  }
  return detail ?? 'Erreur inattendue du serveur.'
}

// Envoie une requête et renvoie le JSON de la réponse.
// fetch : la fonction du navigateur pour faire une requête HTTP.
// Si le code HTTP n'est pas 2xx (res.ok faux), on lève une ApiError.
async function request(path, options = {}) {
  let res
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    // Pas de réponse du tout (serveur arrêté, réseau coupé).
    throw new ApiError(0, "Impossible de joindre l'API. Les conteneurs sont-ils démarrés ?")
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(res.status, formatDetail(data?.detail))
  }
  return data
}

// GET /api/regions -> ["Auvergne-Rhône-Alpes", ...] (liste déroulante)
export function getRegions() {
  return request('/api/regions')
}

// POST /api/searches -> {id, candidate_id, status: "pending"}
export function createSearch(payload) {
  return request('/api/searches', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// GET /api/searches/{id} -> la demande complète (statut, résultats...)
export function getSearch(id) {
  return request(`/api/searches/${id}`)
}
