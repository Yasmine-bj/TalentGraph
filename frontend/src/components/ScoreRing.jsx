// src/components/ScoreRing.jsx — l'anneau de pourcentage de compatibilité.
//
// Technique : conic-gradient = dégradé "en camembert" autour du centre.
// On colore de 0 à percent %, puis gris clair jusqu'à 100 %. Un disque blanc
// posé au centre cache le milieu : il ne reste qu'un anneau.
// Utilisé sur l'accueil (aperçu) et sur chaque carte d'offre des résultats.
import { Box, Text } from '@mantine/core'

// Seuil de couleur (comme la maquette) : violet si bonne compatibilité, corail sinon.
const GOOD_MATCH = 70

//   percent : 0 à 100
//   size    : diamètre en pixels
//   label   : petit texte facultatif sous le pourcentage (ex. "compatible")
export default function ScoreRing({ percent, size = 64, label }) {
  const color = percent >= GOOD_MATCH ? '#5B3DF5' : '#FF6B4A'
  const inner = size - 14 // diamètre du disque blanc → épaisseur de l'anneau = 7 px

  return (
    <Box
      w={size}
      h={size}
      // role="img" + aria-label : un lecteur d'écran lit "Compatibilité : 78 %"
      role="img"
      aria-label={`Compatibilité : ${percent} %`}
      style={{
        flexShrink: 0, // ne jamais être écrasé par un titre long à côté
        borderRadius: '50%',
        background: `conic-gradient(${color} 0 ${percent}%, #ECE9FB ${percent}% 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box
        w={inner}
        h={inner}
        bg="white"
        style={{
          borderRadius: '50%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          lineHeight: 1.1,
        }}
      >
        <Text fw={700} fz={size >= 72 ? 18 : 15}>{percent} %</Text>
        {label && <Text fz={10} c="#5A5778">{label}</Text>}
      </Box>
    </Box>
  )
}
