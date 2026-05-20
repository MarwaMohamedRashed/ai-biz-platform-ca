// Market intelligence domain helpers — TS mirror of api/aeo/market_intelligence.py.
//
// canonicalVertical + normalizeCity must stay in sync with the Python originals
// because the market_intelligence table is keyed on those canonical forms.

// ── Vertical canonicalization ─────────────────────────────────────────────

const PHRASE_TO_VERTICAL: Record<string, string> = {
  restaurant:           'restaurant',
  cafe:                 'cafe',
  salon:                'salon',
  retail:               'retail',
  dentist:              'dentist',
  'physiotherapy clinic': 'physiotherapist',
  'family doctor':      'family_doctor',
  chiropractor:         'chiropractor',
  optometrist:          'optometrist',
  veterinarian:         'veterinarian',
  lawyer:               'lawyer',
  accountant:           'accountant',
  realtor:              'realtor',
  plumber:              'plumber',
  'auto repair':        'auto_repair',
  'cleaning service':   'cleaning_service',
  'personal trainer':   'personal_trainer',
  other:                'other',
}

const VERTICAL_KEYWORDS: [string, string][] = [
  ['physio',       'physiotherapist'],
  ['dental',       'dentist'],
  ['dentist',      'dentist'],
  ['chiro',        'chiropractor'],
  ['optom',        'optometrist'],
  ['eye',          'optometrist'],
  ['vet',          'veterinarian'],
  ['restaurant',   'restaurant'],
  ['cafe',         'cafe'],
  ['coffee',       'cafe'],
  ['salon',        'salon'],
  ['spa',          'salon'],
  ['lawyer',       'lawyer'],
  ['law',          'lawyer'],
  ['legal',        'lawyer'],
  ['account',      'accountant'],
  ['tax',          'accountant'],
  ['realtor',      'realtor'],
  ['real estate',  'realtor'],
  ['plumb',        'plumber'],
  ['auto',         'auto_repair'],
  ['mechanic',     'auto_repair'],
  ['clean',        'cleaning_service'],
  ['trainer',      'personal_trainer'],
  ['fitness',      'personal_trainer'],
  ['gym',          'personal_trainer'],
  ['doctor',       'family_doctor'],
  ['clinic',       'family_doctor'],
]

export function canonicalVertical(businessType: string | null | undefined): string {
  if (!businessType) return 'other'
  const t = businessType.trim().toLowerCase()
  if (PHRASE_TO_VERTICAL[t]) return PHRASE_TO_VERTICAL[t]
  for (const [needle, vertical] of VERTICAL_KEYWORDS) {
    if (t.includes(needle)) return vertical
  }
  return 'other'
}

export function normalizeCity(city: string | null | undefined): string {
  if (!city) return ''
  return city
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// ── Shared types ──────────────────────────────────────────────────────────

export interface MarketQuestion {
  question:     string
  intent:       string
  searchVolume: number | null
  mentioned:    boolean
}

export interface MarketBusiness {
  name:         string
  weightedScore: number
  mentionCount: number
  avgPosition:  number | null
}

export interface MarketRisingKeyword {
  keyword:   string
  changePct: number
}

export interface MarketSource {
  domain:      string
  label:       string
  isDirectory: boolean
  count:       number
}

export interface CategoryDemand {
  /** Total monthly search volume across the market's tracked questions. */
  totalVolume:     number
  /** Month-over-month change vs the previous refresh, e.g. 0.08 = +8%. null when no history yet. */
  momGrowthPct:    number | null
  /** Fastest-growing queries in the area (from DataForSEO monthly_searches). */
  risingKeywords:  MarketRisingKeyword[]
  /** Directories / publishers AI + Google cite for this market's questions. */
  topSources:      MarketSource[]
  /** Your AI-answer coverage (questions you appear in / total), for the "demand grew, did you?" line. */
  coveragePct:     number | null
}

export interface MarketInsightsSummary {
  city:           string
  vertical:       string
  refreshedAt:    string
  refreshStatus:  string
  totalVolume:    number
  topQuestions:   MarketQuestion[]
  topBusinesses:  MarketBusiness[]
  benchmarks: {
    yourShare:  number | null
    avgShare:   number | null
    p75Share:   number | null
    topShare:   number | null
    sampleSize: number
  }
  momShareChange: number | null
  categoryDemand: CategoryDemand
}

// ── Server-side builder ───────────────────────────────────────────────────

// Simplified name match: tokenize business name, check if any significant
// token appears (case-insensitive) in the mention name. Good enough for
// the per-question "mentioned" indicator — the Python engine uses a fuller
// fuzzy match, but we only need approximate for the UI badge.
function businessNameTokens(name: string): string[] {
  return name
    .toLowerCase()
    .split(/\s+/)
    .filter(t => t.length >= 4)
}

function isMentioned(businessName: string, mentions: Record<string, unknown[]>): boolean {
  const tokens = businessNameTokens(businessName)
  if (!tokens.length) return false
  for (const engineMentions of Object.values(mentions)) {
    for (const m of (engineMentions as { name?: string }[])) {
      const mname = (m.name ?? '').toLowerCase()
      if (tokens.some(t => mname.includes(t))) return true
    }
  }
  return false
}

interface RawMarketRow {
  id:             string
  vertical:       string
  city:           string
  questions:      unknown[]
  top_businesses: unknown[]
  benchmarks:     Record<string, unknown>
  refresh_status: string
  refreshed_at:   string
}

interface RawQuestion {
  question?:     string
  intent?:       string
  search_volume?: number | null
  mentions?:     Record<string, unknown[]>
}

interface RawBusiness {
  name?:          string
  weighted_score?: number
  mention_count?: number
  avg_position?:  number | null
}

export function buildMarketInsights(
  row: RawMarketRow,
  businessName: string,
  currentShare: number | null,
  prevShare: number | null,
  // Phase 6 — category-volume tracking inputs:
  prevCategoryVolume: number | null = null,   // from latest market_intelligence_history snapshot
  coveragePct: number | null = null,          // from latest audit's market_visibility
): MarketInsightsSummary {
  const questions = (row.questions as RawQuestion[]) ?? []
  const topBiz    = (row.top_businesses as RawBusiness[]) ?? []
  const benchmarks = row.benchmarks ?? {}

  // Top 10 questions by search volume (non-null first, then null)
  const sorted = [...questions].sort((a, b) => {
    const av = a.search_volume ?? -1
    const bv = b.search_volume ?? -1
    return bv - av
  })
  const topQuestions: MarketQuestion[] = sorted.slice(0, 10).map(q => ({
    question:     q.question ?? '',
    intent:       q.intent ?? 'mixed',
    searchVolume: q.search_volume ?? null,
    mentioned:    isMentioned(businessName, q.mentions ?? {}),
  }))

  // Total volume from all questions with non-null volume
  const totalVolume = questions.reduce((sum, q) => {
    return q.search_volume != null ? sum + q.search_volume : sum
  }, 0)

  // Top 4 businesses by weighted_score
  const topBusinesses: MarketBusiness[] = [...topBiz]
    .sort((a, b) => (b.weighted_score ?? 0) - (a.weighted_score ?? 0))
    .slice(0, 4)
    .map(b => ({
      name:         b.name ?? '',
      weightedScore: b.weighted_score ?? 0,
      mentionCount: b.mention_count ?? 0,
      avgPosition:  b.avg_position ?? null,
    }))

  const momShareChange =
    currentShare != null && prevShare != null
      ? Math.round((currentShare - prevShare) * 1000) / 1000
      : null

  // Phase 6 — category demand. category_volume_summary + category_sources are
  // computed by the refresh worker and stored in benchmarks (no extra table).
  const cvs = (benchmarks.category_volume_summary as {
    total_volume?: number
    rising_keywords?: { keyword?: string; change_pct?: number }[]
  } | undefined) ?? {}
  const categoryTotalVolume = cvs.total_volume ?? totalVolume
  const momGrowthPct =
    prevCategoryVolume != null && prevCategoryVolume > 0
      ? Math.round(((categoryTotalVolume - prevCategoryVolume) / prevCategoryVolume) * 1000) / 1000
      : null
  const risingKeywords: MarketRisingKeyword[] = (cvs.rising_keywords ?? [])
    .filter(r => r.keyword)
    .slice(0, 3)
    .map(r => ({ keyword: r.keyword as string, changePct: r.change_pct ?? 0 }))
  const topSources: MarketSource[] = ((benchmarks.category_sources as {
    domain?: string; label?: string; is_directory?: boolean; count?: number
  }[] | undefined) ?? [])
    .filter(s => s.domain)
    .slice(0, 6)
    .map(s => ({
      domain:      s.domain as string,
      label:       s.label ?? (s.domain as string),
      isDirectory: s.is_directory ?? false,
      count:       s.count ?? 0,
    }))

  return {
    city:          row.city,
    vertical:      row.vertical,
    refreshedAt:   row.refreshed_at,
    refreshStatus: row.refresh_status,
    totalVolume,
    topQuestions,
    topBusinesses,
    benchmarks: {
      yourShare: currentShare,
      avgShare:  (benchmarks.avg_mention_share as number | null) ?? null,
      p75Share:  (benchmarks.p75_mention_share as number | null) ?? null,
      topShare:  (benchmarks.top_mention_share as number | null) ?? null,
      sampleSize: (benchmarks.sample_size as number | null) ?? 0,
    },
    momShareChange,
    categoryDemand: {
      totalVolume:    categoryTotalVolume,
      momGrowthPct,
      risingKeywords,
      topSources,
      coveragePct,
    },
  }
}
