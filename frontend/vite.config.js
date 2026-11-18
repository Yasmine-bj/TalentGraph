// vite.config.js — configuration de Vite (le serveur de développement + l'outil de build)
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Le plugin React permet à Vite de comprendre le JSX et active le rechargement à chaud.
  plugins: [react()],

  server: {
    // Proxy de développement : quand le navigateur appelle /api/... sur localhost:5173,
    // Vite transmet la requête à l'API FastAPI sur localhost:8000.
    // Le navigateur croit parler à une seule origine → pas de problème de CORS.
    // (En production, c'est nginx qui jouera ce rôle.)
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
