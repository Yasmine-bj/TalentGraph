// src/main.jsx — point d'entrée : on "monte" React dans la <div id="root"> d'index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { MantineProvider } from '@mantine/core'

// Feuille de style de base de Mantine : OBLIGATOIRE, sinon les composants s'affichent "nus".
import '@mantine/core/styles.css'

import { theme } from './theme.js'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  // StrictMode : en développement seulement, React vérifie certaines erreurs courantes.
  <StrictMode>
    {/* MantineProvider rend le thème accessible à TOUS les composants en dessous. */}
    <MantineProvider theme={theme}>
      {/* BrowserRouter lit l'URL du navigateur (/, /recherche…) pour savoir quelle page afficher. */}
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </MantineProvider>
  </StrictMode>,
)
