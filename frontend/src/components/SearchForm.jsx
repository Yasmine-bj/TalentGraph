// =============================================================================
// SearchForm.jsx — Le formulaire : profil (nom, email, CV) et critères.
//
// Le formulaire ne fait PAS les appels à l'API : il vérifie les champs, puis
// donne les données à App (onSubmit), qui envoie la demande.
// =============================================================================

import { useState } from 'react'
import {
  Button,
  Chip,
  Divider,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core'
import ModePicker from './ModePicker'
import { CONTRACTS, EXAMPLE } from '../constants'

const EMPTY = {
  full_name: '',
  email: '',
  cv_text: '',
  mode: 'offers',
  job_title: '',
  region: null,
  contract_types: [],
  salary_min: '',
}

const CV_MIN = 50 // mêmes limites que l'API (schemas.py)
const CV_MAX = 20000

// Vérifications côté navigateur : un message immédiat, avant tout appel.
// (L'API refait ces vérifications : le navigateur peut être contourné.)
function validate(values) {
  const errors = {}
  if (!values.full_name.trim()) errors.full_name = 'Indiquez votre nom.'
  if (!/^\S+@\S+\.\S+$/.test(values.email)) errors.email = 'Email invalide.'
  const cvLength = values.cv_text.trim().length
  if (cvLength < CV_MIN) {
    errors.cv_text = `Collez votre CV (au moins ${CV_MIN} caractères, actuellement ${cvLength}).`
  }
  return errors
}

export default function SearchForm({ regions, loading, onSubmit }) {
  // Une seule variable d'état pour tous les champs.
  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState({})

  // Modifie un champ et efface son éventuel message d'erreur.
  const setField = (name, value) => {
    setValues((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: undefined }))
  }

  const handleSubmit = (event) => {
    event.preventDefault() // empêche le rechargement de la page
    const found = validate(values)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    // Mise au format attendu par l'API : champs vides -> null.
    onSubmit({
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      cv_text: values.cv_text.trim(),
      mode: values.mode,
      job_title: values.job_title.trim() || null,
      region: values.region || null,
      contract_types: values.contract_types,
      salary_min: values.salary_min === '' ? null : Number(values.salary_min),
    })
  }

  return (
    <Paper component="form" onSubmit={handleSubmit} withBorder shadow="sm" p="lg" radius="lg">
      <Stack gap="md">
        <Group justify="space-between">
          <Text fw={700}>Votre profil</Text>
          <Button
            variant="subtle"
            size="compact-sm"
            onClick={() => {
              setValues(EXAMPLE)
              setErrors({})
            }}
          >
            Remplir avec un exemple
          </Button>
        </Group>

        <Group grow align="flex-start">
          <TextInput
            label="Nom"
            placeholder="Léa Martin"
            value={values.full_name}
            onChange={(e) => setField('full_name', e.currentTarget.value)}
            error={errors.full_name}
            maxLength={100}
          />
          <TextInput
            label="Email"
            placeholder="lea@example.com"
            value={values.email}
            onChange={(e) => setField('email', e.currentTarget.value)}
            error={errors.email}
          />
        </Group>

        <Textarea
          label="CV"
          description="Collez le texte de votre CV : compétences, expériences, formation."
          placeholder="Étudiante en data : Python, SQL, Spark..."
          autosize
          minRows={5}
          maxRows={12}
          maxLength={CV_MAX}
          value={values.cv_text}
          onChange={(e) => setField('cv_text', e.currentTarget.value)}
          error={errors.cv_text}
        />

        <Divider label="Ce que vous cherchez" labelPosition="left" />

        <ModePicker value={values.mode} onChange={(mode) => setField('mode', mode)} />

        <TextInput
          label="Métier recherché"
          description="Facultatif : active aussi la recherche par mots-clés."
          placeholder="data engineer"
          value={values.job_title}
          onChange={(e) => setField('job_title', e.currentTarget.value)}
          maxLength={100}
        />

        <Group grow align="flex-start">
          <Select
            label="Région"
            placeholder="Toute la France"
            data={regions}
            searchable
            clearable
            nothingFoundMessage="Aucune région"
            value={values.region}
            onChange={(region) => setField('region', region)}
          />
          <NumberInput
            label="Salaire annuel minimum"
            placeholder="Facultatif"
            suffix=" €"
            thousandSeparator=" "
            min={0}
            step={1000}
            value={values.salary_min}
            onChange={(salary) => setField('salary_min', salary)}
          />
        </Group>

        <div>
          <Text size="sm" fw={500} mb={6}>
            Contrats{' '}
            <Text span size="xs" c="dimmed">
              (aucun = tous)
            </Text>
          </Text>
          <Chip.Group
            multiple
            value={values.contract_types}
            onChange={(contracts) => setField('contract_types', contracts)}
          >
            <Group gap={6}>
              {CONTRACTS.map((c) => (
                <Chip key={c.value} value={c.value} size="sm" variant="light">
                  {c.label}
                </Chip>
              ))}
            </Group>
          </Chip.Group>
        </div>

        <Button type="submit" size="md" loading={loading} fullWidth mt="xs">
          Lancer la recherche
        </Button>
      </Stack>
    </Paper>
  )
}
