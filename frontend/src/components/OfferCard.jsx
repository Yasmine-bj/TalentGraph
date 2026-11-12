// =============================================================================
// OfferCard.jsx — Une offre trouvée par la recherche hybride.
//
// - Un liseré coloré + un badge « Vos critères » quand l'offre respecte
//   EXPLICITEMENT la région et les contrats demandés.
// - « Trouvée par » : QUELLES recherches l'ont trouvée (rank_bm25,
//   rank_knn, rank_exact) : c'est ce qui rend le classement compréhensible.
// - Mention « Adzuna » avec un lien : exigée par les conditions d'utilisation
//   de l'API Adzuna (source des offres).
// =============================================================================

import { Anchor, Badge, Card, Group, Stack, Text, Tooltip } from '@mantine/core'
import { CONTRACT_LABELS } from '../constants'

const euros = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

function formatSalary(min, max) {
  if (min == null && max == null) return null
  if (min != null && max != null && min !== max) {
    return `${euros.format(min)} – ${euros.format(max)} €`
  }
  return `${euros.format(min ?? max)} €`
}

function formatDate(value) {
  if (!value) return null
  return new Date(value).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

// Les recherches qui ont trouvé l'offre, avec leur rang.
function foundBy(offer) {
  const found = []
  if (offer.rank_bm25 != null)
    found.push({ label: 'mots-clés', rank: offer.rank_bm25, color: 'orange' })
  if (offer.rank_knn != null)
    found.push({ label: 'sens', rank: offer.rank_knn, color: 'teal' })
  if (offer.rank_exact != null)
    found.push({ label: 'critères exacts', rank: offer.rank_exact, color: 'indigo' })
  return found
}

// L'offre respecte-t-elle explicitement les critères de la demande ?
// (même règle que les bonus de l'API : région exacte, contrat en commun)
function matchesCriteria(offer, criteria) {
  if (!criteria) return false
  const { region, contract_types: contracts = [] } = criteria
  if (!region && contracts.length === 0) return false
  const regionOk = !region || offer.region === region
  const contractOk =
    contracts.length === 0 || offer.contract_types.some((c) => contracts.includes(c))
  return regionOk && contractOk
}

export default function OfferCard({ offer, position, criteria }) {
  const location = [offer.city, offer.region].filter(Boolean).join(', ')
  const salary = formatSalary(offer.salary_min, offer.salary_max)
  const date = formatDate(offer.published_at)
  const match = matchesCriteria(offer, criteria)

  return (
    <Card
      withBorder
      radius="lg"
      padding="lg"
      className="offer-card"
      style={{
        borderLeft: `4px solid var(--mantine-color-${match ? 'indigo-6' : 'gray-3'})`,
      }}
    >
      <Stack gap={10}>
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
          <Group gap="sm" align="flex-start" wrap="nowrap">
            <Text fw={800} c="indigo.6" size="lg" lh={1.3} style={{ minWidth: 26 }}>
              {position}
            </Text>
            <div>
              <Text fw={700} size="md" lh={1.3}>
                {offer.title}
              </Text>
              <Text size="sm" c="dimmed" mt={2}>
                {[offer.company, location || 'Lieu non précisé'].filter(Boolean).join(' · ')}
              </Text>
            </div>
          </Group>
          <Stack gap={4} align="flex-end" style={{ flexShrink: 0 }}>
            {match && (
              <Badge color="indigo" variant="light" size="sm">
                ✓ Vos critères
              </Badge>
            )}
            <Tooltip label="Score final : fusion RRF des recherches + bonus des critères">
              <Text size="xs" c="dimmed">
                score {offer.score.toFixed(3)}
              </Text>
            </Tooltip>
          </Stack>
        </Group>

        <Group gap={6} pl={38}>
          {offer.contract_types.map((c) => (
            <Badge
              key={c}
              variant={c === 'inconnu' ? 'outline' : 'filled'}
              color={c === 'inconnu' ? 'gray' : 'indigo'}
              size="sm"
            >
              {CONTRACT_LABELS[c] ?? c}
            </Badge>
          ))}
          {salary && (
            <Badge variant="light" color="green" size="sm">
              {salary}
            </Badge>
          )}
          {date && (
            <Text size="xs" c="dimmed">
              · publiée le {date}
            </Text>
          )}
        </Group>

        <Group justify="space-between" align="center" gap="xs" pl={38}>
          <Group gap={4}>
            <Text size="xs" c="dimmed">
              Trouvée par
            </Text>
            {foundBy(offer).map((f) => (
              <Tooltip key={f.label} label={`Rang ${f.rank} dans cette recherche`}>
                <Badge variant="dot" color={f.color} size="sm">
                  {f.label}
                </Badge>
              </Tooltip>
            ))}
          </Group>
          <Group gap={10}>
            {offer.url && (
              <Anchor href={offer.url} target="_blank" rel="noopener noreferrer" size="sm" fw={600}>
                Voir l&apos;offre ↗
              </Anchor>
            )}
            <Anchor href="https://www.adzuna.fr" target="_blank" rel="noopener noreferrer" size="xs" c="dimmed">
              via Adzuna
            </Anchor>
          </Group>
        </Group>
      </Stack>
    </Card>
  )
}
