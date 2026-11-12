// =============================================================================
// constants.js — Valeurs partagées par plusieurs composants
// =============================================================================

// Les 4 modes de TalentGraph (mêmes valeurs que l'API : schemas.py, Mode).
// available: false -> affiché, mais pas encore sélectionnable (agents IA, M5).
export const MODES = [
  {
    value: 'offers',
    label: 'Offres compatibles',
    description: 'Les offres réelles les plus proches de votre profil.',
    available: true,
  },
  {
    value: 'skills',
    label: 'Compétences à travailler',
    description: 'Ce que le marché demande et qui manque à votre CV.',
    available: false,
  },
  {
    value: 'cv',
    label: 'Améliorer mon CV',
    description: 'Des conseils pour adapter votre CV à une offre.',
    available: false,
  },
  {
    value: 'letter',
    label: 'Lettre de motivation',
    description: 'Une lettre rédigée pour une offre précise.',
    available: false,
  },
]

// Contrats (mêmes valeurs que l'API : schemas.py, ContractType).
export const CONTRACTS = [
  { value: 'cdi', label: 'CDI' },
  { value: 'cdd', label: 'CDD' },
  { value: 'stage', label: 'Stage' },
  { value: 'alternance', label: 'Alternance' },
  { value: 'freelance', label: 'Freelance' },
]

// Libellés affichés sur les cartes d'offres (avec "inconnu", jamais coché).
export const CONTRACT_LABELS = {
  ...Object.fromEntries(CONTRACTS.map((c) => [c.value, c.label])),
  inconnu: 'Contrat non précisé',
}

// Un exemple complet, pour tester l'application en un clic.
export const EXAMPLE = {
  full_name: 'Léa Martin',
  email: 'lea.martin@example.com',
  cv_text:
    "Étudiante en école d'ingénieurs, spécialité data. Compétences : Python, SQL, " +
    'Spark, Airflow, Docker, PostgreSQL. Projet : pipeline de données (ingestion, ' +
    'nettoyage, entrepôt de données) et tableau de bord. Recherche une alternance ' +
    'en data engineering.',
  mode: 'offers',
  job_title: 'data engineer',
  region: 'Île-de-France',
  contract_types: ['alternance'],
  salary_min: '',
}
