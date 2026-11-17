// src/components/Footer.jsx — pied de page : mention projet + attribution des données.
import { Container, Group, Text, Anchor } from '@mantine/core'

export default function Footer() {
  return (
    // w="100%" : même raison que dans Navbar.jsx
    <Container size={1200} pb={40} pt="md" w="100%">
      {/* justify="space-between" : un texte à gauche, l'autre à droite
          (ils passent l'un sous l'autre sur petit écran grâce à wrap) */}
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Text size="sm" c="#5A5778">
          TalentGraph · projet ENSIIE
        </Text>
        <Text size="sm" c="#5A5778">
          {/* L'attribution d'Adzuna est OBLIGATOIRE dans leurs conditions d'utilisation de l'API */}
          Offres d'emploi fournies par{' '}
          <Anchor href="https://www.adzuna.fr" target="_blank" rel="noreferrer" size="sm">
            Adzuna
          </Anchor>
        </Text>
      </Group>
    </Container>
  )
}
