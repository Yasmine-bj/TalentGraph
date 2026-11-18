// src/pages/ResultsPage.jsx — /resultats/:id : attente, puis résultats (maquettes 3 et 4).
//
// RAPPEL DU FONCTIONNEMENT DE L'API (M4, étape 5) :
//   POST /api/searches répond TOUT DE SUITE (statut "pending"), puis la recherche
//   tourne en arrière-plan (BackgroundTasks) : "pending" → "running" → "done" ou "failed".
//
// Le frontend fait donc du POLLING : il redemande GET /api/searches/:id toutes
// les 1,5 seconde tant que la recherche n'est pas terminée.
//   - pending / running → écran d'attente
//   - done              → les offres (results.offers)
//   - failed            → le message d'erreur (error_message)
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import {
  Alert, Badge, Box, Button, Container, Grid, Group, Paper, Radio, Stack, Text, Title,
} from '@mantine/core'

import { getSearch } from '../api.js'
import { CheckIcon, SearchIcon } from '../components/Icons.jsx'
import OfferCard, { CONTRACT_LABELS } from '../components/OfferCard.jsx'
import { COLORS } from '../theme.js'

const POLL_INTERVAL_MS = 1500   // délai entre deux questions à l'API
const SLOW_NOTICE_MS = 20_000   // au-delà, on explique pourquoi c'est long

// Une offre respecte-t-elle EXPLICITEMENT les critères choisis ?
// (Pour le filtre "Vos critères uniquement". Une offre à la région inconnue ou
// au contrat "inconnu" n'est pas exclue par l'API, mais elle ne passe pas ce filtre.)
function matchesCriteria(offer, search) {
  const regionOk = !search.region || offer.region === search.region
  const contractOk =
    search.contract_types.length === 0 ||
    offer.contract_types.some((c) => search.contract_types.includes(c)) // au moins un en commun
  return regionOk && contractOk
}

// ---------------------------------------------------------------------------
// Écran d'attente (maquette "3 · Recherche en cours")
// ---------------------------------------------------------------------------

// Animations CSS : rotation (spinner) et "respiration" (icône). Une balise <style>
// dans le composant suffit pour deux animations.
const ANIMATIONS = `
  @keyframes tg-spin { to { transform: rotate(360deg) } }
  @keyframes tg-pulse { 0%, 100% { transform: scale(1); opacity: 1 } 50% { transform: scale(1.06); opacity: .85 } }
`

// Une ligne de la liste d'étapes. state : 'done' | 'active' | 'waiting'
function LoadingStep({ state, children }) {
  return (
    <Group gap={14} p="18px 20px" bg="white" wrap="nowrap"
      style={{ borderRadius: 18, boxShadow: state === 'active' ? '0 0 0 2px #5B3DF5' : 'none' }}>
      {state === 'done' && (
        <Box w={32} h={32} bg="mint.6" c="white" style={{
          borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <CheckIcon size={16} width={3} />
        </Box>
      )}
      {state === 'active' && (
        <Box w={32} h={32} style={{
          borderRadius: '50%', flexShrink: 0, border: '3px solid #E2DEF3', borderTopColor: '#5B3DF5',
          animation: 'tg-spin 1.1s linear infinite',
        }} />
      )}
      {state === 'waiting' && (
        <Box w={32} h={32} style={{ borderRadius: '50%', flexShrink: 0, border: '2px dashed #CFCAE6' }} />
      )}
      <Text fw={600} c={state === 'waiting' ? '#6E6B88' : COLORS.ink}>{children}</Text>
    </Group>
  )
}

function LoadingView({ slow }) {
  return (
    <Container size={640} pt={48} pb={88}>
      <style>{ANIMATIONS}</style>
      <Stack align="center" gap={32} ta="center">
        <Box w={120} h={120} bg="violet.6" c="white" style={{
          borderRadius: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 20px 50px rgba(91,61,245,0.35)', animation: 'tg-pulse 1.8s ease-in-out infinite',
        }}>
          <SearchIcon size={52} />
        </Box>
        <div>
          <Title order={1} fz="clamp(30px, 4vw, 38px)" mb={10}>Nous cherchons vos offres…</Title>
          <Text fz={17} c={COLORS.muted}>
            {slow
              ? 'La première recherche peut prendre un peu plus de temps (chargement du modèle). Merci de patienter.'
              : 'Cela prend généralement quelques secondes.'}
          </Text>
        </div>
        <Stack gap={12} w="100%" ta="left">
          <LoadingStep state="done">Votre demande est enregistrée dans la base</LoadingStep>
          <LoadingStep state="active">On passe 20 000+ offres du jour au crible pour vous</LoadingStep>
          <LoadingStep state="waiting">Classement des offres les plus compatibles</LoadingStep>
        </Stack>
      </Stack>
    </Container>
  )
}

// ---------------------------------------------------------------------------
// Écran d'erreur (demande introuvable, recherche échouée, API injoignable)
// ---------------------------------------------------------------------------

function ErrorView({ title, message }) {
  return (
    <Container size={640} pt={48} pb={88}>
      <Stack gap={24}>
        <Alert color="red" radius="lg" title={title}>{message}</Alert>
        <Button component={Link} to="/recherche" radius="xl" size="md" style={{ alignSelf: 'flex-start' }}>
          Faire une nouvelle recherche
        </Button>
      </Stack>
    </Container>
  )
}

// ---------------------------------------------------------------------------
// Colonne de gauche : résumé de la recherche + filtre
// ---------------------------------------------------------------------------

function SearchSummary({ search, filter, setFilter, counts }) {
  const hasCriteria = Boolean(search.region) || search.contract_types.length > 0
  const createdAt = new Date(search.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })

  return (
    <Stack gap={16}>
      <Paper p={20} radius={20}>
        <Text size="xs" fw={700} c="#5A5778" tt="uppercase" mb={6}>Votre recherche</Text>
        <Text fw={700} fz={18} mb={10}>{search.job_title || 'Métier non précisé'}</Text>
        <Group gap={6} mb={10}>
          <Badge variant="light" radius="xl" tt="none">{search.region || 'Toute la France'}</Badge>
          {search.contract_types.length === 0
            ? <Badge variant="light" radius="xl" tt="none">Tous les contrats</Badge>
            : search.contract_types.map((c) => (
              <Badge key={c} variant="light" radius="xl" tt="none">{CONTRACT_LABELS[c] ?? c}</Badge>
            ))}
        </Group>
        <Text size="sm" c="#6E6B88">Demande n° {search.id} · {createdAt}</Text>
      </Paper>

      {/* Le filtre n'a de sens que si une région ou un contrat a été choisi */}
      {hasCriteria && (
        <Paper p={20} radius={20}>
          <Radio.Group label="Afficher" value={filter} onChange={setFilter}>
            <Stack gap={10} mt={10}>
              <Radio value="all" label={`Toutes les offres (${counts.all})`} />
              <Radio value="criteria" label={`Vos critères uniquement (${counts.criteria})`} />
            </Stack>
          </Radio.Group>
        </Paper>
      )}

      <Button component={Link} to="/recherche" variant="light" radius="xl" size="md">
        Nouvelle recherche
      </Button>
    </Stack>
  )
}

// ---------------------------------------------------------------------------
// La page
// ---------------------------------------------------------------------------
export default function ResultsPage() {
  const { id } = useParams() // /resultats/42 → id = '42'

  const [search, setSearch] = useState(null) // la réponse de GET /api/searches/:id
  const [error, setError] = useState(null)   // ApiError si l'appel échoue
  const [slow, setSlow] = useState(false)    // la recherche dure plus de SLOW_NOTICE_MS
  const [filter, setFilter] = useState('all') // 'all' | 'criteria'

  // POLLING. Se relance si l'id de l'URL change ([id] = liste des dépendances).
  useEffect(() => {
    let cancelled = false // passe à true si on quitte la page : on arrête tout
    let timer = null

    async function poll() {
      try {
        const data = await getSearch(id)
        if (cancelled) return
        setSearch(data)
        // Pas encore terminée → on redemande dans POLL_INTERVAL_MS
        if (data.status === 'pending' || data.status === 'running') {
          timer = setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (!cancelled) setError(err)
      }
    }

    poll()
    const slowTimer = setTimeout(() => setSlow(true), SLOW_NOTICE_MS)

    // Fonction de NETTOYAGE : React l'appelle quand on quitte la page.
    // Sans elle, le polling continuerait en arrière-plan pour rien.
    return () => {
      cancelled = true
      clearTimeout(timer)
      clearTimeout(slowTimer)
    }
  }, [id])

  // 1) Erreurs
  if (error) {
    return error.status === 404
      ? <ErrorView title="Recherche introuvable" message={`Aucune demande n° ${id}. Le lien est peut-être incorrect.`} />
      : <ErrorView title="Impossible de charger la recherche" message={error.message} />
  }
  if (search?.status === 'failed') {
    return <ErrorView title="La recherche a échoué" message={search.error_message || 'Erreur inconnue.'} />
  }

  // 2) Attente (pas encore de réponse, ou recherche en cours)
  if (!search || search.status !== 'done') {
    return <LoadingView slow={slow} />
  }

  // 3) Résultats
  const offers = search.results?.offers ?? []
  const criteriaOffers = offers.filter((offer) => matchesCriteria(offer, search))
  const shown = filter === 'criteria' ? criteriaOffers : offers

  return (
    <Container size={1200} pt={16} pb={88}>
      {/* Grid : 12 colonnes. Sur grand écran, 4 pour le résumé, 8 pour les offres ;
          sur téléphone, chaque bloc prend les 12 (l'un sous l'autre). */}
      <Grid gutter={32}>
        <Grid.Col span={{ base: 12, md: 4 }}>
          {/* position: sticky : le résumé reste visible quand on fait défiler les offres */}
          <Box style={{ position: 'sticky', top: 16 }}>
            <SearchSummary
              search={search}
              filter={filter}
              setFilter={setFilter}
              counts={{ all: offers.length, criteria: criteriaOffers.length }}
            />
          </Box>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap={20}>
            <Group justify="space-between" align="baseline">
              <Title order={1} fz="clamp(28px, 3.5vw, 34px)" style={{ letterSpacing: -0.5 }}>
                {shown.length} offre{shown.length > 1 ? 's' : ''} pour vous
              </Title>
              <Text size="sm" c="#5A5778">Classées par compatibilité</Text>
            </Group>

            {/* <details>/<summary> : bloc repliable natif du navigateur, sans JavaScript */}
            <Box component="details" p="16px 20px" bg="white" style={{ borderRadius: 18 }}>
              <Box component="summary" fw={600} c="violet.8" style={{ cursor: 'pointer' }}>
                Comment est calculée la compatibilité ?
              </Box>
              <Text size="sm" c="#3A3756" mt={10} lh={1.6}>
                Nous comparons votre CV aux offres de deux façons : par vos mots-clés et par le sens de
                votre parcours. Les offres bien classées par les deux méthodes passent devant. Celles qui
                respectent vos critères (région, contrat) reçoivent un bonus. Le pourcentage compare le
                score de l'offre au meilleur score possible pour votre recherche.
              </Text>
            </Box>

            {shown.length === 0 ? (
              <Alert color="violet" radius="lg" title="Aucune offre pour l'instant">
                Essayez avec moins de critères : une autre région, plus de types de contrat, ou sans salaire minimum.
              </Alert>
            ) : (
              shown.map((offer, index) => (
                <OfferCard key={offer.id} offer={offer} position={index + 1} />
              ))
            )}
          </Stack>
        </Grid.Col>
      </Grid>
    </Container>
  )
}
