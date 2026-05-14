export type PillarKey = 'gbp' | 'reviews' | 'website' | 'local_search' | 'ai_citation'

interface RawResults {
  perplexity?: { mentioned: boolean; snippet?: string | null }
  chatgpt?: { mentioned: boolean; snippet?: string | null }
  google?: {
    ai_overview?: { mentioned: boolean; snippet?: string | null }
    local_pack?: { present: boolean; position: number | null }
    organic?: { present: boolean; position?: number | null }
    knowledge_graph?: {
      found: boolean
      title?: string | null
      rating?: number | null
      reviews_count?: number | null
      type?: string | null
      website?: string | null
      phone?: string | null
    }
  }
  website?: {
    reachable: boolean
    has_local_business_schema: boolean
    has_faq_schema: boolean
  }
}

export interface PillarMeta {
  key: PillarKey
  label: string
  max: number
  whatItMeasures: string
  whyItMatters: string
}

export const PILLARS_META: PillarMeta[] = [
  {
    key: 'gbp',
    label: 'Google Business Profile',
    max: 25,
    whatItMeasures:
      "Whether Google has a verified, complete profile for your business — Knowledge Graph entry, category, rating, contact details, and overall profile completeness.",
    whyItMatters:
      "Google Business Profile is the foundation of every local AI citation. ChatGPT, Perplexity, and Google AI Overview all pull from Google's entity graph. A weak profile equals invisible to AI.",
  },
  {
    key: 'reviews',
    label: 'Reviews & Reputation',
    max: 22,
    whatItMeasures:
      "Total Google review count and average star rating. Volume and quality both signal real-world trust — review counts above 50 with 4+ stars are strong AI-citation triggers.",
    whyItMatters:
      "AI engines weight review volume and rating heavily when deciding which local business to recommend. A 4.2★ business with 87 reviews is more 'answer-worthy' to an AI than a 4.9★ with only 3 reviews.",
  },
  {
    key: 'website',
    label: 'Website & Schema',
    max: 20,
    whatItMeasures:
      "Whether your website is reachable and includes structured data (LocalBusiness JSON-LD, FAQ schema). Schema is how AI engines parse your business at machine speed.",
    whyItMatters:
      "AI crawlers prefer structured data over guessing from prose. A site with LocalBusiness + FAQ schema gets cited 2-3x more often than one without — even if the prose is identical.",
  },
  {
    key: 'local_search',
    label: 'Local Search Presence',
    max: 15,
    whatItMeasures:
      "Whether you appear in Google's local pack (the 3 Map results) and organic search for category-relevant queries in your city.",
    whyItMatters:
      "Local-pack rank is the strongest predictor of Perplexity citations and Google AI Overview inclusion. If you're not in the pack, AI engines often don't see you.",
  },
  {
    key: 'ai_citation',
    label: 'AI Citations',
    max: 18,
    whatItMeasures:
      "Whether ChatGPT, Perplexity, and Google AI Overview mention your business by name when asked the same 3 local-search benchmark queries.",
    whyItMatters:
      "This is the literal output we measure: do the AI engines that customers ask actually know you exist? Each engine has different data sources, so cross-engine consistency is signal of true visibility.",
  },
]

export interface PillarFinding {
  signal: string
  detail: string
  hit: boolean
}

export function computePillarFindings(
  pillar: PillarKey,
  raw: RawResults | null | undefined
): PillarFinding[] {
  if (!raw) return []
  const findings: PillarFinding[] = []

  if (pillar === 'gbp') {
    const kg = raw.google?.knowledge_graph
    findings.push({
      signal: 'Google Knowledge Graph entry',
      detail: kg?.found
        ? `Found: "${kg.title ?? '(no title)'}"`
        : 'Not found — Google does not yet recognize your business as a verified entity',
      hit: !!kg?.found,
    })
    if (kg?.found) {
      findings.push({
        signal: 'Star rating on profile',
        detail: kg.rating ? `${kg.rating}★` : 'No rating data',
        hit: !!kg.rating,
      })
      findings.push({
        signal: 'Review count on profile',
        detail: kg.reviews_count ? `${kg.reviews_count} reviews` : 'No review data',
        hit: !!kg.reviews_count,
      })
      findings.push({
        signal: 'Category set',
        detail: kg.type ?? 'Not set',
        hit: !!kg.type,
      })
      findings.push({
        signal: 'Website on profile',
        detail: kg.website ?? 'Not set',
        hit: !!kg.website,
      })
      findings.push({
        signal: 'Phone on profile',
        detail: kg.phone ?? 'Not set',
        hit: !!kg.phone,
      })
    }
  }

  if (pillar === 'reviews') {
    const kg = raw.google?.knowledge_graph
    const count = kg?.reviews_count ?? 0
    findings.push({
      signal: 'Total review count',
      detail: count > 0 ? `${count} reviews` : 'Could not detect any reviews',
      hit: count > 0,
    })
    findings.push({
      signal: 'Average rating',
      detail: kg?.rating ? `${kg.rating}★` : 'No rating',
      hit: (kg?.rating ?? 0) >= 4.0,
    })
    findings.push({
      signal: 'Volume tier',
      detail: count >= 50 ? '50+ reviews (strong)' : count >= 10 ? '10–49 reviews (moderate)' : 'Under 10 reviews (weak)',
      hit: count >= 10,
    })
  }

  if (pillar === 'website') {
    const w = raw.website
    findings.push({
      signal: 'Website reachable',
      detail: w?.reachable ? 'Yes (HTTP 200)' : 'No — site did not respond or returned an error',
      hit: !!w?.reachable,
    })
    findings.push({
      signal: 'LocalBusiness JSON-LD schema',
      detail: w?.has_local_business_schema
        ? 'Detected on home page'
        : "Not detected — AI engines have to guess your business type from prose",
      hit: !!w?.has_local_business_schema,
    })
    findings.push({
      signal: 'FAQPage JSON-LD schema',
      detail: w?.has_faq_schema
        ? 'Detected'
        : 'Not detected — adding an FAQ schema makes you instantly more cite-worthy',
      hit: !!w?.has_faq_schema,
    })
  }

  if (pillar === 'local_search') {
    const lp = raw.google?.local_pack
    findings.push({
      signal: "Google local pack (Map results)",
      detail: lp?.present
        ? `Position #${lp.position ?? '?'}`
        : "Not in the local pack for your category in your city",
      hit: !!lp?.present,
    })
    findings.push({
      signal: 'Google organic results',
      detail: raw.google?.organic?.present
        ? `Position #${raw.google.organic.position ?? '?'}`
        : 'Not on page 1 of Google for your category',
      hit: !!raw.google?.organic?.present,
    })
  }

  if (pillar === 'ai_citation') {
    findings.push({
      signal: 'ChatGPT (gpt-4o-mini)',
      detail: raw.chatgpt?.mentioned
        ? `Mentioned. Snippet: "${truncate(raw.chatgpt.snippet ?? '', 140)}"`
        : 'Not mentioned in our 3 benchmark queries',
      hit: !!raw.chatgpt?.mentioned,
    })
    findings.push({
      signal: 'Perplexity (sonar)',
      detail: raw.perplexity?.mentioned
        ? `Mentioned. Snippet: "${truncate(raw.perplexity.snippet ?? '', 140)}"`
        : 'Not mentioned in our 3 benchmark queries',
      hit: !!raw.perplexity?.mentioned,
    })
    findings.push({
      signal: 'Google AI Overview',
      detail: raw.google?.ai_overview?.mentioned
        ? `Mentioned. Snippet: "${truncate(raw.google.ai_overview.snippet ?? '', 140)}"`
        : 'Not mentioned in our 3 benchmark queries',
      hit: !!raw.google?.ai_overview?.mentioned,
    })
  }

  return findings
}

function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length <= n ? s : s.slice(0, n - 1) + '…'
}

export interface ScoreTier {
  label: string
  description: string
  color: string
}

export function scoreTier(score: number): ScoreTier {
  if (score >= 80) return {
    label: 'Excellent',
    description: 'Strong AI visibility. Customers asking ChatGPT, Perplexity, or Google AI about your category are likely to see you cited. Maintain monthly audits to catch drift.',
    color: '#16a34a',
  }
  if (score >= 60) return {
    label: 'Good',
    description: 'Solid foundation with room to improve. A few targeted actions from the recommendations below will move you into Excellent territory.',
    color: '#65a30d',
  }
  if (score >= 40) return {
    label: 'Fair',
    description: "Moderate visibility. AI engines see partial signals about your business — completing the recommendations below will materially improve citations within weeks.",
    color: '#d97706',
  }
  return {
    label: 'Needs work',
    description: 'Limited AI visibility today. The recommendations below are prioritized by impact — start with the highest-impact items and re-run the audit to track progress.',
    color: '#dc2626',
  }
}
