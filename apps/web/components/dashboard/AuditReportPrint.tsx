import React from 'react'

/**
 * AuditReportPrint — print-only section rendered inside .print-area on the dashboard.
 *
 * Hidden on screen (display:none via .print-only CSS class).
 * When the user clicks "Download PDF" → window.print() → this section becomes visible
 * and all interactive accordions / drawers are replaced by fully-expanded content.
 *
 * Sections:
 *   1. Score Overview (pillars + bars)
 *   2. Signal Breakdown (why each pillar got its score — same data as the "Why this score?" drawer)
 *   3. Recommendations (all expanded — pillar, title, impact, description, full action, URL)
 *   4. Competitor Analysis (comparison table + individual competitor detail)
 *   5. Competitor Weaknesses (themes + strategic opportunity)
 *   6. Citation Gaps (where you're present / missing)
 */

interface Breakdown {
  gbp: number
  reviews: number
  website: number
  local_search: number
  ai_citation: number
}

interface Recommendation {
  pillar: 'gbp' | 'reviews' | 'website' | 'local_search' | 'ai_citation'
  title: string
  description: string
  action: string
  difficulty: 'easy' | 'medium' | 'hard'
  impact: number
  url?: string
}

interface Competitor {
  name: string
  position: number
  score?: number
  rating?: number | null
  reviews?: number | null
  type?: string | null
  city?: string | null
  address?: string | null
  phone?: string | null
  website?: string | null
  cross_border?: boolean
  cross_city?: boolean
  breakdown?: Breakdown
  has_full_data?: boolean
}

interface CompetitorTheme {
  theme: string
  count: number
  example: string
}

interface CompetitorInsights {
  themes: CompetitorTheme[]
  avg_competitor_rating: number | null
  opportunity_summary: string
  competitors_analysed: number
  reviews_analysed: number
}

interface ReputationItem {
  theme?: string
  detail?: string
  source?: string
  example?: string
}

function reputationLabel(item: string | ReputationItem): string {
  if (typeof item === 'string') return item
  return item.theme ?? ''
}

interface OwnReputation {
  strengths: (string | ReputationItem)[]
  weaknesses: (string | ReputationItem)[]
  summary: string
  review_count: number
  avg_rating: number | null
}

interface CitationGaps {
  user?: string[]
  competitors?: Record<string, string[]>
  gaps?: string[]
}

interface RawResults {
  perplexity?: { mentioned: boolean; snippet?: string | null }
  chatgpt?: { mentioned: boolean; snippet?: string | null }
  google?: {
    ai_overview?: { mentioned: boolean; snippet?: string | null }
    local_pack?: { present: boolean; position: number | null }
    organic?: { present: boolean }
    knowledge_graph?: {
      found: boolean
      title?: string | null
      rating?: number | null
      reviews_count?: number | null
      type?: string | null
      website?: string | null
      phone?: string | null
    }
    competitors?: Competitor[]
  }
  website?: { reachable: boolean; has_local_business_schema: boolean; has_faq_schema: boolean }
  recommendations?: Recommendation[]
  competitors?: Competitor[]
  competitor_insights?: CompetitorInsights
  citation_gaps?: CitationGaps
}

interface Audit {
  score: number
  score_breakdown: Breakdown | null
  raw_results: RawResults | null
  created_at: string
}

interface Props {
  audit: Audit
  businessName: string | null
  auditDate: string
  reputation?: OwnReputation | null
  locale?: string
}

// ─── constants ────────────────────────────────────────────────────────────────

const PILLARS: { key: keyof Breakdown; label: string; max: number; description: string }[] = [
  {
    key: 'gbp',
    label: 'Google Business Profile',
    max: 25,
    description:
      'Measures how complete and optimised your Google Business Profile is. A strong GBP means Google can confidently surface your business in Knowledge Graph cards and Maps.',
  },
  {
    key: 'reviews',
    label: 'Reviews & Reputation',
    max: 22,
    description:
      'Volume and quality of reviews directly affect AI engine trust. 50+ reviews at ≥4.5★ earns maximum points. Fewer or lower-rated reviews mean AI engines treat your reputation as unverified.',
  },
  {
    key: 'website',
    label: 'Website & Schema',
    max: 20,
    description:
      'AI crawlers need your site to be reachable (HTTP 200) and marked up with LocalBusiness and FAQPage schema so they can extract structured facts about your business.',
  },
  {
    key: 'local_search',
    label: 'Local Search Presence',
    max: 15,
    description:
      "Appearing in Google's map pack and organic results signals to AI that your business is locally authoritative. Position #1 in the map pack earns full points; not appearing earns zero.",
  },
  {
    key: 'ai_citation',
    label: 'AI Citations',
    max: 18,
    description:
      'Points are awarded when your business is mentioned by name in ChatGPT answers, Perplexity answers, and Google AI Overviews. Each engine is worth 6 points. Being cited by all three is the gold standard.',
  },
]

const PILLAR_LABELS: Record<keyof Breakdown, string> = {
  gbp: 'GBP',
  reviews: 'Reviews',
  website: 'Website',
  local_search: 'Local Search',
  ai_citation: 'AI Citations',
}

const DIFFICULTY_LABELS: Record<Recommendation['difficulty'], string> = {
  easy: '5–10 min',
  medium: '30–60 min',
  hard: 'Multi-week commitment',
}

const DIRECTORY_CLAIM_URLS: Record<string, string> = {
  Yelp: 'https://biz.yelp.com/signup',
  'Yellow Pages': 'https://www.yellowpages.ca/account/register',
  BBB: 'https://www.bbb.org/get-listed',
  TripAdvisor: 'https://www.tripadvisor.com/Owners',
  Facebook: 'https://www.facebook.com/business/pages/set-up',
  Instagram: 'https://business.instagram.com/getting-started',
  LinkedIn: 'https://www.linkedin.com/company/setup/new/',
  Foursquare: 'https://business.foursquare.com/',
  Nextdoor: 'https://business.nextdoor.com/local',
  RateMDs: 'https://www.ratemds.com/profile/claim/',
  Healthgrades: 'https://partner.healthgrades.com/',
  '411.ca': 'https://411.ca/business',
  Canada411: 'https://www.canada411.ca',
  MapQuest: 'https://www.mapquest.com/business',
  Opencare: 'https://www.opencare.com/dentists/join/',
  Zocdoc: 'https://www.zocdoc.com/join',
  'Wellness.com': 'https://www.wellness.com/dir/practitioner_signup.aspx',
  Houzz: 'https://www.houzz.com/proSignup',
  HomeStars: 'https://homestars.com/create-account',
  TrustedPros: 'https://www.trustedpros.ca/contractor',
  Angi: 'https://pro.angi.com/',
  Thumbtack: 'https://www.thumbtack.com/pro/',
  n49: 'https://www.n49.com/biz/claim',
  'Cylex Canada': 'https://www.cylex-canada.ca/add-business.html',
  'Realtor.ca': 'https://www.crea.ca/membership/',
  LawyerLocate: 'https://www.lawyerlocate.ca/lawyers/register',
  OpenTable: 'https://restaurant.opentable.com',
  Reddit: 'https://www.reddit.com/search/?q=',
}

// ─── i18n ─────────────────────────────────────────────────────────────────────

const REPORT_STRINGS = {
  en: {
    scoreLabel: (s: number) =>
      s >= 70 ? 'Strong' : s >= 50 ? 'Moderate' : s >= 30 ? 'Needs work' : 'Critical',
    scoreSummary: (s: number) =>
      s >= 70
        ? 'Your business is well-optimised for AI search. Focus on maintaining this level and pushing for AI citations.'
        : s >= 50
        ? 'You have a solid foundation but meaningful gaps remain. The recommendations below show the fastest paths to improvement.'
        : s >= 30
        ? 'Several core signals are missing. AI engines may not surface your business reliably. Address the high-impact recommendations first.'
        : 'Your business has critical visibility gaps. AI engines are unlikely to recommend you. Start with the easiest wins below.',
    hero: {
      title: 'AEO Readiness Score',
      mapPosition: (pos: number) => `#${pos} on Google Maps results for your category and city`,
      noMapPosition: '⚠ Not currently appearing in Google Maps results for your category and city',
      audited: (date: string) => `Audited: ${date}`,
    },
    sections: {
      scoreBreakdown: 'Score Breakdown by Pillar',
      signalBreakdown: 'Detailed Signal Breakdown — How Each Score Was Calculated',
      competitors: 'Competitor Analysis',
      reputation: 'Your Reputation',
      weaknesses: 'Competitor Weaknesses — Your Strategic Opportunity',
      citations: 'Directory & Citation Gap Analysis',
    },
    pillars: [
      { key: 'gbp' as const, label: 'Google Business Profile', max: 25, description: 'Measures how complete and optimised your Google Business Profile is. A strong GBP means Google can confidently surface your business in Knowledge Graph cards and Maps.' },
      { key: 'reviews' as const, label: 'Reviews & Reputation', max: 22, description: 'Volume and quality of reviews directly affect AI engine trust. 50+ reviews at ≥4.5★ earns maximum points. Fewer or lower-rated reviews mean AI engines treat your reputation as unverified.' },
      { key: 'website' as const, label: 'Website & Schema', max: 20, description: "AI crawlers need your site to be reachable (HTTP 200) and marked up with LocalBusiness and FAQPage schema so they can extract structured facts about your business." },
      { key: 'local_search' as const, label: 'Local Search Presence', max: 15, description: "Appearing in Google's map pack and organic results signals to AI that your business is locally authoritative. Position #1 in the map pack earns full points; not appearing earns zero." },
      { key: 'ai_citation' as const, label: 'AI Citations', max: 18, description: 'Points are awarded when your business is mentioned by name in ChatGPT answers, Perplexity answers, and Google AI Overviews. Each engine is worth 6 points. Being cited by all three is the gold standard.' },
    ],
    gbp: {
      desc: "Google's Knowledge Graph is the structured database that powers AI answers about local businesses. A found, complete profile earns points. Missing details (no category, no phone, no website) all reduce the score.",
      foundRow: 'Found in Knowledge Graph', nameRow: 'Business name on listing', categoryRow: 'Business category',
      ratingRow: 'Star rating', reviewRow: 'Review count', websiteRow: 'Website linked on listing', phoneRow: 'Phone number on listing',
      found: '✓ Yes', notFound: '✗ Not found', na: 'Not available', notSet: 'Not set', notListed: '✗ Not listed',
    },
    reviews: {
      desc: 'Volume: 50+ reviews earns the most points. 10–49 earns partial credit. Fewer than 10 earns zero for volume. Rating: ≥4.5★ earns full rating points; ≥4.0★ earns partial; below 4.0★ earns zero.',
      ratingRow: 'Star rating', countRow: 'Review count', na: 'Not available', noRating: 'No rating',
      count: (n: number) => `${n} reviews`,
      tooFew: 'You have fewer than 10 reviews. Actively requesting reviews from customers is the single fastest way to increase this score. Target: reach 50+ reviews at 4.5★ for full points.',
      needsMore: (n: number) => `You have ${n} reviews. Reaching 50+ at ≥4.5★ will earn the maximum points for this pillar.`,
    },
    website: {
      desc: 'AI crawlers need your website to respond with HTTP 200. Structured data markup (Schema.org JSON-LD) lets search engines extract verified facts about your business without guessing.',
      reachableRow: 'Website reachable (HTTP 200)', lbsRow: 'LocalBusiness schema markup present', faqRow: 'FAQ / HowTo schema markup present',
      yes: 'Yes (HTTP 200)', notReachable: 'Not reachable', detected: '✓ Detected', notFound: '✗ Not found',
      lbsHint: "Adding LocalBusiness JSON-LD to your website's <head> is a one-time change with lasting impact. LeapOne's Content page can generate the exact markup for you — copy and paste it into your site.",
    },
    localSearch: {
      desc: "We ran your audit queries on Google and recorded whether your business appears in the Maps local pack and in organic (web) results. Higher pack position and organic presence both contribute to the score.",
      inPackRow: 'Appears in Google Maps local pack', positionRow: 'Local pack position', organicRow: 'In organic (web) results',
      notInPack: 'Not in pack',
      notInPackHint: "Not in the local pack means customers searching for your category in your city are not seeing you on the map. Improving your Google Business Profile completeness and review count are the primary drivers of local pack ranking.",
    },
    aiCitations: {
      desc: 'We asked ChatGPT, Perplexity, and Google AI Overview for the best businesses of your type in your city. Each engine is worth 6 points. A snippet below confirms the exact text where your business was mentioned.',
      mentioned: 'Mentioned', notMentioned: 'Not mentioned',
      chatgptHint: 'ChatGPT uses training data, not live search. Improvements take 6–12 months to appear as OpenAI re-trains. Focus on Yelp, TripAdvisor, Yellow Pages, and local press mentions to build training-data footprint.',
      perplexityHint: 'Perplexity uses real-time web search. Improvements here can appear within days of publishing fresh content and claiming directory listings.',
    },
    reputation: {
      meta: (n: number, s: string) => `Based on ${n} Google review${s} from the last 3 months`,
      avgRating: (r: number) => `${r}★ avg rating`,
      strengths: '✅ What customers love', weaknesses: '⚠️ What needs attention',
    },
    competitors: {
      intro: (n: number) => `Top ${n} businesses Google ranks alongside you for your category in your city — scored on the same 5-pillar formula. Use this to identify where competitors are stronger and where you have the edge.`,
      you: 'You', diffCountry: '🌍 Diff. country', nearbyCity: (c: string | null | undefined) => `📍 ${c ?? 'Nearby city'}`,
      totalScore: 'Total Score', rating: 'Rating', reviews: 'Reviews', address: 'Address', website: 'Website',
    },
    weaknesses: {
      intro: (r: number, c: number, s: string) => `We analysed ${r} Google Maps reviews across ${c} competitor${s}.`,
      avgRating: (r: number) => ` Average competitor rating: ${r}★.`,
      hint: 'The complaint themes below are where you can win business by doing the opposite.',
      times: (n: number) => `${n}× mentioned`,
      noPatterns: 'No clear complaint patterns found — competitors have generally strong reputations in these reviews.',
      opportunity: '🎯 Strategic opportunity',
    },
    citations: {
      intro: "We scanned Google search results for 28 directories. Being listed where your competitors are — and you're not — is one of the fastest ways to close the AI citation gap.",
      present: '✓ Directories where you already appear',
      gaps: '⚠ Gaps — competitors are listed here, you are not',
      gapsHint: "Each gap below is a listing your competitors have that you're missing. Claiming these directories adds citation signals that AI engines use to verify and recommend local businesses.",
      reddit: 'Search your city subreddit',
      noGaps: '✓ No citation gaps found — you appear on all directories where your competitors appear.',
    },
    footer: {
      generated: (d: string) => `Generated by LeapOne · leapone.ca · ${d}`,
      source: 'Data sourced from SerpApi (Google), Perplexity Sonar, and OpenAI GPT-4o-mini',
    },
  },
  fr: {
    scoreLabel: (s: number) =>
      s >= 70 ? 'Solide' : s >= 50 ? 'Acceptable' : s >= 30 ? 'À améliorer' : 'Critique',
    scoreSummary: (s: number) =>
      s >= 70
        ? "Votre entreprise est bien optimisée pour la recherche IA. Concentrez-vous sur le maintien de ce niveau et visez davantage de citations IA."
        : s >= 50
        ? "Vous avez une bonne base, mais des lacunes importantes subsistent. Les recommandations ci-dessous montrent les chemins les plus rapides vers l'amélioration."
        : s >= 30
        ? "Plusieurs signaux clés sont manquants. Les moteurs IA peuvent ne pas afficher votre entreprise de manière fiable. Commencez par les recommandations à fort impact."
        : "Votre entreprise présente des lacunes de visibilité critiques. Les moteurs IA sont peu susceptibles de vous recommander. Commencez par les gains les plus faciles ci-dessous.",
    hero: {
      title: 'Score de préparation AEO',
      mapPosition: (pos: number) => `N°${pos} dans les résultats Google Maps pour votre catégorie et votre ville`,
      noMapPosition: "⚠ N'apparaît pas actuellement dans les résultats Google Maps pour votre catégorie et votre ville",
      audited: (date: string) => `Audité le : ${date}`,
    },
    sections: {
      scoreBreakdown: 'Répartition du score par pilier',
      signalBreakdown: 'Détail des signaux — Comment chaque score a été calculé',
      competitors: 'Analyse de la concurrence',
      reputation: 'Votre réputation',
      weaknesses: 'Faiblesses des concurrents — Votre opportunité stratégique',
      citations: 'Analyse des lacunes en annuaires et citations',
    },
    pillars: [
      { key: 'gbp' as const, label: 'Google Business Profile', max: 25, description: "Mesure l'exhaustivité et l'optimisation de votre profil Google Business. Un profil GBP solide permet à Google d'afficher votre entreprise avec confiance dans les fiches Knowledge Graph et sur Maps." },
      { key: 'reviews' as const, label: 'Avis & Réputation', max: 22, description: "Le volume et la qualité des avis influencent directement la confiance des moteurs IA. 50+ avis à ≥4,5★ obtient le maximum de points. Moins d'avis ou une note plus faible réduisent la visibilité IA." },
      { key: 'website' as const, label: 'Site Web & Schema', max: 20, description: "Les robots IA ont besoin que votre site réponde en HTTP 200 et soit balisé avec des données structurées LocalBusiness et FAQPage pour extraire des faits vérifiés sur votre entreprise." },
      { key: 'local_search' as const, label: 'Présence locale', max: 15, description: "Apparaître dans le pack local Google (la carte des 3 résultats) et dans les résultats organiques signale aux IA que votre entreprise est une autorité locale. La position 1 dans le pack local obtient le maximum de points." },
      { key: 'ai_citation' as const, label: 'Citations IA', max: 18, description: "Des points sont attribués lorsque votre entreprise est mentionnée par nom dans les réponses ChatGPT, Perplexity et les AI Overviews Google. Chaque moteur vaut 6 points. Être cité par les trois est le meilleur résultat." },
    ],
    gbp: {
      desc: "Le Knowledge Graph de Google est la base de données structurée qui alimente les réponses IA sur les entreprises locales. Un profil trouvé et complet rapporte des points. Les détails manquants (pas de catégorie, pas de téléphone, pas de site web) réduisent le score.",
      foundRow: 'Trouvé dans le Knowledge Graph', nameRow: "Nom de l'entreprise sur la fiche", categoryRow: "Catégorie d'activité",
      ratingRow: 'Note en étoiles', reviewRow: "Nombre d'avis", websiteRow: 'Site web lié à la fiche', phoneRow: 'Numéro de téléphone sur la fiche',
      found: '✓ Oui', notFound: '✗ Non trouvé', na: 'Non disponible', notSet: 'Non défini', notListed: '✗ Non renseigné',
    },
    reviews: {
      desc: "Volume : 50+ avis obtient le plus de points. 10–49 avis obtient du crédit partiel. Moins de 10 avis obtient zéro pour le volume. Note : ≥4,5★ obtient les points complets ; ≥4,0★ obtient du crédit partiel ; en dessous de 4,0★ obtient zéro.",
      ratingRow: 'Note en étoiles', countRow: "Nombre d'avis", na: 'Non disponible', noRating: 'Pas de note',
      count: (n: number) => `${n} avis`,
      tooFew: "Vous avez moins de 10 avis. Demander activement des avis à vos clients est le moyen le plus rapide d'augmenter ce score. Objectif : atteindre 50+ avis à 4,5★ pour le maximum de points.",
      needsMore: (n: number) => `Vous avez ${n} avis. Atteindre 50+ à ≥4,5★ vous donnera le maximum de points pour ce pilier.`,
    },
    website: {
      desc: "Les robots IA ont besoin que votre site réponde en HTTP 200. Le balisage de données structurées (Schema.org JSON-LD) permet aux moteurs de recherche d'extraire des faits vérifiés sur votre entreprise sans avoir à deviner.",
      reachableRow: 'Site web accessible (HTTP 200)', lbsRow: 'Balisage schema LocalBusiness présent', faqRow: 'Balisage schema FAQ/HowTo présent',
      yes: 'Oui (HTTP 200)', notReachable: 'Non accessible', detected: '✓ Détecté', notFound: '✗ Non trouvé',
      lbsHint: "Ajouter un JSON-LD LocalBusiness dans la section head de votre site est une modification ponctuelle avec un impact durable. La page Contenu de LeapOne peut générer le balisage exact pour vous — copiez-collez-le dans votre site.",
    },
    localSearch: {
      desc: "Nous avons exécuté vos requêtes d'audit sur Google et enregistré si votre entreprise apparaît dans le pack local Maps et dans les résultats organiques (web). Une meilleure position dans le pack et une présence organique contribuent toutes deux au score.",
      inPackRow: 'Apparaît dans le pack local Google Maps', positionRow: 'Position dans le pack local', organicRow: 'Dans les résultats organiques (web)',
      notInPack: 'Pas dans le pack',
      notInPackHint: "Ne pas figurer dans le pack local signifie que les clients qui recherchent votre catégorie dans votre ville ne vous voient pas sur la carte. Améliorer l'exhaustivité de votre profil Google Business et votre nombre d'avis sont les principaux leviers du classement dans le pack local.",
    },
    aiCitations: {
      desc: "Nous avons demandé à ChatGPT, Perplexity et Google AI Overview les meilleures entreprises de votre type dans votre ville. Chaque moteur vaut 6 points. Un extrait ci-dessous confirme le texte exact où votre entreprise a été mentionnée.",
      mentioned: 'Mentionné', notMentioned: 'Non mentionné',
      chatgptHint: "ChatGPT utilise des données d'entraînement, pas la recherche en temps réel. Les améliorations prennent 6 à 12 mois pour apparaître au fur et à mesure qu'OpenAI se réentraîne. Concentrez-vous sur Yelp, TripAdvisor, Pages Jaunes et les mentions dans la presse locale pour construire votre empreinte de données d'entraînement.",
      perplexityHint: "Perplexity utilise la recherche web en temps réel. Les améliorations ici peuvent apparaître dans les jours suivant la publication de nouveau contenu et la revendication de fiches d'annuaires.",
    },
    reputation: {
      meta: (n: number, s: string) => `Basé sur ${n} avis Google${s} des 3 derniers mois`,
      avgRating: (r: number) => `${r}★ note moyenne`,
      strengths: '✅ Ce que les clients apprécient', weaknesses: '⚠️ Ce qui nécessite attention',
    },
    competitors: {
      intro: (n: number) => `Les ${n} premières entreprises que Google classe à côté de vous pour votre catégorie dans votre ville — notées selon la même formule à 5 piliers. Utilisez ceci pour identifier où les concurrents sont plus forts et où vous avez l'avantage.`,
      you: 'Vous', diffCountry: '🌍 Autre pays', nearbyCity: (c: string | null | undefined) => `📍 ${c ?? 'Ville proche'}`,
      totalScore: 'Score total', rating: 'Note', reviews: 'Avis', address: 'Adresse', website: 'Site web',
    },
    weaknesses: {
      intro: (r: number, c: number, s: string) => `Nous avons analysé ${r} avis Google Maps sur ${c} concurrent${s}.`,
      avgRating: (r: number) => ` Note moyenne des concurrents : ${r}★.`,
      hint: 'Les thèmes de plaintes ci-dessous sont là où vous pouvez gagner des clients en faisant le contraire.',
      times: (n: number) => `${n}× mentionné`,
      noPatterns: 'Aucun schéma de plainte clair trouvé — les concurrents ont généralement de bonnes réputations dans ces avis.',
      opportunity: '🎯 Opportunité stratégique',
    },
    citations: {
      intro: "Nous avons analysé les résultats Google pour 28 annuaires. Être référencé là où vos concurrents le sont — et pas vous — est l'un des moyens les plus rapides de combler le manque de citations IA.",
      present: '✓ Annuaires où vous apparaissez déjà',
      gaps: '⚠ Lacunes — vos concurrents sont listés ici, pas vous',
      gapsHint: "Chaque lacune ci-dessous est une fiche que vos concurrents ont et que vous n'avez pas. Revendiquer ces annuaires ajoute des signaux de citation que les moteurs IA utilisent pour vérifier et recommander les entreprises locales.",
      reddit: 'Cherchez votre subreddit local',
      noGaps: '✓ Aucune lacune de citation trouvée — vous apparaissez sur tous les annuaires où vos concurrents apparaissent.',
    },
    footer: {
      generated: (d: string) => `Généré par LeapOne · leapone.ca · ${d}`,
      source: 'Données issues de SerpApi (Google), Perplexity Sonar et OpenAI GPT-4o-mini',
    },
  },
} satisfies Record<string, unknown>

// ─── helpers ──────────────────────────────────────────────────────────────────

function boolIcon(val: boolean | undefined | null): string {
  if (val === true) return '✓'
  if (val === false) return '✗'
  return '—'
}

function boolColor(val: boolean | undefined | null): string {
  if (val === true) return '#16a34a'
  if (val === false) return '#dc2626'
  return '#64748b'
}

function pillarBarColor(pct: number): string {
  if (pct >= 75) return '#22c55e'
  if (pct >= 40) return '#f59e0b'
  return '#f87171'
}

// ─── sub-components ───────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{
      fontSize: '13px',
      fontWeight: 800,
      color: '#1e293b',
      borderBottom: '2px solid #4f46e5',
      paddingBottom: '6px',
      marginBottom: '14px',
      marginTop: 0,
    }}>
      {children}
    </h2>
  )
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{
      fontSize: '11px',
      fontWeight: 700,
      color: '#1e293b',
      margin: '0 0 8px 0',
    }}>
      {children}
    </h3>
  )
}

function SignalRow({ label, value, positive }: { label: string; value: string; positive?: boolean | null }) {
  const color = positive === true ? '#16a34a' : positive === false ? '#dc2626' : '#334155'
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      padding: '5px 0',
      borderBottom: '1px solid #f1f5f9',
      gap: '12px',
    }}>
      <span style={{ fontSize: '10px', color: '#64748b', flex: 1 }}>{label}</span>
      <span style={{ fontSize: '10px', fontWeight: 600, color, flexShrink: 0 }}>{value}</span>
    </div>
  )
}

function PillarBar({ label, pts, max, userPts }: { label: string; pts: number; max: number; userPts?: number }) {
  const pct = max === 0 ? 0 : Math.round((pts / max) * 100)
  const color = pillarBarColor(pct)
  const delta = userPts != null ? userPts - pts : null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
      <span style={{ fontSize: '10px', color: '#475569', width: '64px', flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px' }} />
      </div>
      <span style={{ fontSize: '10px', color: '#64748b', width: '32px', textAlign: 'right', flexShrink: 0 }}>
        {pts}/{max}
      </span>
      {delta != null && (
        <span style={{
          fontSize: '9px',
          fontWeight: 700,
          color: delta > 0 ? '#16a34a' : delta < 0 ? '#dc2626' : '#94a3b8',
          width: '40px',
          textAlign: 'right',
          flexShrink: 0,
        }}>
          {delta > 0 ? `you +${delta}` : delta < 0 ? `you ${delta}` : 'tied'}
        </span>
      )}
    </div>
  )
}

function Card({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e2e8f0',
      borderLeft: accent ? `3px solid ${accent}` : '1px solid #e2e8f0',
      borderRadius: '10px',
      padding: '12px 14px',
      marginBottom: '10px',
      pageBreakInside: 'avoid',
    }}>
      {children}
    </div>
  )
}

// ─── main component ───────────────────────────────────────────────────────────

export default function AuditReportPrint({ audit, businessName, auditDate, reputation, locale }: Props) {
  const T = REPORT_STRINGS[locale === 'fr' ? 'fr' : 'en'] as typeof REPORT_STRINGS['en']
  const bd = audit.score_breakdown
  const rr = audit.raw_results
  const kg = rr?.google?.knowledge_graph
  const lp = rr?.google?.local_pack
  const ws = rr?.website
  const perplexity = rr?.perplexity
  const chatgpt = rr?.chatgpt
  const aiOverview = rr?.google?.ai_overview

  // Merge competitor lists (same logic as CompetitorsPage)
  const scoredCompetitors = rr?.competitors ?? []
  const rawCompetitors = rr?.google?.competitors ?? []
  const competitors: Competitor[] = scoredCompetitors.length >= rawCompetitors.length
    ? scoredCompetitors
    : rawCompetitors.map(c => {
        const key = c.name?.trim().toLowerCase() || ''
        const scored = scoredCompetitors.find(
          s => (s.name?.trim().toLowerCase() || '') === key
        )
        return scored ?? c
      })
  const topCompetitors = [...competitors]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 3)

  const insights = rr?.competitor_insights
  const citationGaps = rr?.citation_gaps

  const recommendations: Recommendation[] = (rr?.recommendations ?? [])
    .slice()
    .sort((a, b) => b.impact - a.impact)

  const userPosition: number | null = lp?.present ? (lp.position ?? null) : null

  const scoreColor = audit.score >= 70 ? '#16a34a' : audit.score >= 40 ? '#f59e0b' : '#dc2626'

  return (
    <div className="print-only" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>

      {/* ── PAGE 1: Score Overview + Signal Breakdown ── */}
      <div style={{ pageBreakAfter: 'always' }}>

        {/* Score Hero */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '10px',
          padding: '16px 20px',
          marginBottom: '20px',
        }}>
          <div>
            <div style={{ fontSize: '10px', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
              {T.hero.title}
            </div>
            <div style={{ fontSize: '42px', fontWeight: 900, color: scoreColor, lineHeight: 1 }}>
              {audit.score}
              <span style={{ fontSize: '16px', fontWeight: 600, color: '#94a3b8' }}>/100</span>
            </div>
            <div style={{ fontSize: '11px', fontWeight: 700, color: scoreColor, marginTop: '4px' }}>
              {T.scoreLabel(audit.score)}
            </div>
          </div>
          <div style={{ maxWidth: '380px' }}>
            <p style={{ fontSize: '11px', color: '#475569', lineHeight: 1.6, margin: 0 }}>
              {T.scoreSummary(audit.score)}
            </p>
            {userPosition != null ? (
              <p style={{ fontSize: '10px', fontWeight: 600, color: '#4f46e5', marginTop: '8px' }}>
                {T.hero.mapPosition(userPosition!)}
              </p>
            ) : (
              <p style={{ fontSize: '10px', fontWeight: 600, color: '#dc2626', marginTop: '8px' }}>
                {T.hero.noMapPosition}
              </p>
            )}
            <p style={{ fontSize: '10px', color: '#94a3b8', margin: '6px 0 0' }}>
              {T.hero.audited(auditDate)}
            </p>
          </div>
        </div>

        {/* Pillar Summary */}
        {bd && (
          <div style={{ marginBottom: '24px' }}>
            <SectionHeading>{T.sections.scoreBreakdown}</SectionHeading>
            {T.pillars.map(p => {
              const pct = p.max === 0 ? 0 : Math.round((bd[p.key] / p.max) * 100)
              const color = pillarBarColor(pct)
              return (
                <Card key={p.key}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: '#1e293b' }}>{p.label}</div>
                      <p style={{ fontSize: '10px', color: '#64748b', margin: '3px 0 0', lineHeight: 1.5 }}>{p.description}</p>
                    </div>
                    <span style={{ fontSize: '14px', fontWeight: 800, color, marginLeft: '16px', flexShrink: 0 }}>
                      {bd[p.key]}/{p.max}
                    </span>
                  </div>
                  <div style={{ height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px' }} />
                  </div>
                </Card>
              )
            })}
          </div>
        )}

      </div>

      {/* ── Signal Breakdown ── */}
      <div style={{ pageBreakAfter: 'always' }}>
        <SectionHeading>{T.sections.signalBreakdown}</SectionHeading>

        {/* GBP */}
        <Card accent="#4f46e5">
          <SubHeading>Google Business Profile — {bd?.gbp ?? '?'}/25 pts</SubHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 8px', lineHeight: 1.5 }}>
            {T.gbp.desc}
          </p>
          <SignalRow label={T.gbp.foundRow} value={kg?.found ? T.gbp.found : T.gbp.notFound} positive={kg?.found} />
          {kg?.title && <SignalRow label={T.gbp.nameRow} value={kg.title} positive={null} />}
          {kg?.type && <SignalRow label={T.gbp.categoryRow} value={kg.type} positive={null} />}
          <SignalRow
            label={T.gbp.ratingRow}
            value={kg?.rating != null ? `${kg.rating}★` : T.gbp.na}
            positive={kg?.rating != null ? kg.rating >= 4.0 : null}
          />
          <SignalRow
            label={T.gbp.reviewRow}
            value={kg?.reviews_count != null ? `${kg.reviews_count}` : T.gbp.na}
            positive={kg?.reviews_count != null ? kg.reviews_count >= 10 : null}
          />
          <SignalRow
            label={T.gbp.websiteRow}
            value={kg?.website ?? (kg?.website === null ? T.gbp.notListed : '—')}
            positive={kg?.website != null && kg.website !== ''}
          />
          <SignalRow
            label={T.gbp.phoneRow}
            value={kg?.phone ?? (kg?.phone === null ? T.gbp.notListed : '—')}
            positive={kg?.phone != null && kg.phone !== ''}
          />
        </Card>

        {/* Reviews */}
        <Card accent="#f59e0b">
          <SubHeading>Reviews & Reputation — {bd?.reviews ?? '?'}/22 pts</SubHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 8px', lineHeight: 1.5 }}>
            {T.reviews.desc}
          </p>
          <SignalRow
            label={T.reviews.ratingRow}
            value={kg?.rating != null ? `${kg.rating}★` : T.reviews.na}
            positive={kg?.rating != null ? kg.rating >= 4.0 : null}
          />
          <SignalRow
            label={T.reviews.countRow}
            value={kg?.reviews_count != null ? T.reviews.count(kg.reviews_count) : T.reviews.na}
            positive={kg?.reviews_count != null ? kg.reviews_count >= 50 : null}
          />
          {kg?.reviews_count != null && kg.reviews_count < 50 && (
            <div style={{
              background: '#fffbeb',
              border: '1px solid #fcd34d',
              borderRadius: '6px',
              padding: '8px 10px',
              marginTop: '8px',
            }}>
              <p style={{ fontSize: '10px', color: '#92400e', margin: 0 }}>
                {kg.reviews_count < 10
                  ? T.reviews.tooFew
                  : T.reviews.needsMore(kg.reviews_count)}
              </p>
            </div>
          )}
        </Card>

        {/* Website */}
        <Card accent="#22c55e">
          <SubHeading>Website & Schema — {bd?.website ?? '?'}/20 pts</SubHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 8px', lineHeight: 1.5 }}>
            {T.website.desc}
          </p>
          <SignalRow label={T.website.reachableRow} value={ws?.reachable ? T.website.yes : ws?.reachable === false ? T.website.notReachable : '—'} positive={ws?.reachable} />
          <SignalRow
            label={T.website.lbsRow}
            value={ws?.has_local_business_schema ? T.website.detected : ws?.has_local_business_schema === false ? T.website.notFound : '—'}
            positive={ws?.has_local_business_schema}
          />
          <SignalRow
            label={T.website.faqRow}
            value={ws?.has_faq_schema ? T.website.detected : ws?.has_faq_schema === false ? T.website.notFound : '—'}
            positive={ws?.has_faq_schema}
          />
          {!ws?.has_local_business_schema && (
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '6px', padding: '8px 10px', marginTop: '8px' }}>
              <p style={{ fontSize: '10px', color: '#166534', margin: 0 }}>
                {T.website.lbsHint}
              </p>
            </div>
          )}
        </Card>

        {/* Local Search */}
        <Card accent="#0ea5e9">
          <SubHeading>Local Search Presence — {bd?.local_search ?? '?'}/15 pts</SubHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 8px', lineHeight: 1.5 }}>
            {T.localSearch.desc}
          </p>
          <SignalRow
            label={T.localSearch.inPackRow}
            value={lp?.present ? T.gbp.found : lp?.present === false ? `✗ ${T.localSearch.notInPack}` : '—'}
            positive={lp?.present}
          />
          <SignalRow
            label={T.localSearch.positionRow}
            value={lp?.position != null ? `#${lp.position}` : lp?.present === false ? T.localSearch.notInPack : '—'}
            positive={lp?.position != null ? lp.position <= 3 : null}
          />
          <SignalRow
            label={T.localSearch.organicRow}
            value={rr?.google?.organic?.present ? T.gbp.found : rr?.google?.organic?.present === false ? `✗ ${T.localSearch.notInPack}` : '—'}
            positive={rr?.google?.organic?.present}
          />
          {!lp?.present && (
            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px', padding: '8px 10px', marginTop: '8px' }}>
              <p style={{ fontSize: '10px', color: '#1e40af', margin: 0 }}>
                {T.localSearch.notInPackHint}
              </p>
            </div>
          )}
        </Card>

        {/* AI Citations */}
        <Card accent="#8b5cf6">
          <SubHeading>AI Citations — {bd?.ai_citation ?? '?'}/18 pts</SubHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 8px', lineHeight: 1.5 }}>
            {T.aiCitations.desc}
          </p>

          {/* ChatGPT */}
          <div style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid #f1f5f9' }}>
              <span style={{ fontSize: '10px', color: '#64748b' }}>ChatGPT</span>
              <span style={{ fontSize: '10px', fontWeight: 600, color: boolColor(chatgpt?.mentioned) }}>
                {boolIcon(chatgpt?.mentioned)} {chatgpt?.mentioned ? T.aiCitations.mentioned : chatgpt ? T.aiCitations.notMentioned : '—'}
              </span>
            </div>
            {chatgpt?.snippet && (
              <p style={{ fontSize: '9px', color: '#64748b', fontStyle: 'italic', margin: '4px 0 0', lineHeight: 1.5 }}>
                &ldquo;{chatgpt.snippet.slice(0, 250)}{chatgpt.snippet.length > 250 ? '…' : ''}&rdquo;
              </p>
            )}
            {chatgpt && !chatgpt.mentioned && (
              <p style={{ fontSize: '9px', color: '#94a3b8', margin: '4px 0 0', lineHeight: 1.5 }}>
                {T.aiCitations.chatgptHint}
              </p>
            )}
          </div>

          {/* Perplexity */}
          <div style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid #f1f5f9' }}>
              <span style={{ fontSize: '10px', color: '#64748b' }}>Perplexity</span>
              <span style={{ fontSize: '10px', fontWeight: 600, color: boolColor(perplexity?.mentioned) }}>
                {boolIcon(perplexity?.mentioned)} {perplexity?.mentioned ? T.aiCitations.mentioned : perplexity ? T.aiCitations.notMentioned : '—'}
              </span>
            </div>
            {perplexity?.snippet && (
              <p style={{ fontSize: '9px', color: '#64748b', fontStyle: 'italic', margin: '4px 0 0', lineHeight: 1.5 }}>
                &ldquo;{perplexity.snippet.slice(0, 250)}{perplexity.snippet.length > 250 ? '…' : ''}&rdquo;
              </p>
            )}
            {perplexity && !perplexity.mentioned && (
              <p style={{ fontSize: '9px', color: '#94a3b8', margin: '4px 0 0', lineHeight: 1.5 }}>
                {T.aiCitations.perplexityHint}
              </p>
            )}
          </div>

          {/* Google AI Overview */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid #f1f5f9' }}>
              <span style={{ fontSize: '10px', color: '#64748b' }}>Google AI Overview</span>
              <span style={{ fontSize: '10px', fontWeight: 600, color: boolColor(aiOverview?.mentioned) }}>
                {boolIcon(aiOverview?.mentioned)} {aiOverview?.mentioned ? T.aiCitations.mentioned : aiOverview ? T.aiCitations.notMentioned : '—'}
              </span>
            </div>
            {aiOverview?.snippet && (
              <p style={{ fontSize: '9px', color: '#64748b', fontStyle: 'italic', margin: '4px 0 0', lineHeight: 1.5 }}>
                &ldquo;{aiOverview.snippet.slice(0, 250)}{aiOverview.snippet.length > 250 ? '…' : ''}&rdquo;
              </p>
            )}
          </div>
        </Card>
      </div>

      {/* ── Your Reputation ── */}
      {reputation && (reputation.strengths.length > 0 || reputation.weaknesses.length > 0) && (
        <div style={{ pageBreakInside: 'avoid', marginBottom: '20px' }}>
          <SectionHeading>{T.sections.reputation}</SectionHeading>

          {/* Header meta */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}>
            <p style={{ fontSize: '10px', color: '#64748b', margin: 0 }}>
              {T.reputation.meta(reputation.review_count, reputation.review_count !== 1 ? 's' : '')}
            </p>
            {reputation.avg_rating != null && (
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#f59e0b' }}>
                {T.reputation.avgRating(reputation.avg_rating)}
              </span>
            )}
          </div>

          {/* Strengths */}
          {reputation.strengths.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <p style={{ fontSize: '10px', fontWeight: 700, color: '#15803d', margin: '0 0 8px' }}>
                {T.reputation.strengths}
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {reputation.strengths.map((s, i) => (
                  <span key={i} style={{
                    fontSize: '10px',
                    fontWeight: 500,
                    color: '#166534',
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    padding: '3px 10px',
                    borderRadius: '12px',
                  }}>{reputationLabel(s)}</span>
                ))}
              </div>
            </div>
          )}

          {/* Weaknesses */}
          {reputation.weaknesses.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <p style={{ fontSize: '10px', fontWeight: 700, color: '#b45309', margin: '0 0 8px' }}>
                {T.reputation.weaknesses}
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {reputation.weaknesses.map((w, i) => (
                  <span key={i} style={{
                    fontSize: '10px',
                    fontWeight: 500,
                    color: '#92400e',
                    background: '#fffbeb',
                    border: '1px solid #fde68a',
                    padding: '3px 10px',
                    borderRadius: '12px',
                  }}>{reputationLabel(w)}</span>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {reputation.summary && (
            <div style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '10px 12px',
            }}>
              <p style={{ fontSize: '10px', color: '#475569', margin: 0, lineHeight: 1.6 }}>
                {reputation.summary}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Competitor Analysis ── */}
      {topCompetitors.length > 0 && (
        <div style={{ pageBreakAfter: 'always' }}>
          <SectionHeading>{T.sections.competitors}</SectionHeading>
          <p style={{ fontSize: '10px', color: '#64748b', margin: '-10px 0 16px', lineHeight: 1.5 }}>
            {T.competitors.intro(topCompetitors.length)}
          </p>

          {/* Summary comparison table */}
          {bd && (
            <div style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '12px',
              marginBottom: '16px',
              overflowX: 'auto',
            }}>
              {/* Header row */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: `140px repeat(${topCompetitors.length + 1}, 1fr)`,
                gap: '4px',
                marginBottom: '8px',
              }}>
                <div />
                <div style={{ fontSize: '10px', fontWeight: 800, color: '#4f46e5', textAlign: 'center', padding: '4px' }}>
                  {T.competitors.you}
                  {businessName && (
                    <div style={{ fontSize: '9px', fontWeight: 400, color: '#64748b', marginTop: '2px' }}>{businessName}</div>
                  )}
                </div>
                {topCompetitors.map((c, i) => (
                  <div key={i} style={{ fontSize: '10px', fontWeight: 700, color: '#1e293b', textAlign: 'center', padding: '4px' }}>
                    #{c.position ?? i + 1}
                    <div style={{ fontSize: '9px', fontWeight: 400, color: '#64748b', marginTop: '2px' }}>{c.name}</div>
                    {c.cross_border && (
                      <div style={{ fontSize: '8px', color: '#b45309', marginTop: '2px' }}>{T.competitors.diffCountry}</div>
                    )}
                    {!c.cross_border && c.cross_city && (
                      <div style={{ fontSize: '8px', color: '#1d4ed8', marginTop: '2px' }}>{T.competitors.nearbyCity(c.city)}</div>
                    )}
                  </div>
                ))}
              </div>

              {/* Data rows */}
              {[
                { label: T.competitors.totalScore, getValue: (c: Competitor | null) => c == null ? `${audit.score}/100` : c.score != null ? `${c.score}/100` : '—' },
                { label: T.competitors.rating, getValue: (c: Competitor | null) => c == null ? (kg?.rating != null ? `${kg.rating}★` : '—') : c.rating != null ? `${c.rating}★` : '—' },
                { label: T.competitors.reviews, getValue: (c: Competitor | null) => c == null ? (kg?.reviews_count != null ? `${kg.reviews_count}` : '—') : c.reviews != null ? `${c.reviews}` : '—' },
                { label: T.competitors.address, getValue: (c: Competitor | null) => c == null ? '—' : c.address ?? '—' },
                { label: T.competitors.website, getValue: (c: Competitor | null) => c == null ? (kg?.website ? kg.website.replace(/^https?:\/\/(www\.)?/, '').slice(0, 35) : '—') : c.website ? c.website.replace(/^https?:\/\/(www\.)?/, '').slice(0, 35) : '—' },
                ...T.pillars.map(p => ({
                  label: p.label,
                  getValue: (c: Competitor | null) => c == null ? `${bd[p.key]}/${p.max}` : c.breakdown ? `${c.breakdown[p.key]}/${p.max}` : '—',
                })),
              ].map((row, ri) => (
                <div key={ri} style={{
                  display: 'grid',
                  gridTemplateColumns: `140px repeat(${topCompetitors.length + 1}, 1fr)`,
                  gap: '4px',
                  borderTop: '1px solid #f1f5f9',
                }}>
                  <div style={{ fontSize: '10px', color: '#64748b', padding: '5px 4px', fontWeight: ri === 0 ? 700 : 400 }}>
                    {row.label}
                  </div>
                  <div style={{ fontSize: ri >= 3 && ri <= 4 ? '9px' : '10px', color: '#1e293b', textAlign: 'center', padding: '5px 4px', fontWeight: ri === 0 ? 700 : 400 }}>
                    {row.getValue(null)}
                  </div>
                  {topCompetitors.map((c, ci) => (
                    <div key={ci} style={{ fontSize: ri >= 3 && ri <= 4 ? '9px' : '10px', color: '#475569', textAlign: 'center', padding: '5px 4px' }}>
                      {row.getValue(c)}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── PAGE 4: Competitor Weaknesses + Citation Gaps ── */}
      {(insights || citationGaps) && (
        <div>
          {/* Competitor Weaknesses */}
          {insights && (
            <div style={{ marginBottom: '24px' }}>
              <SectionHeading>{T.sections.weaknesses}</SectionHeading>
              <div style={{
                background: '#fffbeb',
                border: '1px solid #fcd34d',
                borderRadius: '10px',
                padding: '14px 16px',
                marginBottom: '12px',
              }}>
                <p style={{ fontSize: '10px', color: '#78350f', margin: '0 0 4px', lineHeight: 1.5 }}>
                  {T.weaknesses.intro(insights.reviews_analysed, insights.competitors_analysed, insights.competitors_analysed !== 1 ? 's' : '')}
                  {insights.avg_competitor_rating != null && (
                    <>{T.weaknesses.avgRating(insights.avg_competitor_rating)}</>
                  )}{' '}
                  {T.weaknesses.hint}
                </p>
              </div>

              {(insights.themes ?? []).length > 0 ? (
                (insights.themes ?? []).map((t, i) => (
                  <Card key={i} accent="#f59e0b">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: t.example ? '6px' : 0 }}>
                      <p style={{ fontSize: '11px', fontWeight: 700, color: '#92400e', margin: 0 }}>{t.theme}</p>
                      <span style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        color: '#b45309',
                        background: '#fef3c7',
                        padding: '2px 7px',
                        borderRadius: '12px',
                        flexShrink: 0,
                        marginLeft: '8px',
                      }}>
                        {T.weaknesses.times(t.count)}
                      </span>
                    </div>
                    {t.example && (
                      <p style={{ fontSize: '10px', color: '#64748b', fontStyle: 'italic', margin: '4px 0 0' }}>
                        &ldquo;{t.example}&rdquo;
                      </p>
                    )}
                  </Card>
                ))
              ) : (
                <p style={{ fontSize: '10px', color: '#64748b', fontStyle: 'italic' }}>
                  {T.weaknesses.noPatterns}
                </p>
              )}

              {insights.opportunity_summary && (
                <div style={{
                  background: '#fef3c7',
                  border: '1px solid #fcd34d',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  marginTop: '10px',
                }}>
                  <p style={{ fontSize: '10px', fontWeight: 700, color: '#78350f', margin: '0 0 4px' }}>
                    {T.weaknesses.opportunity}
                  </p>
                  <p style={{ fontSize: '10px', color: '#92400e', margin: 0, lineHeight: 1.6 }}>
                    {insights.opportunity_summary}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Citation Gaps */}
          {citationGaps && (
            <div>
              <SectionHeading>{T.sections.citations}</SectionHeading>
              <p style={{ fontSize: '10px', color: '#64748b', margin: '-10px 0 14px', lineHeight: 1.5 }}>
                {T.citations.intro}
              </p>

              {/* Where you already appear */}
              {citationGaps.user && citationGaps.user.length > 0 && (
                <div style={{ marginBottom: '14px' }}>
                  <p style={{ fontSize: '10px', fontWeight: 700, color: '#15803d', margin: '0 0 8px' }}>
                    {T.citations.present}
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {citationGaps.user.map(dir => (
                      <span key={dir} style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: '#15803d',
                        background: '#f0fdf4',
                        border: '1px solid #86efac',
                        padding: '3px 8px',
                        borderRadius: '12px',
                      }}>
                        {dir}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Gaps */}
              {citationGaps.gaps && citationGaps.gaps.length > 0 && (
                <div>
                  <p style={{ fontSize: '10px', fontWeight: 700, color: '#b45309', margin: '0 0 8px' }}>
                    {T.citations.gaps}
                  </p>
                  <p style={{ fontSize: '10px', color: '#64748b', margin: '0 0 10px', lineHeight: 1.5 }}>
                    {T.citations.gapsHint}
                  </p>
                  {citationGaps.gaps.map(dir => (
                    <div key={dir} style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '7px 10px',
                      border: '1px solid #fcd34d',
                      background: '#fffbeb',
                      borderRadius: '8px',
                      marginBottom: '6px',
                    }}>
                      <span style={{ fontSize: '10px', fontWeight: 600, color: '#78350f' }}>{dir}</span>
                      {DIRECTORY_CLAIM_URLS[dir] && dir !== 'Reddit' && (
                        <span style={{ fontSize: '9px', color: '#4f46e5' }}>
                          {DIRECTORY_CLAIM_URLS[dir]}
                        </span>
                      )}
                      {dir === 'Reddit' && (
                        <span style={{ fontSize: '9px', color: '#64748b' }}>{T.citations.reddit}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {(!citationGaps.gaps || citationGaps.gaps.length === 0) && (
                <p style={{ fontSize: '10px', color: '#16a34a', fontWeight: 600 }}>
                  {T.citations.noGaps}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div style={{
        marginTop: '24px',
        paddingTop: '12px',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <p style={{ fontSize: '9px', color: '#94a3b8', margin: 0 }}>
          {T.footer.generated(auditDate)}
        </p>
        <p style={{ fontSize: '9px', color: '#94a3b8', margin: 0 }}>
          {T.footer.source}
        </p>
      </div>

    </div>
  )
}
