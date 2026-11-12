// =============================================================================
// App.jsx — La page TalentGraph : formulaire à gauche, résultats à droite.
//
// Gère l'ÉTAT de la page :
//   - regions  : la liste des régions (GET /api/regions, au chargement) ;
//   - search   : la demande en cours ({id, status, results, error_message}) ;
//   - criteria : les critères envoyés (pour signaler les offres qui les respectent) ;
//   - error    : une erreur à afficher (API injoignable, données refusées...).
//
// Le parcours d'une demande :
//   1. SearchForm appelle handleSubmit -> POST /api/searches -> {id, "pending"}
//   2. POLLING : tant que le statut est pending ou running, on relit
//      GET /api/searches/{id} toutes les secondes ;
//   3. done -> on affiche les offres ; failed -> on affiche le message.
// =============================================================================

import { useEffect, useState } from 'react'
import { Alert, Anchor, Badge, Container, Grid, Group, Stack, Text } from '@mantine/core'
import { createSearch, getRegions, getSearch } from './api'
import { CONTRACT_LABELS } from './constants'
import Header from './components/Header'
import HowItWorks from './components/HowItWorks'
import OfferCard from './components/OfferCard'
import OfferSkeleton from './components/OfferSkeleton'
import SearchForm from './components/SearchForm'
import StatusSteps from './components/StatusSteps'

const POLL_INTERVAL_MS = 1000 // relecture du statut toutes les secondes
const POLL_MAX_TRIES = 180 // au-delà de 3 minutes, on abandonne

export default function App() {
  const [regions, setRegions] = useState([])
  const [search, setSearch] = useState(null)
  const [criteria, setCriteria] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Au chargement de la page : la liste des régions (une seule fois, d'où []).
  useEffect(() => {
    getRegions()
      .then(setRegions)
      .catch((e) => setError(e.message))
  }, [])

  // POLLING : chaque fois que la demande change et n'est pas terminée, on
  // programme une relecture dans 1 seconde. La fonction renvoyée ("cleanup")
  // annule le minuteur si la page change avant (nouvelle demande...).
  const searchId = search?.id
  const status = search?.status
  const tries = search?.tries ?? 0
  useEffect(() => {
    if (!searchId || (status !== 'pending' && status !== 'running')) return
    const timer = setTimeout(async () => {
      // Trop d'essais : on arrête le polling (search ne change plus).
      if (tries >= POLL_MAX_TRIES) {
        setError('La recherche prend trop de temps. Réessayez dans un instant.')
        return
      }
      try {
        const fresh = await getSearch(searchId)
        setSearch({ ...fresh, tries: tries + 1 })
      } catch (e) {
        setError(e.message)
      }
    }, POLL_INTERVAL_MS)
    return () => clearTimeout(timer)
  }, [searchId, status, tries])

  // Envoi du formulaire.
  const handleSubmit = async (payload) => {
    setError(null)
    setSubmitting(true)
    try {
      const created = await createSearch(payload) // {id, candidate_id, status}
      setCriteria({ region: payload.region, contract_types: payload.contract_types })
      setSearch({ ...created, results: null, error_message: null, tries: 0 })
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const running = status === 'pending' || status === 'running'
  const offers = search?.results?.offers ?? []

  // Résumé des critères, affiché au-dessus des résultats.
  const criteriaLabels = criteria
    ? [
        criteria.region ?? 'Toute la France',
        ...(criteria.contract_types.length
          ? criteria.contract_types.map((c) => CONTRACT_LABELS[c])
          : ['Tous contrats']),
      ]
    : []

  return (
    <>
      <Header />

      <Container size="xl" py="xl">
        <Grid gutter="xl">
          {/* Colonne de gauche : le formulaire */}
          <Grid.Col span={{ base: 12, md: 5 }}>
            <div className="sticky-form">
              <SearchForm
                regions={regions}
                loading={submitting || running}
                onSubmit={handleSubmit}
              />
            </div>
          </Grid.Col>

          {/* Colonne de droite : avancement et résultats */}
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="md">
              {error && (
                <Alert
                  color="red"
                  variant="light"
                  title="Erreur"
                  withCloseButton
                  onClose={() => setError(null)}
                >
                  {error}
                </Alert>
              )}

              {!search && <HowItWorks />}

              {search && <StatusSteps search={search} />}

              {/* Pendant la recherche : des cartes « fantômes » animées */}
              {running && [1, 2, 3].map((i) => <OfferSkeleton key={i} />)}

              {status === 'done' && (
                <>
                  <Group justify="space-between" align="center" mt="xs">
                    <Text fw={700} size="lg">
                      {offers.length > 0
                        ? `${offers.length} offres trouvées`
                        : 'Aucune offre ne correspond à ces critères.'}
                    </Text>
                    <Group gap={6}>
                      {criteriaLabels.map((label) => (
                        <Badge key={label} variant="light" color="gray" size="sm">
                          {label}
                        </Badge>
                      ))}
                    </Group>
                  </Group>
                  {offers.map((offer, i) => (
                    <OfferCard
                      key={offer.id}
                      offer={offer}
                      position={i + 1}
                      criteria={criteria}
                    />
                  ))}
                </>
              )}
            </Stack>
          </Grid.Col>
        </Grid>

        <Text size="xs" c="dimmed" ta="center" mt={48}>
          Offres d&apos;emploi fournies par{' '}
          <Anchor href="https://www.adzuna.fr" target="_blank" rel="noopener noreferrer" inherit>
            Adzuna
          </Anchor>{' '}
          · TalentGraph, projet BigData / NoSQL (ENSIIE)
        </Text>
      </Container>
    </>
  )
}
