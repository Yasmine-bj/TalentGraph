// src/components/OfferCard.jsx — la carte d'UNE offre sur la page résultats.
//
// Contenu (maquette "4 · Résultats") :
//   - l'anneau de compatibilité (match_percent, calculé par l'API au M7) ;
//   - titre, entreprise, lieu, contrat, salaire, date ;
//   - des puces "raisons" (Correspond à vos mots-clés, Dans votre région…) ;
//   - un détail repliable "Pourquoi cette offre ?" : la place de l'offre dans
//     chaque recherche et les points que ça lui rapporte (score_details) ;
//   - le lien vers l'annonce, avec la mention "via Adzuna" (obligatoire).
//
// Les PHRASES sont écrites ici, côté frontend : l'API ne renvoie que des
// nombres (rangs, points). Séparer données et présentation permet de changer
// un texte sans toucher à l'API.
import { useState } from 'react'
import { Anchor, Badge, Box, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'

import { CheckIcon } from './Icons.jsx'
import ScoreRing from './ScoreRing.jsx'

const RRF_K = 60 // même constante que api/app/search.py : points = 1 / (RRF_K + rang)

// Texte affiché pour chaque valeur de contrat de l'API.
export const CONTRACT_LABELS = {
  cdi: 'CDI',
  cdd: 'CDD',
  stage: 'Stage',
  alternance: 'Alternance',
  freelance: 'Freelance',
}

// ---------------------------------------------------------------------------
// Fonctions de mise en forme (nombre → texte en français)
// ---------------------------------------------------------------------------

// 1 → "1ʳᵉ", 30 → "30ᵉ"
function ordinal(rank) {
  return rank === 1 ? '1ʳᵉ' : `${rank}ᵉ`
}

// 0.0164 → "+ 0,016" (3 décimales, virgule française)
function formatPoints(points) {
  return `+ ${points.toFixed(3).replace('.', ',')}`
}

// Le salaire. Adzuna ne dit pas toujours s'il est mensuel ou annuel : on devine
// avec le montant (moins de 10 000 € → c'est forcément par mois).
// toLocaleString('fr-FR') : 35000 → "35 000"
function formatSalary(min, max) {
  if (!min && !max) return null
  const top = max || min
  const unit = top < 10_000 ? '€ / mois' : '€ / an'
  const fmt = (n) => Math.round(n).toLocaleString('fr-FR')
  if (min && max && min !== max) return `${fmt(min)} – ${fmt(max)} ${unit}`
  return `${fmt(top)} ${unit}`
}

// "2026-09-30T…" → "publiée le 30 sept."
function formatDate(isoDate) {
  if (!isoDate) return null
  const date = new Date(isoDate)
  return `publiée le ${date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}`
}

// ['cdi', 'alternance'] → "CDI · Alternance" ; ['inconnu'] → null (contrat non précisé)
function formatContracts(contractTypes) {
  const known = (contractTypes || []).filter((c) => CONTRACT_LABELS[c])
  return known.length ? known.map((c) => CONTRACT_LABELS[c]).join(' · ') : null
}

// ---------------------------------------------------------------------------
// Explications du classement
// ---------------------------------------------------------------------------

// Les puces de raisons, déduites des rangs et des bonus.
// "?." (chaînage optionnel) : si score_details est absent (recherche d'avant
// le M7), on obtient undefined au lieu d'une erreur.
function buildReasons(offer) {
  const reasons = []
  if (offer.rank_bm25) reasons.push('Correspond à vos mots-clés')
  if (offer.rank_knn || offer.rank_exact) reasons.push('Proche de votre parcours')
  if (offer.score_details?.bonus_region) reasons.push('Dans votre région')
  if (offer.score_details?.bonus_contract) reasons.push('Le contrat que vous cherchez')
  return reasons
}

// Les lignes de "Pourquoi cette offre ?" : [phrase, points].
// On commence par la PLACE de l'offre (plus parlant que les points).
function buildScoreLines(offer) {
  const lines = []
  const rankLine = (rank, text) => {
    if (rank) lines.push([`${ordinal(rank)} ${text}`, 1 / (RRF_K + rank)])
  }
  rankLine(offer.rank_bm25, 'pour vos mots-clés')
  rankLine(offer.rank_knn, 'pour la proximité avec votre parcours')
  rankLine(offer.rank_exact, 'parmi les offres qui respectent vos critères')
  if (offer.score_details?.bonus_region) lines.push(['Bonus : votre région', offer.score_details.bonus_region])
  if (offer.score_details?.bonus_contract) lines.push(['Bonus : votre contrat', offer.score_details.bonus_contract])
  return lines
}

// ---------------------------------------------------------------------------
// La carte
// ---------------------------------------------------------------------------

//   offer    : une offre de results.offers (format OfferResult de l'API)
//   position : sa place dans la liste (1, 2, 3…)
export default function OfferCard({ offer, position }) {
  // Chaque carte a SON propre état : ouvrir le détail d'une offre ne touche pas aux autres.
  const [open, setOpen] = useState(false)

  const place = [offer.city, offer.region].filter(Boolean).join(', ') // retire les valeurs vides
  const contract = formatContracts(offer.contract_types)
  const salary = formatSalary(offer.salary_min, offer.salary_max)
  const date = formatDate(offer.published_at)
  const reasons = buildReasons(offer)
  const hasPercent = offer.match_percent != null // != null : ni null ni undefined

  return (
    <Paper component="article" p={24} radius={24} style={{ boxShadow: '0 6px 24px rgba(27,22,64,0.06)' }}>
      <Stack gap={16}>
        {/* En-tête : anneau + informations principales */}
        <Group align="flex-start" wrap="nowrap" gap={18}>
          {hasPercent && <ScoreRing percent={offer.match_percent} size={80} label="compatible" />}

          <Stack gap={6} style={{ flex: 1, minWidth: 0 }}>
            <Group justify="space-between" align="flex-start" wrap="nowrap" gap={8}>
              <Title order={2} fz={20} lh={1.25}>{offer.title}</Title>
              <Text size="sm" c="#6E6B88" fw={600} style={{ flexShrink: 0 }}>n° {position}</Text>
            </Group>
            <Text size="sm" c="#5A5778">
              {[offer.company, place].filter(Boolean).join(' · ') || 'Entreprise non précisée'}
            </Text>
            <Group gap={8} mt={4}>
              {contract
                ? <Badge radius="xl" tt="none" size="lg">{contract}</Badge>
                : <Badge radius="xl" tt="none" size="lg" variant="outline" color="gray">Contrat non précisé</Badge>}
              {salary && <Badge radius="xl" tt="none" size="lg" variant="light" color="mint">{salary}</Badge>}
              {date && <Text size="sm" c="#6E6B88">{date}</Text>}
            </Group>
          </Stack>
        </Group>

        {/* Puces de raisons */}
        {reasons.length > 0 && (
          <Group gap={8}>
            {reasons.map((reason) => (
              <Group key={reason} gap={6} px={12} py={7} bg="#F4F1FF" c="#3F24C9" style={{ borderRadius: 999 }}>
                <CheckIcon size={14} width={3} />
                <Text size="sm" fw={600}>{reason}</Text>
              </Group>
            ))}
          </Group>
        )}

        {/* Détail repliable : affiché seulement si open vaut true */}
        {open && <ScoreBreakdown offer={offer} />}

        {/* Pied de carte */}
        <Group justify="space-between" gap={12}>
          <Button variant="subtle" radius="xl" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Masquer le détail' : 'Pourquoi cette offre ?'}
          </Button>
          <Group gap={12}>
            <Text size="sm" c="#6E6B88">
              via <Anchor href="https://www.adzuna.fr" target="_blank" rel="noreferrer" size="sm">Adzuna</Anchor>
            </Text>
            {offer.url && (
              // target="_blank" : ouvre l'annonce dans un nouvel onglet (on garde nos résultats)
              <Button component="a" href={offer.url} target="_blank" rel="noreferrer" radius="xl" color="#1B1640">
                Voir l'offre
              </Button>
            )}
          </Group>
        </Group>
      </Stack>
    </Paper>
  )
}

// Le tableau "Pourquoi cette offre ?".
function ScoreBreakdown({ offer }) {
  const lines = buildScoreLines(offer)
  return (
    <Box p={18} bg="#F6F5FD" style={{ borderRadius: 18 }}>
      <Text fw={700}>Pourquoi cette offre ?</Text>
      <Text size="sm" c="#5A5778" mb={12}>Sa place dans chaque recherche, et les points qu'elle rapporte</Text>
      <Stack gap={8}>
        {lines.map(([label, points]) => (
          <Group key={label} justify="space-between" wrap="nowrap" gap={12}>
            <Text size="sm">{label}</Text>
            <Text size="sm" fw={600} ff="monospace" style={{ flexShrink: 0 }}>{formatPoints(points)}</Text>
          </Group>
        ))}
        <Group justify="space-between" pt={10} mt={2} style={{ borderTop: '1px solid #E2DEF3' }}>
          <Text fw={700}>Score final</Text>
          <Text fw={700} ff="monospace">
            {offer.score.toFixed(3).replace('.', ',')}
            {offer.match_percent != null && ` · ${offer.match_percent} %`}
          </Text>
        </Group>
      </Stack>
    </Box>
  )
}
