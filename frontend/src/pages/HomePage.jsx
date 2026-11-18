// src/pages/HomePage.jsx — page d'accueil (maquette "1 · Accueil").
//
// Organisation : 4 sections empilées, chacune dans son propre petit composant
// (Hero, Features, HowItWorks, FinalCall). La page les assemble.
// Les textes répétitifs (4 fonctionnalités, 3 étapes) sont dans des TABLEAUX
// de données, et on les affiche avec .map() : un seul bloc de code JSX
// pour 4 cartes, au lieu de 4 copier-coller.
import { Link } from 'react-router'
import { Badge, Box, Button, Container, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core'

import { ArrowRightIcon, ChartIcon, CheckIcon, DocumentCheckIcon, MailIcon, TargetIcon } from '../components/Icons.jsx'
import ScoreRing from '../components/ScoreRing.jsx' // M7 étape 7 : déplacé dans son propre fichier
import { COLORS } from '../theme.js'

// clamp(min, idéal, max) : taille de police qui s'adapte à la largeur de l'écran
// (vw = % de la largeur de la fenêtre), sans descendre sous min ni dépasser max.
const HERO_TITLE_SIZE = 'clamp(40px, 6vw, 64px)'
const SECTION_TITLE_SIZE = 'clamp(32px, 4vw, 44px)'

// ---------------------------------------------------------------------------
// Données affichées
// ---------------------------------------------------------------------------

// Les chiffres sous le titre principal.
const STATS = [
  { value: '20 000+', label: 'offres réelles chaque jour' },
  { value: '19', label: 'régions couvertes' },
  { value: 'CDI → stage', label: 'tous les contrats' },
]

// Les 4 modes de TalentGraph. Seul "offers" existe aujourd'hui (les autres = M5).
//   Icon       : le COMPOSANT icône (pas encore affiché : on écrira <Icon /> plus bas)
//   bg / iconBg / iconColor / textColor / badgeColor : les couleurs de la carte
const FEATURES = [
  {
    Icon: TargetIcon,
    title: 'Trouvez les offres faites pour vous',
    text: 'Votre CV est comparé aux offres par le sens de votre parcours, pas seulement par mots-clés.',
    available: true,
    bg: '#5B3DF5', iconBg: 'rgba(255,255,255,0.18)', iconColor: '#FFFFFF',
    titleColor: '#FFFFFF', textColor: '#E4DEFF', badgeColor: '#3F24C9',
  },
  {
    Icon: ChartIcon,
    title: 'Identifiez les compétences à développer',
    text: 'Ce que le marché demande et qui manque encore à votre profil.',
    available: false,
    bg: '#FFF1EC', iconBg: '#FFD6CB', iconColor: '#B83A1D',
    titleColor: COLORS.ink, textColor: COLORS.muted, badgeColor: '#8A2C15',
  },
  {
    Icon: DocumentCheckIcon,
    title: 'Boostez votre CV',
    text: 'Des conseils concrets pour adapter votre CV à une offre précise.',
    available: false,
    bg: '#E8FAF5', iconBg: '#C9F2E8', iconColor: '#0B6B57',
    titleColor: COLORS.ink, textColor: COLORS.muted, badgeColor: '#0B6B57',
  },
  {
    Icon: MailIcon,
    title: 'Générez votre lettre de motivation',
    text: "Une lettre personnalisée pour l'offre de votre choix, en quelques secondes.",
    available: false,
    bg: '#FFF7DD', iconBg: '#FFE9A8', iconColor: '#7A5600',
    titleColor: COLORS.ink, textColor: COLORS.muted, badgeColor: '#6A4A00',
  },
]

// Les 3 étapes du parcours, avec la couleur du grand numéro.
const STEPS = [
  { number: '01', color: '#5B3DF5', title: 'Déposez votre CV', text: 'Collez son texte. Il reste modifiable avant la recherche.' },
  { number: '02', color: '#FF6B4A', title: 'Précisez ce que vous cherchez', text: 'Métier, région, type de contrat : tout est facultatif.' },
  { number: '03', color: '#0E8F74', title: 'Découvrez vos offres', text: 'Classées par compatibilité, avec la raison de chaque recommandation.' },
]

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

// Section 1 : le titre principal, le bouton d'action et les chiffres clés.
function Hero() {
  return (
    <Container size={1200} pt={56} pb={72}>
      {/* SimpleGrid : grille de colonnes égales. cols={{ base: 1, md: 2 }} =
          1 colonne sur téléphone, 2 colonnes à partir d'un écran moyen (responsive). */}
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing={48} style={{ alignItems: 'center' }}>
        <Stack gap={24}>
          <Badge size="lg" variant="light" radius="xl" tt="none" style={{ alignSelf: 'flex-start' }}>
            Votre copilote carrière
          </Badge>

          <Title order={1} fz={HERO_TITLE_SIZE} lh={1.02} style={{ letterSpacing: -1.5 }}>
            Trouvez l'offre qui vous{' '}
            <Text span inherit c="violet.6">correspond vraiment</Text>.
          </Title>

          <Text fz={19} lh={1.6} c={COLORS.muted} maw={520}>
            Collez votre CV : TalentGraph le compare à des milliers d'offres réelles et vous montre
            celles qui collent à votre parcours, pas seulement à vos mots-clés.
          </Text>

          <Group gap={12}>
            <Button
              component={Link}
              to="/recherche"
              size="xl"
              radius="xl"
              rightSection={<ArrowRightIcon size={18} width={2.4} />}
            >
              Essayer maintenant
            </Button>
            <Text size="sm" c="#5A5778">Gratuit · sans inscription</Text>
          </Group>

          {/* .map() transforme chaque élément de STATS en un bloc JSX.
              key : identifiant unique exigé par React pour suivre chaque élément d'une liste. */}
          <Group gap={32} pt={8}>
            {STATS.map((stat) => (
              <div key={stat.label}>
                <Text ff="heading" fw={700} fz={32}>{stat.value}</Text>
                <Text size="sm" c="#5A5778">{stat.label}</Text>
              </div>
            ))}
          </Group>
        </Stack>

        <OfferPreview />
      </SimpleGrid>
    </Container>
  )
}

// Illustration à droite du titre : une fausse carte d'offre, comme sur la page résultats.
// Les deux formes colorées derrière sont positionnées en "absolute" dans un parent "relative".
function OfferPreview() {
  return (
    <Box pos="relative" py={24} style={{ display: 'flex', justifyContent: 'center' }}>
      {/* Rond corail et carré menthe décoratifs (aria-hidden : ignorés par les lecteurs d'écran) */}
      <Box aria-hidden pos="absolute" w={380} h={380} right={10} top={0}
        style={{ borderRadius: '50%', background: '#FFD6CB', maxWidth: '90%' }} />
      <Box aria-hidden pos="absolute" w={220} h={220} left={20} bottom={0}
        style={{ borderRadius: 40, background: '#C9F2E8', transform: 'rotate(-12deg)' }} />

      <Stack pos="relative" gap={16} p={24} w="100%" maw={420} bg="white"
        style={{ borderRadius: 24, boxShadow: '0 24px 60px rgba(27,22,64,0.14)' }}>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Text fw={700} fz={18}>Data Engineer · alternance</Text>
            <Text size="sm" c="#5A5778" mt={4}>Entreprise exemple · Massy</Text>
          </div>
          <ScoreRing percent={90} />
        </Group>

        <Group gap={8}>
          <Badge variant="light" radius="xl" tt="none" size="lg">Alternance</Badge>
          <Badge variant="light" color="mint" radius="xl" tt="none" size="lg">Dans votre région</Badge>
        </Group>

        <Stack gap={8}>
          {['Proche de votre parcours', 'Correspond à vos mots-clés'].map((reason) => (
            <Group key={reason} gap={8}>
              <CheckIcon size={16} color="#0E8F74" width={2.6} />
              <Text size="sm" c="#3A3756">{reason}</Text>
            </Group>
          ))}
        </Stack>
      </Stack>
    </Box>
  )
}

// Section 2 : les 4 fonctionnalités (1 disponible, 3 "Bientôt").
function Features() {
  return (
    // id="fonctionnalites" : la cible du lien "Fonctionnalités" de la barre du haut
    <Box id="fonctionnalites" bg="white" py={88}>
      <Container size={1200}>
        <Stack gap={12} maw={640} mb={40}>
          <Title order={2} fz={SECTION_TITLE_SIZE} style={{ letterSpacing: -0.8 }}>
            Tout pour décrocher le bon poste
          </Title>
          <Text fz={18} c={COLORS.muted}>Un seul CV, quatre façons de vous faire avancer.</Text>
        </Stack>

        {/* 1 colonne sur téléphone, 2 sur tablette, 4 sur grand écran */}
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing={20}>
          {FEATURES.map(({ Icon, ...feature }) => (
            <Stack key={feature.title} gap={14} p={28} bg={feature.bg} style={{ borderRadius: 24 }}>
              <Box w={48} h={48} bg={feature.iconBg} style={{
                borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {/* Une variable qui contient un composant s'utilise comme une balise : <Icon /> */}
                <Icon color={feature.iconColor} />
              </Box>
              <Text fw={700} fz={21} c={feature.titleColor}>{feature.title}</Text>
              <Text fz={15} lh={1.6} c={feature.textColor} style={{ flex: 1 }}>{feature.text}</Text>
              <Badge bg="white" c={feature.badgeColor} radius="xl" tt="none" size="lg"
                style={{ alignSelf: 'flex-start' }}>
                {/* Opérateur ternaire : condition ? valeur_si_vrai : valeur_si_faux */}
                {feature.available ? 'Disponible' : 'Bientôt'}
              </Badge>
            </Stack>
          ))}
        </SimpleGrid>
      </Container>
    </Box>
  )
}

// Section 3 : les 3 étapes.
function HowItWorks() {
  return (
    <Container id="comment" size={1200} py={88}>
      <Title order={2} fz={SECTION_TITLE_SIZE} mb={40} style={{ letterSpacing: -0.8 }}>
        Trois étapes, c'est tout
      </Title>
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing={24}>
        {STEPS.map((step) => (
          <Stack key={step.number} gap={12}>
            <Text ff="heading" fw={700} fz={56} lh={1} c={step.color}>{step.number}</Text>
            <Text fw={700} fz={21}>{step.title}</Text>
            <Text lh={1.6} c={COLORS.muted}>{step.text}</Text>
          </Stack>
        ))}
      </SimpleGrid>
    </Container>
  )
}

// Section 4 : le bandeau foncé final avec un dernier bouton.
function FinalCall() {
  return (
    <Container size={1200} pb={88}>
      <Group justify="space-between" gap={24} bg={COLORS.ink} c="white"
        px={{ base: 28, sm: 48 }} py={56} style={{ borderRadius: 32 }}>
        <Stack gap={10} maw={620}>
          <Title order={2} c="white" fz="clamp(28px, 3.5vw, 40px)" style={{ letterSpacing: -0.6 }}>
            Prête à trouver votre prochain poste ?
          </Title>
          <Text fz={17} c="#CFCBEA">Deux minutes suffisent.</Text>
        </Stack>
        {/* size="lg" (et pas "xl") : sur téléphone, le texte tient dans le bouton sans être coupé.
            w responsive : pleine largeur sur téléphone, taille naturelle à partir de "sm". */}
        <Button component={Link} to="/recherche" size="lg" radius="xl" color="coral.6" c={COLORS.ink}
          w={{ base: '100%', sm: 'auto' }}>
          Commencer ma recherche
        </Button>
      </Group>
    </Container>
  )
}

// ---------------------------------------------------------------------------
// La page : on assemble les sections dans l'ordre.
// ---------------------------------------------------------------------------
export default function HomePage() {
  return (
    <>
      {/* <>...</> (Fragment) : regroupe plusieurs éléments sans ajouter de <div> inutile */}
      <Hero />
      <Features />
      <HowItWorks />
      <FinalCall />
    </>
  )
}
