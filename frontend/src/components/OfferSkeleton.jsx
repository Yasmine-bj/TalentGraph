// OfferSkeleton.jsx — Cartes « fantômes » animées pendant la recherche :
// la page montre que quelque chose se prépare, à la place des futures offres.
import { Card, Group, Skeleton, Stack } from '@mantine/core'

export default function OfferSkeleton() {
  return (
    <Card withBorder radius="lg" padding="lg">
      <Stack gap={10}>
        <Skeleton height={16} width="70%" radius="sm" />
        <Skeleton height={12} width="40%" radius="sm" />
        <Group gap={6}>
          <Skeleton height={18} width={80} radius="xl" />
          <Skeleton height={18} width={110} radius="xl" />
        </Group>
      </Stack>
    </Card>
  )
}
