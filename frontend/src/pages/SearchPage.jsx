// src/pages/SearchPage.jsx — l'assistant de recherche en 4 étapes (maquette "2 · Assistant").
//
//   Étape 1 « Vous »          : nom, email, texte du CV        (obligatoires)
//   Étape 2 « Objectif »      : le mode (seul "offers" est disponible aujourd'hui)
//   Étape 3 « Critères »      : métier, région, salaire, contrats (tous facultatifs)
//   Étape 4 « Récapitulatif » : on relit, puis on envoie à l'API
//
// Après l'envoi, l'API renvoie l'id de la demande et on va sur /resultats/:id.
//
// Notion clé : l'ÉTAT (state). useState garde une valeur en mémoire ENTRE deux
// affichages. Quand on la change (setForm, setStep…), React ré-affiche le composant
// avec la nouvelle valeur. Tout le formulaire tient dans UN objet "form".
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Alert, Badge, Box, Button, Chip, Container, Group, NumberInput, Paper, Select,
  SimpleGrid, Stack, Text, Textarea, TextInput, Title, UnstyledButton,
} from '@mantine/core'

import { createSearch, getRegions } from '../api.js'
import { COLORS } from '../theme.js'

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const STEP_LABELS = ['Vous', 'Objectif', 'Critères', 'Récapitulatif']

// Mêmes règles que SearchCreate dans api/app/schemas.py : on prévient l'utilisateur
// AVANT l'envoi, plutôt que de recevoir une erreur 422 de l'API.
const CV_MIN_LENGTH = 50
const CV_MAX_LENGTH = 20_000
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/ // "quelque chose @ quelque chose . quelque chose"

// Les 4 objectifs (= le champ "mode" de l'API). value = valeur envoyée à l'API.
const GOALS = [
  { value: 'offers', title: 'Trouver des offres', text: 'Les offres réelles les plus proches de votre profil.', available: true },
  { value: 'skills', title: 'Compétences à développer', text: 'Ce que le marché attend de vous.', available: false },
  { value: 'cv', title: 'Booster mon CV', text: "L'adapter à une offre précise.", available: false },
  { value: 'letter', title: 'Lettre de motivation', text: "Rédigée pour l'offre de votre choix.", available: false },
]

// Les contrats : value = valeur de l'API (ContractType), label = texte affiché.
const CONTRACTS = [
  { value: 'cdi', label: 'CDI' },
  { value: 'cdd', label: 'CDD' },
  { value: 'stage', label: 'Stage' },
  { value: 'alternance', label: 'Alternance' },
  { value: 'freelance', label: 'Freelance' },
]

// Valeurs de départ du formulaire. Les champs facultatifs vides valent '' ou [] ;
// on les transformera en null au moment de l'envoi (voir buildPayload).
const EMPTY_FORM = {
  full_name: '',
  email: '',
  cv_text: '',
  mode: 'offers',
  job_title: '',
  region: null,        // null = "Toute la France"
  contract_types: [],  // [] = tous les contrats
  salary_min: '',
}

// ---------------------------------------------------------------------------
// Fonctions utilitaires (pures : elles ne touchent pas à l'état, faciles à tester)
// ---------------------------------------------------------------------------

// Vérifie les champs d'UNE étape. Renvoie un objet { champ: message } ;
// un objet vide {} signifie "tout est bon".
function validateStep(step, form) {
  const errors = {}
  if (step === 1) {
    if (!form.full_name.trim()) errors.full_name = 'Indiquez votre nom.'
    if (!EMAIL_PATTERN.test(form.email.trim())) errors.email = 'Adresse email invalide.'
    const cvLength = form.cv_text.trim().length
    if (cvLength < CV_MIN_LENGTH) {
      errors.cv_text = `Votre CV est trop court : ${CV_MIN_LENGTH} caractères minimum (${cvLength} actuellement).`
    }
  }
  // Étape 3 : rien d'obligatoire. NumberInput empêche déjà les valeurs négatives (min={0}),
  // et maxLength limite le métier à 100 caractères.
  return errors
}

// Transforme le formulaire en corps JSON attendu par POST /api/searches.
// Un champ facultatif vide devient null : l'API comprend "pas de critère".
function buildPayload(form) {
  return {
    full_name: form.full_name.trim(),
    email: form.email.trim(),
    cv_text: form.cv_text.trim(),
    mode: form.mode,
    job_title: form.job_title.trim() || null, // '' est "faux" en JS → null
    region: form.region || null,
    contract_types: form.contract_types,
    salary_min: form.salary_min === '' ? null : Number(form.salary_min),
  }
}

// ---------------------------------------------------------------------------
// Petits composants d'affichage
// ---------------------------------------------------------------------------

// Barre d'avancement : 4 segments, colorés jusqu'à l'étape actuelle.
function StepProgress({ step }) {
  return (
    <Stack gap={12}>
      <Text size="sm" fw={600} c="#5A5778">Étape {step} sur {STEP_LABELS.length}</Text>
      <SimpleGrid cols={4} spacing={10}>
        {STEP_LABELS.map((label, index) => {
          const number = index + 1
          const reached = number <= step // étape atteinte (passée ou actuelle)
          return (
            <Stack key={label} gap={8}>
              <Box h={6} bg={reached ? 'violet.6' : '#E2DEF3'} style={{ borderRadius: 999 }} />
              <Text size="sm" fw={number === step ? 700 : 500} c={reached ? COLORS.ink : '#6E6B88'}>
                {label}
              </Text>
            </Stack>
          )
        })}
      </SimpleGrid>
    </Stack>
  )
}

// Titre + sous-titre en haut de chaque étape.
function StepHeader({ title, subtitle }) {
  return (
    <div>
      <Title order={1} fz="clamp(28px, 4vw, 36px)" mb={8} style={{ letterSpacing: -0.6 }}>{title}</Title>
      <Text c={COLORS.muted}>{subtitle}</Text>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Les 4 étapes. Chacune reçoit :
//   form     : les valeurs actuelles
//   setField : fonction pour changer UN champ, ex. setField('email', 'a@b.fr')
//   errors   : les messages d'erreur à afficher sous les champs
// ---------------------------------------------------------------------------

function StepProfile({ form, setField, errors }) {
  const cvLength = form.cv_text.trim().length
  return (
    <Stack gap={24}>
      <StepHeader title="Parlez-nous de vous" subtitle="Votre CV est la base de la recherche. Rien n'est publié." />

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={16}>
        {/* Champ "contrôlé" : value vient de l'état, onChange met l'état à jour.
            event.currentTarget.value = le texte actuellement tapé dans le champ. */}
        <TextInput
          label="Nom complet"
          placeholder="Léa Martin"
          size="md"
          maxLength={100}
          value={form.full_name}
          onChange={(event) => setField('full_name', event.currentTarget.value)}
          error={errors.full_name}
        />
        <TextInput
          label="Email"
          type="email"
          placeholder="lea@example.com"
          size="md"
          value={form.email}
          onChange={(event) => setField('email', event.currentTarget.value)}
          error={errors.email}
        />
      </SimpleGrid>

      <Textarea
        label="Collez le texte de votre CV"
        description="Compétences, formations, expériences… Plus il est complet, meilleurs sont les résultats."
        placeholder="Étudiante en école d'ingénieurs, spécialité data. Compétences : Python, SQL, Spark…"
        size="md"
        autosize          // la zone grandit avec le texte…
        minRows={8}
        maxRows={16}      // …jusqu'à 16 lignes, puis une barre de défilement apparaît
        maxLength={CV_MAX_LENGTH}
        value={form.cv_text}
        onChange={(event) => setField('cv_text', event.currentTarget.value)}
        error={errors.cv_text}
      />
      {/* Compteur : vert quand le minimum est atteint */}
      <Text size="sm" c={cvLength >= CV_MIN_LENGTH ? 'mint.7' : 'dimmed'} mt={-16}>
        {cvLength} caractère{cvLength > 1 ? 's' : ''} · {CV_MIN_LENGTH} minimum
      </Text>
    </Stack>
  )
}

function StepGoal({ form, setField }) {
  return (
    <Stack gap={24}>
      <StepHeader title="Que voulez-vous faire ?" subtitle="Choisissez un objectif." />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={16}>
        {GOALS.map((goal) => {
          const selected = form.mode === goal.value
          return (
            // UnstyledButton : un vrai <button> (cliquable au clavier) sans style imposé,
            // pour dessiner nos propres cartes.
            <UnstyledButton
              key={goal.value}
              disabled={!goal.available}
              onClick={() => setField('mode', goal.value)}
              p={22}
              style={{
                borderRadius: 20,
                border: `2px solid ${selected ? '#5B3DF5' : '#E2DEF3'}`,
                background: selected ? '#F4F1FF' : '#FFFFFF',
                opacity: goal.available ? 1 : 0.55,
                cursor: goal.available ? 'pointer' : 'not-allowed',
              }}
            >
              <Group gap={8} mb={8}>
                <Text fw={700} fz={18}>{goal.title}</Text>
                {!goal.available && <Badge color="coral" variant="light" radius="xl" tt="none">Bientôt</Badge>}
              </Group>
              <Text size="sm" c={COLORS.muted}>{goal.text}</Text>
            </UnstyledButton>
          )
        })}
      </SimpleGrid>
    </Stack>
  )
}

function StepCriteria({ form, setField, regions }) {
  // Format attendu par <Select> : [{ value, label }]. La 1re option (value '') = pas de filtre.
  const regionOptions = [
    { value: '', label: 'Toute la France' },
    ...regions.map((region) => ({ value: region, label: region })), // "..." = on déplie la liste
  ]

  return (
    <Stack gap={24}>
      <StepHeader title="Vos critères" subtitle="Tout est facultatif : laissez vide pour élargir la recherche." />

      <TextInput
        label="Métier recherché"
        placeholder="data engineer"
        size="md"
        maxLength={100}
        value={form.job_title}
        onChange={(event) => setField('job_title', event.currentTarget.value)}
      />

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={16}>
        <Select
          label="Région"
          size="md"
          data={regionOptions}
          value={form.region ?? ''}           // null → '' pour afficher "Toute la France"
          onChange={(value) => setField('region', value || null)}
          allowDeselect={false}               // on ne peut pas "vider" : on choisit "Toute la France"
          searchable                          // on peut taper pour filtrer la liste
        />
        <NumberInput
          label="Salaire annuel minimum (€)"
          placeholder="Facultatif"
          size="md"
          min={0}
          step={1000}
          thousandSeparator=" "               // affiche 35 000 au lieu de 35000
          hideControls
          value={form.salary_min}
          onChange={(value) => setField('salary_min', value)} // nombre, ou '' si vide
        />
      </SimpleGrid>

      <div>
        <Text fw={500} mb={10}>Type de contrat</Text>
        {/* Chip.Group multiple : plusieurs puces cochables ; value = tableau des valeurs cochées */}
        <Chip.Group multiple value={form.contract_types} onChange={(values) => setField('contract_types', values)}>
          <Group gap={10}>
            {CONTRACTS.map((contract) => (
              <Chip key={contract.value} value={contract.value} size="md" variant="outline">
                {contract.label}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Text size="sm" c="dimmed" mt={8}>Aucun contrat coché = tous les contrats.</Text>
      </div>
    </Stack>
  )
}

function StepSummary({ form }) {
  const goal = GOALS.find((g) => g.value === form.mode)
  const contractLabels = CONTRACTS
    .filter((c) => form.contract_types.includes(c.value))
    .map((c) => c.label)

  // Chaque ligne du récapitulatif : [titre, valeur]
  const rows = [
    ['Profil', `${form.full_name.trim()} · ${form.email.trim()} · CV de ${form.cv_text.trim().length} caractères`],
    ['Objectif', goal.title],
    ['Métier', form.job_title.trim() || 'Non précisé'],
    ['Région', form.region || 'Toute la France'],
    ['Contrat', contractLabels.length ? contractLabels.join(', ') : 'Tous les contrats'],
    ['Salaire minimum', form.salary_min === '' ? 'Non précisé' : `${Number(form.salary_min).toLocaleString('fr-FR')} € / an`],
  ]

  return (
    <Stack gap={24}>
      <StepHeader title="Tout est prêt" subtitle="Vérifiez vos informations avant de lancer la recherche." />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
        {rows.map(([label, value]) => (
          <Box key={label} p={16} bg="#F6F5FD" style={{ borderRadius: 16 }}>
            <Text size="xs" fw={700} c="#5A5778" tt="uppercase" mb={4}>{label}</Text>
            <Text fw={600} style={{ wordBreak: 'break-word' }}>{value}</Text>
          </Box>
        ))}
      </SimpleGrid>
    </Stack>
  )
}

// ---------------------------------------------------------------------------
// La page
// ---------------------------------------------------------------------------
export default function SearchPage() {
  const navigate = useNavigate() // pour changer de page depuis le code (après l'envoi)

  const [step, setStep] = useState(1)              // étape affichée (1 à 4)
  const [form, setForm] = useState(EMPTY_FORM)     // toutes les valeurs du formulaire
  const [errors, setErrors] = useState({})         // erreurs de validation de l'étape
  const [regions, setRegions] = useState([])       // liste reçue de GET /api/regions
  const [submitting, setSubmitting] = useState(false) // envoi en cours → bouton en chargement
  const [submitError, setSubmitError] = useState(null) // message si l'API refuse / ne répond pas

  // useEffect(fonction, []) : exécute la fonction UNE fois, juste après le premier affichage.
  // Idéal pour charger des données au démarrage de la page.
  useEffect(() => {
    getRegions()
      .then(setRegions)
      .catch(() => setRegions([])) // API indisponible : on garde seulement "Toute la France"
  }, [])

  // Change UN champ sans toucher aux autres.
  // { ...previous, [name]: value } = copie de l'objet, avec le champ "name" remplacé.
  // (Avec React, on ne modifie jamais l'état directement : on en crée une nouvelle version.)
  function setField(name, value) {
    setForm((previous) => ({ ...previous, [name]: value }))
    setErrors((previous) => ({ ...previous, [name]: undefined })) // on efface l'erreur du champ corrigé
  }

  function goNext() {
    const stepErrors = validateStep(step, form)
    setErrors(stepErrors)
    // Object.keys({}) = [] : pas d'erreur → on passe à l'étape suivante
    if (Object.keys(stepErrors).length === 0) setStep(step + 1)
  }

  function goBack() {
    setSubmitError(null)
    setStep(step - 1)
  }

  // "async" car on attend la réponse de l'API avec "await".
  async function submit() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const created = await createSearch(buildPayload(form)) // → { id, candidate_id, status }
      navigate(`/resultats/${created.id}`)                    // page des résultats
    } catch (error) {
      setSubmitError(error.message) // message préparé par api.js (ApiError)
      setSubmitting(false)
    }
  }

  const isLastStep = step === STEP_LABELS.length

  return (
    <Container size={880} pt={24} pb={72}>
      <Stack gap={28}>
        <StepProgress step={step} />

        <Paper p={{ base: 24, sm: 40 }} radius={28} style={{ boxShadow: '0 12px 40px rgba(27,22,64,0.08)' }}>
          <Stack gap={28}>
            {/* Affichage conditionnel : "condition && <Composant />" n'affiche
                le composant QUE si la condition est vraie. */}
            {step === 1 && <StepProfile form={form} setField={setField} errors={errors} />}
            {step === 2 && <StepGoal form={form} setField={setField} />}
            {step === 3 && <StepCriteria form={form} setField={setField} regions={regions} />}
            {step === 4 && <StepSummary form={form} />}

            {submitError && (
              <Alert color="red" radius="lg" title="La recherche n'a pas pu être lancée">
                {submitError}
              </Alert>
            )}

            {/* Boutons de navigation */}
            <Group justify="space-between">
              {/* Sur l'étape 1, pas de "Précédent" : un <div /> vide garde "Suivant" à droite */}
              {step > 1 ? (
                <Button variant="subtle" color="gray" size="md" radius="xl" onClick={goBack} disabled={submitting}>
                  ← Précédent
                </Button>
              ) : <div />}

              {isLastStep ? (
                <Button size="lg" radius="xl" color="coral.6" c={COLORS.ink} onClick={submit} loading={submitting}>
                  Lancer la recherche
                </Button>
              ) : (
                <Button size="md" radius="xl" onClick={goNext}>
                  Suivant →
                </Button>
              )}
            </Group>
          </Stack>
        </Paper>
      </Stack>
    </Container>
  )
}