// =============================================================================
// HowItWorks.jsx — Affiché avant la première recherche : les 3 étapes, et le
// rôle de chaque base de données (utile pour comprendre... et pour la démo).
// =============================================================================

import { Paper, SimpleGrid, Stack, Text, ThemeIcon, Title } from '@mantine/core'

const STEPS = [
  {
    number: 1,
    color: 'blue',
    title: 'Votre demande est enregistrée',
    text: 'PostgreSQL garde votre profil et votre demande (la source de vérité). Redis suit son avancement en direct.',
  },
  {
    number: 2,
    color: 'yellow',
    title: 'Elasticsearch cherche les offres',
    text: 'Deux recherches combinées : par mots-clés (BM25) et par le sens de votre CV (embeddings, recherche kNN).',
  },
  {
    number: 3,
    color: 'teal',
    title: 'Les meilleures offres remontent',
    text: 'Les classements sont fusionnés (RRF) ; les offres qui respectent vos critères passent devant.',
  },
]

export default function HowItWorks() {
  return (
    <Paper withBorder p="xl" radius="lg" shadow="xs">
      <Title order={3} mb={4}>
        Comment ça marche ?
      </Title>
      <Text size="sm" c="dimmed" mb="lg">
        Remplissez le formulaire (ou cliquez sur « Remplir avec un exemple »), puis lancez la
        recherche : les résultats s&apos;affichent ici.
      </Text>

      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="lg">
        {STEPS.map((step) => (
          <Stack key={step.number} gap={8}>
            <ThemeIcon size={36} radius="xl" variant="light" color={step.color} fw={700}>
              {step.number}
            </ThemeIcon>
            <Text fw={600} size="sm">
              {step.title}
            </Text>
            <Text size="xs" c="dimmed">
              {step.text}
            </Text>
          </Stack>
        ))}
      </SimpleGrid>
    </Paper>
  )
}
