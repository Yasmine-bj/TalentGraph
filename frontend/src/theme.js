// src/theme.js — le "thème" Mantine : couleurs, polices, arrondis.
// Tous les composants Mantine (Button, Card, Badge…) lisent ce thème,
// donc on définit le style UNE fois ici au lieu de le répéter partout.
import { createTheme } from '@mantine/core'

// Mantine attend chaque couleur sous forme de 10 nuances (de la plus claire [0]
// à la plus foncée [9]). La nuance [6] est celle utilisée par défaut.
const violet = [
  '#F0EDFF', '#E2DCFE', '#C4B8FC', '#A493FA', '#8870F8',
  '#7259F7', '#5B3DF5', '#4A2EE0', '#3F24C9', '#2F1A99',
] // [6] = #5B3DF5, le violet principal des maquettes

const coral = [
  '#FFF0EC', '#FFDDD5', '#FFBBAB', '#FF9880', '#FF7F62',
  '#FF7354', '#FF6B4A', '#E5563A', '#C94430', '#9E3322',
] // [6] = #FF6B4A, la couleur d'accent

const mint = [
  '#E6F6F2', '#C6EBE2', '#8FD6C5', '#57C0A7', '#2DAC8E',
  '#169C7F', '#0E8F74', '#0B7A63', '#086653', '#054A3C',
] // [6] = #0E8F74, utilisé pour "validé / compatible"

export const theme = createTheme({
  colors: { violet, coral, mint },
  primaryColor: 'violet',          // couleur des boutons, liens, focus… par défaut

  fontFamily: 'Inter, system-ui, sans-serif',
  headings: {
    fontFamily: "'Space Grotesk', Inter, sans-serif",
    fontWeight: '700',
  },

  defaultRadius: 'lg',             // coins bien arrondis, comme sur les maquettes
  black: '#1B1640',                // couleur du texte ("ink")
})

// Couleurs "brutes" réutilisées hors composants Mantine (fond de page, etc.)
export const COLORS = {
  ink: '#1B1640',
  muted: '#4A4766',
  background: '#F6F5FD',
}
