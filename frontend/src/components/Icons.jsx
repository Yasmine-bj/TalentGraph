// src/components/Icons.jsx — les petites icônes des maquettes, en SVG.
//
// Un SVG est une image décrite par du code (des traits, des cercles…) : il reste net
// à toutes les tailles et on peut changer sa couleur avec une simple prop.
// Plutôt que d'installer une bibliothèque d'icônes entière pour 7 dessins,
// on les écrit ici une fois et on les réutilise partout.

// Composant de base : le "cadre" commun à toutes nos icônes.
//   size  : largeur/hauteur en pixels
//   color : couleur du trait ('currentColor' = la couleur du texte autour)
//   width : épaisseur du trait
//   children : les formes à dessiner (path, circle…)
function Icon({ size = 24, color = 'currentColor', width = 2, children }) {
  return (
    <svg
      aria-hidden="true" // décoratif : les lecteurs d'écran l'ignorent
      width={size}
      height={size}
      viewBox="0 0 24 24" // système de coordonnées interne : 24 × 24
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  )
}

// "...props" transmet toutes les props reçues (size, color…) au composant Icon.
export const ArrowRightIcon = (props) => (
  <Icon {...props}><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></Icon>
)

export const CheckIcon = (props) => (
  <Icon {...props}><path d="m5 12 5 5 9-10" /></Icon>
)

export const TargetIcon = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" />
  </Icon>
)

export const ChartIcon = (props) => (
  <Icon {...props}><path d="M4 19V5" /><path d="M4 19h16" /><path d="m8 15 4-4 3 3 5-6" /></Icon>
)

export const DocumentCheckIcon = (props) => (
  <Icon {...props}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" /><path d="m9 15 2 2 4-4" />
  </Icon>
)

export const MailIcon = (props) => (
  <Icon {...props}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></Icon>
)

export const SearchIcon = (props) => (
  <Icon {...props}><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>
)

export const UploadIcon = (props) => (
  <Icon {...props}><path d="M12 16V4" /><path d="m6 10 6-6 6 6" /><path d="M4 20h16" /></Icon>
)
