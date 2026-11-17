// src/components/Footer.jsx — pied de page : mention projet + attribution des données.
import { Container, Text } from '@mantine/core'

export default function Footer() {
  return (
    <Container size={1200} py="xl">
      <Text size="sm" c="dimmed" ta="center">
        TalentGraph — projet BigData/NoSQL, ENSIIE 2026 · Offres d'emploi fournies par Adzuna
      </Text>
    </Container>
  )
}
