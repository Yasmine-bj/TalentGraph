// Choix du mode : 4 cartes cliquables. Les modes pas encore disponibles
// (agents IA, M5) sont affichés mais désactivés, avec un badge « Bientôt ».
import { Badge, Group, SimpleGrid, Text, UnstyledButton } from '@mantine/core'
import { MODES } from '../constants'

export default function ModePicker({ value, onChange }) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="xs">
      {MODES.map((mode) => {
        const selected = value === mode.value
        return (
          <UnstyledButton
            key={mode.value}
            disabled={!mode.available}
            onClick={() => onChange(mode.value)}
            aria-pressed={selected}
            style={(theme) => ({
              padding: theme.spacing.sm,
              borderRadius: theme.radius.md,
              border: `1px solid ${
                selected ? theme.colors.indigo[6] : theme.colors.gray[3]
              }`,
              background: selected ? theme.colors.indigo[0] : 'white',
              opacity: mode.available ? 1 : 0.6,
              cursor: mode.available ? 'pointer' : 'not-allowed',
              transition: 'border-color 120ms, background 120ms',
            })}
          >
            <Group justify="space-between" gap={4} wrap="nowrap">
              <Text fw={600} size="sm">
                {mode.label}
              </Text>
              {!mode.available && (
                <Badge size="xs" variant="light" color="gray" style={{ flexShrink: 0 }}>
                  Bientôt
                </Badge>
              )}
            </Group>
            <Text size="xs" c="dimmed" mt={4}>
              {mode.description}
            </Text>
          </UnstyledButton>
        )
      })}
    </SimpleGrid>
  )
}
