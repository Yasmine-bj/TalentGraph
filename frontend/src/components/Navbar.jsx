// src/components/Navbar.jsx — barre du haut : logo à gauche, bouton d'action à droite.
import { Link } from 'react-router'
import { Group, Box, Text, Button, Container } from '@mantine/core'

export default function Navbar() {
  return (
    <Container size={1200} py="lg">
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

        {/* component={Link} : un bouton Mantine qui se comporte comme un lien du routeur */}
        <Button component={Link} to="/recherche" radius="xl">
          Commencer
        </Button>
      </Group>
    </Container>
  )
}
