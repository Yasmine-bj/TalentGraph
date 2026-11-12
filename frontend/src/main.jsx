// =============================================================================
// main.jsx — Point d'entrée de l'application React
//
// 1. Importe les styles de Mantine (UNE fois, pour toute l'application).
// 2. Définit le THÈME : couleurs, arrondis, police, partagés par tous les
//    composants -> une interface cohérente.
// 3. "Branche" React dans <div id="root"> (index.html) et y dessine <App />,
//    entouré de <MantineProvider>, qui donne le thème à tous les composants.
// =============================================================================

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider, createTheme } from '@mantine/core'

// Feuille de style de Mantine : sans elle, les composants n'ont aucun style.
import '@mantine/core/styles.css'
// Nos quelques styles globaux (fond de page, survol des cartes...).
import './styles.css'

import App from './App.jsx'

// Le thème de TalentGraph : modifier une valeur ici change TOUTE l'interface.
const theme = createTheme({
  primaryColor: 'indigo',     // couleur principale (boutons, liens, sélection)
  defaultRadius: 'md',        // coins arrondis moyens partout
  fontFamily:
    'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  headings: { fontWeight: '700' },
})

// createRoot(...).render(...) : React prend le contrôle de <div id="root">.
// StrictMode : mode de vérification (développement seulement) qui signale
// les erreurs courantes ; sans effet en production.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="light">
      <App />
    </MantineProvider>
  </StrictMode>,
)
