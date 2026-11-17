// src/pages/ResultsPage.jsx — squelette provisoire (le vrai contenu arrive dans une prochaine étape).
import { useParams } from 'react-router'
import { Container, Title } from '@mantine/core'

export default function ResultsPage() {
  // useParams lit la partie variable de l'URL : /resultats/42 → { id: '42' }
  const { id } = useParams()
  return (
    <Container size={1200} py="xl">
      <Title order={1}>Résultats de la recherche n°{id}</Title>
    </Container>
  )
}
