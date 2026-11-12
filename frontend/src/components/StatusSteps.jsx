// =============================================================================
// StatusSteps.jsx — L'avancement de la demande, en direct.
//
// Le statut vient de GET /api/searches/{id}, relu chaque seconde (polling) :
//   pending -> running -> done (ou failed)
// Chaque étape rappelle quelle base de données travaille : utile pour la démo.
// =============================================================================

import { Alert, Code, Paper, Stepper, Text } from '@mantine/core'

// Index de l'étape active du Stepper pour chaque statut.
const ACTIVE_STEP = { pending: 1, running: 1, done: 3, failed: 1 }

export default function StatusSteps({ search }) {
  const { id, status, error_message: errorMessage } = search
  const failed = status === 'failed'

  return (
    <Paper withBorder p="md" radius="lg">
      <Text size="sm" mb="sm">
        Demande <b>n° {id}</b> · vérifiable dans Redis avec{' '}
        <Code>HGETALL search:{id}</Code>
      </Text>

      <Stepper
        active={ACTIVE_STEP[status] ?? 0}
        color={failed ? 'red' : 'indigo'}
        size="sm"
        allowNextStepsSelect={false}
      >
        <Stepper.Step label="Enregistrée" description="PostgreSQL + Redis" />
        <Stepper.Step
          label="Recherche"
          description="Elasticsearch (mots + sens)"
          loading={status === 'pending' || status === 'running'}
        />
        <Stepper.Step label="Résultats" description="Enregistrés dans PostgreSQL" />
      </Stepper>

      {failed && (
        <Alert color="red" variant="light" mt="md" title="La demande n'a pas abouti">
          {errorMessage || 'Erreur inconnue.'}
        </Alert>
      )}
    </Paper>
  )
}
