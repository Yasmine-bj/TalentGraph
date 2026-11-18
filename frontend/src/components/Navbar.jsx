// src/components/Navbar.jsx — barre du haut : logo à gauche, liens + bouton à droite.
import { Link } from 'react-router'
import { Group, Box, Text, Button, Container, Anchor, Popover } from '@mantine/core'

export default function Navbar() {
  return (
    // w="100%" : dans le parent en "flex column" (App.jsx), un Container centré par
    // des marges auto se rétrécirait à la taille de son contenu ; on force la pleine largeur.
    <Container size={1200} py="lg" w="100%">
      <Group justify="space-between">
        {/* <Link> change de page SANS recharger le navigateur (contrairement à <a href>) */}
        <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Group gap={10}>
            {/* Le carré violet "TG" des maquettes */}
            <Box
              w={40}
              h={40}
              bg="violet.6"
              c="white"
              style={{
                borderRadius: 12,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 700,
                fontSize: 17,
              }}
            >
              TG
            </Box>
            <Text ff="'Space Grotesk', sans-serif" fw={700} fz={22}>
              TalentGraph
            </Text>
          </Group>
        </Link>

        <Group gap="xl">
          {/* Liens vers les sections de l'accueil. "/#fonctionnalites" = page d'accueil,
              puis le navigateur descend jusqu'à l'élément qui a id="fonctionnalites".
              visibleFrom="sm" : masqués sur les petits écrans (téléphone) pour gagner de la place. */}
          <Anchor href="/#fonctionnalites" c="inherit" fw={500} underline="never" visibleFrom="sm">
            Fonctionnalités
          </Anchor>
          <Anchor href="/#comment" c="inherit" fw={500} underline="never" visibleFrom="sm">
            Comment ça marche
          </Anchor>

          {/* "Se connecter" : les comptes ne sont pas encore codés (prévu après le M7).
              Popover = petite bulle qui s'ouvre au clic, sous le bouton, pour le dire
              clairement : un bouton qui ne réagit pas du tout paraîtrait cassé. */}
          <Popover width={240} position="bottom-end" shadow="md" radius="lg" withArrow>
            <Popover.Target>
              <Button variant="subtle" color="#1B1640" fw={500} size="md" px={8}>
                Se connecter
              </Button>
            </Popover.Target>
            <Popover.Dropdown>
              <Text fw={700} size="sm">Bientôt disponible</Text>
              <Text size="sm" c="dimmed">
                Les comptes arrivent bientôt. En attendant, la recherche est libre, sans inscription.
              </Text>
            </Popover.Dropdown>
          </Popover>

          {/* component={Link} : un bouton Mantine qui se comporte comme un lien du routeur.
              color="#1B1640" ("ink") : bouton foncé comme sur la maquette. */}
          <Button component={Link} to="/recherche" radius="xl" color="#1B1640" size="md">
            Commencer
          </Button>
        </Group>
      </Group>
    </Container>
  )
}
