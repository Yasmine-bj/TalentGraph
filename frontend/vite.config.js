// =============================================================================
// vite.config.js — Configuration de Vite (l'outil de construction du frontend)
//
// Vite a deux rôles :
//   - npm run dev   : serveur de DÉVELOPPEMENT (http://localhost:5173), qui
//                     traduit le JSX à la volée et recharge la page à chaque
//                     sauvegarde ;
//   - npm run build : construit les fichiers de PRODUCTION (dossier dist/),
//                     servis ensuite par nginx dans le conteneur frontend.
// =============================================================================

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // Plugin React : traduit le JSX (<Composant />) en JavaScript normal.
  plugins: [react()],

  server: {
    // PROXY (développement seulement) : les appels de la page vers /api/...
    // sont TRANSMIS à notre API, qui tourne dans Docker sur le port 8000.
    //   navigateur -> localhost:5173/api/searches -> localhost:8000/api/searches
    // Pour le navigateur, la page et l'API ont la MÊME adresse : pas de
    // blocage CORS. En production, c'est nginx qui joue ce rôle (nginx.conf).
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
