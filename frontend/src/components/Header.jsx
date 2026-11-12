// =============================================================================
// Header.jsx — Bandeau du haut + introduction de la page.
// =============================================================================

import { Badge, Box, Container, Group, Stack, Text, ThemeIcon, Title } from '@mantine/core'

// Les technologies, avec leur rôle (affiché au survol... et utile à la démo).
const STACK = [
  { name: 'PostgreSQL', color: 'blue' },
  { name: 'Redis', color: 'red' },
  { name: 'Elasticsearch', color: 'yellow' },
  { name: 'FastAPI', color: 'teal' },
  { name: 'React', color: 'cyan' },
]

export default function Header() {
  return (
    <Box
      component="header"
      style={{
        background: 'linear-gradient(120deg, #312e81 0%, #4338ca 45%, #0e7490 100%)',
        color: 'white',
      }}
    >
      <Container size="xl" py={28}>
        <Group justify="space-between" align="flex-end" gap="lg">
          <Group gap="md" wrap="nowrap">
            {/* Logo : les initiales dans une pastille */}
            <ThemeIcon
              size={52}
              radius="lg"
              variant="white"
              color="indigo"
              style={{ fontWeight: 800, fontSize: 20 }}
            >
              TG
            </ThemeIcon>
            <Stack gap={2}>
              <Title order={1} fz={{ base: 28, sm: 34 }} c="white" lh={1.1}>
                TalentGraph
              </Title>
              <Text size="md" c="indigo.1">
                Copilote carrière : de votre CV aux offres d&apos;emploi réelles.
              </Text>
            </Stack>
          </Group>

          <Group gap={6}>
            {STACK.map((tech) => (
              <Badge
                key={tech.name}
                variant="white"
                color={tech.color}
                radius="sm"
                size="sm"
              >
                {tech.name}
              </Badge>
            ))}
          </Group>
        </Group>
      </Container>
    </Box>
  )
}
