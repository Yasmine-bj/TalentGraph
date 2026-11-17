// src/App.jsx — la "carte" de l'application : quelle URL affiche quelle page.
import { Routes, Route } from 'react-router'
import { Box } from '@mantine/core'

import Navbar from './components/Navbar.jsx'
import Footer from './components/Footer.jsx'
import HomePage from './pages/HomePage.jsx'
import SearchPage from './pages/SearchPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import { COLORS } from './theme.js'

export default function App() {
  return (
    // Fond lavande sur toute la hauteur de l'écran ; le footer reste en bas.
    <Box
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: COLORS.background,
        color: COLORS.ink,
      }}
    >
      {/* La barre de navigation est affichée sur TOUTES les pages */}
      <Navbar />

      {/* <main> prend toute la place restante (flex: 1) */}
      <Box component="main" style={{ flex: 1 }}>
        {/* <Routes> choisit UNE route selon l'URL actuelle */}
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/recherche" element={<SearchPage />} />
          {/* :id est un paramètre : /resultats/42 → id = "42" (lu avec useParams) */}
          <Route path="/resultats/:id" element={<ResultsPage />} />
          {/* "*" = toute autre URL → on revient à l'accueil */}
          <Route path="*" element={<HomePage />} />
        </Routes>
      </Box>

      <Footer />
    </Box>
  )
}
