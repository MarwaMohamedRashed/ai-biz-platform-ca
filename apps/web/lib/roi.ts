// ROI computation — simple formula (3a) from leapone-roi-framework.md.
//
//   AI_INFLUENCED  = N × A
//   EXPOSURE_LOW   = AI_INFLUENCED × (S/100) × V × L × (1 − UNCERTAINTY)
//   EXPOSURE_HIGH  = AI_INFLUENCED × (S/100) × V × L × (1 + UNCERTAINTY)
//   AT_RISK_LOW    = AI_INFLUENCED × (1 − S/100) × V × L × (1 − UNCERTAINTY)
//   AT_RISK_HIGH   = AI_INFLUENCED × (1 − S/100) × V × L × (1 + UNCERTAINTY)
//   POTENTIAL_LOW  = AI_INFLUENCED × CEILING × V × L × (1 − UNCERTAINTY)
//   POTENTIAL_HIGH = AI_INFLUENCED × CEILING × V × L × (1 + UNCERTAINTY)
//
// where:
//   N = monthly new online customers (from owner; falls back to vertical-default proxy)
//   A = AI share of online discovery (system-wide constant, 2026 midpoint)
//   S = AEO score (from the most recent audit)
//   V = avg customer value CAD (from owner; falls back to vertical default)
//   L = LTV multiple (override or vertical default)
//   CEILING = practical maximum capture rate at perfect score (0.95)
//   UNCERTAINTY = ± band around every figure (default 0.20). The framework
//                 doc demands ranges, never precise figures.
//
// IMPORTANT: the output is labelled "exposure" in the UI, not "captured
// revenue". The score → revenue relationship is correlational, not causal,
// so promising captured revenue invites disappointment. Exposure is the
// honest framing for the part of the AI-search opportunity our score
// touches today.

import { getVerticalDefault, type VerticalDefault } from './roi-defaults'

/** 2026 midpoint per Sparktoro Aug 2025 + Stackmatix Mar 2026. */
export const DEFAULT_AI_SHARE = 0.22
/** Practical capture ceiling — we never promise 100%. */
export const POTENTIAL_CEILING = 0.95
/** Symmetrical band around every monthly figure (± fraction). */
export const UNCERTAINTY = 0.20

// When the owner skips the "monthly new online customers" question we
// have to estimate it. The placeholder below is conservative — a small
// SMB picking up roughly one customer per business day from online. Real
// businesses will swing wide on either side; the UI hint should encourage
// owners to fill in their actual number.
export const FALLBACK_MONTHLY_ONLINE_CUSTOMERS = 20

export interface RoiInputs {
  /** Free-form business type from the businesses row. Used for vertical lookup. */
  businessType?: string | null
  /** Owner-provided monthly new online customers, if known. */
  monthlyNewOnlineCustomers?: number | null
  /** Owner-provided average customer value in CAD, if known. */
  avgCustomerValueCad?: number | null
  /** Override for LTV multiple — usually null, falls back to vertical default. */
  ltvMultipleOverride?: number | null
  /** AEO score (0–100) from the latest audit. */
  score: number
  /** Override for AI share of discovery — useful for what-if calculations. */
  aiShareOverride?: number
}

export interface RoiRange {
  low: number
  high: number
}

export interface RoiBreakdown {
  /** Inputs the formula resolved to, after fallbacks. Surfaced in the UI under "How we calculate this". */
  resolved: {
    vertical:                VerticalDefault
    monthlyNewOnlineCustomers: number
    monthlyNewOnlineCustomersFromOwner: boolean
    avgCustomerValueCad:     number
    avgCustomerValueFromOwner: boolean
    ltvMultiple:             number
    ltvFromOwner:            boolean
    aiShare:                 number
    score:                   number
  }
  /** Which formula produced these numbers. Shown in the card footer. */
  formulaSource: 'A' | 'B' | 'C'
  /** Estimated AI-influenced customers per month (single point, used by UI labels). */
  aiInfluencedCustomersPerMonth: number
  /** Estimated lifetime revenue per AI-influenced customer (single point). */
  lifetimeValueCad: number
  /** Estimated monthly revenue exposure we're currently capturing, as a range. */
  exposureMonthly: RoiRange
  /** Estimated monthly revenue gap to perfect, as a range. */
  atRiskMonthly: RoiRange
  /** Estimated monthly revenue at the 95% ceiling, as a range. */
  potentialMonthly: RoiRange
  /** Estimated monthly upside between current and potential, as a range. */
  upsideMonthly: RoiRange
}

/**
 * Compute the ROI breakdown for a business. Pure function; safe to call from
 * a Server Component, a Client Component, or a route handler.
 */
export function computeRoi(inputs: RoiInputs): RoiBreakdown {
  const vertical = getVerticalDefault(inputs.businessType)
  const aiShare  = inputs.aiShareOverride ?? DEFAULT_AI_SHARE

  // Resolve inputs against fallbacks. We track whether each value came
  // from the owner or from a default, so the disclosure can name it.
  const monthlyNewOnlineCustomers = inputs.monthlyNewOnlineCustomers
    ?? FALLBACK_MONTHLY_ONLINE_CUSTOMERS
  const avgCustomerValueCad = inputs.avgCustomerValueCad
    ?? vertical.avgCustomerValueCad
  const ltvMultiple = inputs.ltvMultipleOverride
    ?? vertical.ltvMultiple

  const score = clamp(inputs.score, 0, 100)
  const aiInfluenced = monthlyNewOnlineCustomers * aiShare
  const ltv = avgCustomerValueCad * ltvMultiple

  const capturedPoint  = aiInfluenced * (score / 100) * ltv
  const atRiskPoint    = aiInfluenced * (1 - score / 100) * ltv
  const potentialPoint = aiInfluenced * POTENTIAL_CEILING * ltv
  const upsidePoint    = Math.max(0, potentialPoint - capturedPoint)

  return {
    resolved: {
      vertical,
      monthlyNewOnlineCustomers,
      monthlyNewOnlineCustomersFromOwner: inputs.monthlyNewOnlineCustomers != null,
      avgCustomerValueCad,
      avgCustomerValueFromOwner: inputs.avgCustomerValueCad != null,
      ltvMultiple,
      ltvFromOwner: inputs.ltvMultipleOverride != null,
      aiShare,
      score,
    },
    formulaSource: 'C',
    aiInfluencedCustomersPerMonth: aiInfluenced,
    lifetimeValueCad: ltv,
    exposureMonthly:  toRange(capturedPoint),
    atRiskMonthly:    toRange(atRiskPoint),
    potentialMonthly: toRange(potentialPoint),
    upsideMonthly:    toRange(upsidePoint),
  }
}

function toRange(point: number): RoiRange {
  return {
    low:  Math.max(0, point * (1 - UNCERTAINTY)),
    high: point * (1 + UNCERTAINTY),
  }
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(Math.max(n, min), max)
}

// ─── Display helpers ────────────────────────────────────────────────────────

/**
 * Format a single CAD figure for inline display ("$3,200"). Rounded to the
 * nearest $50 to avoid implying false precision — the underlying math is
 * approximate and the spec demands ranges, not point figures.
 */
export function formatCad(value: number, locale: string = 'en'): string {
  const rounded = roundToNearest(value, 50)
  return new Intl.NumberFormat(locale === 'fr' ? 'fr-CA' : 'en-CA', {
    style:                 'currency',
    currency:              'CAD',
    maximumFractionDigits: 0,
  }).format(rounded)
}

/**
 * Format a range ("$2,400 – $4,200") for display. Used everywhere the
 * framework calls for ranges instead of precise figures.
 */
export function formatCadRange(range: RoiRange, locale: string = 'en'): string {
  const dash = '–' // en-dash, matches typographic style of audit copy
  return `${formatCad(range.low, locale)} ${dash} ${formatCad(range.high, locale)}`
}

function roundToNearest(value: number, step: number): number {
  return Math.round(value / step) * step
}

// ─── Per-recommendation dollar attribution ─────────────────────────────────

// Each audit pillar carries a maximum-point contribution to the score.
// Mirrors the FastAPI scoring model (see api/aeo/router.py: calculate_score).
// The exact weights don't have to match perfectly; this is a UI heuristic.
export const PILLAR_MAX_POINTS: Record<string, number> = {
  gbp:          25,
  reviews:      22,
  website:      20,
  local_search: 15,
  ai_citation:  18,
}

/**
 * Estimated monthly dollar impact of implementing one recommendation.
 *
 * Heuristic: a recommendation in pillar P with relative "impact" rating I
 * (1–5 scale from the FastAPI recommendation list) contributes roughly
 *   I / 5 × PILLAR_MAX_POINTS[P] / 100
 * of the AI-influenced LTV pool. We then ± by UNCERTAINTY to produce a
 * range. Caps at the size of upsideMonthly so we don't claim a single
 * action delivers more than the entire potential headroom.
 */
export function recommendationImpactRange(
  pillar: string,
  impact: number, // 1..5 from the recs list
  roi: RoiBreakdown,
): RoiRange {
  const pillarPoints = PILLAR_MAX_POINTS[pillar] ?? 10
  const i = clamp(impact ?? 3, 1, 5)
  const fractionOfPotential = (i / 5) * (pillarPoints / 100)
  const point = roi.potentialMonthly.low / (1 - UNCERTAINTY) * fractionOfPotential
  const cappedPoint = Math.min(point, roi.upsideMonthly.high)
  return toRange(cappedPoint)
}

// ─── ROI v2 — market-intelligence-backed formulas ──────────────────────────

/** Shape of audits.raw_results.market_visibility, written by market_augment.py. */
export interface MarketVisibility {
  market_id:              string
  questions_covered:      number
  questions_total:        number
  /** Sum of non-null search_volume across market questions. */
  total_volume:           number
  /** Volume-weighted AI mention share for this business across the question set. */
  weighted_mention_share: number | null
  position_avg:           number | null
  sentiment_avg:          number | null
  /** Average mention share across all businesses in the same (vertical, city). */
  vertical_avg_share:     number | null
  /** 75th-percentile mention share — the target for "outperform most local peers". */
  vertical_p75_share:     number | null
  /** Sum of non-null search_volume from the per-business augmented keyword set. */
  augmented_volume_total: number | null
  augmented_n_with_volume: number | null
  data_ready:             boolean
}

/**
 * Pick and run the best available ROI formula given market visibility data.
 *
 * Formula A — `total_volume` from the cached question set + observed mention share.
 *   Best signal. Used when market_visibility is data_ready and has measurable volume.
 * Formula B — augmented_volume_total + question coverage ratio.
 *   Used when volume exists from augmentation but Formula A data is thin.
 * Formula C — existing score-based formula (computeRoi). Final fallback.
 */
export function computeRoiV2(
  inputs: RoiInputs,
  marketVisibility?: MarketVisibility | null,
): RoiBreakdown {
  if (marketVisibility?.data_ready) {
    const share = marketVisibility.weighted_mention_share
    const vol   = marketVisibility.total_volume ?? 0

    // Formula A: observed mention share × measured market volume
    if (share != null && vol > 0) {
      return computeRoiFormulaA(inputs, marketVisibility)
    }

    // Formula B: question coverage × augmented volume
    const augVol = marketVisibility.augmented_volume_total ?? 0
    if (marketVisibility.questions_total > 0 && augVol > 0) {
      return computeRoiFormulaB(inputs, marketVisibility)
    }
  }

  // Formula C: existing score-based path
  return computeRoi(inputs)
}

/**
 * Formula A — volume-weighted mention share (primary path).
 *
 *   aiPool = total_volume × aiShare
 *   captured = mention_share × aiPool × ltv
 *   potential = CEILING × aiPool × ltv
 *   upside = (target_share − mention_share) × aiPool × ltv
 *     where target_share = min(CEILING, vertical_p75_share)
 */
function computeRoiFormulaA(inputs: RoiInputs, mv: MarketVisibility): RoiBreakdown {
  const vertical = getVerticalDefault(inputs.businessType)
  const aiShare  = inputs.aiShareOverride ?? DEFAULT_AI_SHARE

  const avgCustomerValueCad = inputs.avgCustomerValueCad ?? vertical.avgCustomerValueCad
  const ltvMultiple         = inputs.ltvMultipleOverride ?? vertical.ltvMultiple
  const ltv = avgCustomerValueCad * ltvMultiple

  const share       = mv.weighted_mention_share!
  const aiPool      = mv.total_volume * aiShare
  const targetShare = Math.min(POTENTIAL_CEILING, mv.vertical_p75_share ?? POTENTIAL_CEILING)

  const capturedPoint  = share * aiPool * ltv
  const potentialPoint = POTENTIAL_CEILING * aiPool * ltv
  const upsidePoint    = Math.max(0, (targetShare - share) * aiPool * ltv)
  const atRiskPoint    = Math.max(0, potentialPoint - capturedPoint)

  return {
    resolved: {
      vertical,
      // Formula A doesn't use monthly_new_online_customers as the main input,
      // but we preserve it for the math disclosure block.
      monthlyNewOnlineCustomers: inputs.monthlyNewOnlineCustomers ?? 0,
      monthlyNewOnlineCustomersFromOwner: inputs.monthlyNewOnlineCustomers != null,
      avgCustomerValueCad,
      avgCustomerValueFromOwner: inputs.avgCustomerValueCad != null,
      ltvMultiple,
      ltvFromOwner: inputs.ltvMultipleOverride != null,
      aiShare,
      score: inputs.score,
    },
    formulaSource: 'A',
    aiInfluencedCustomersPerMonth: aiPool,
    lifetimeValueCad: ltv,
    exposureMonthly:  toRange(capturedPoint),
    atRiskMonthly:    toRange(atRiskPoint),
    potentialMonthly: toRange(potentialPoint),
    upsideMonthly:    toRange(upsidePoint),
  }
}

/**
 * Formula B — question coverage × augmented volume (mid-quality fallback).
 *
 *   coverage = questions_covered / questions_total
 *   aiPool = augmented_volume_total × aiShare
 *   captured = coverage × aiPool × ltv
 */
function computeRoiFormulaB(inputs: RoiInputs, mv: MarketVisibility): RoiBreakdown {
  const vertical = getVerticalDefault(inputs.businessType)
  const aiShare  = inputs.aiShareOverride ?? DEFAULT_AI_SHARE

  const avgCustomerValueCad = inputs.avgCustomerValueCad ?? vertical.avgCustomerValueCad
  const ltvMultiple         = inputs.ltvMultipleOverride ?? vertical.ltvMultiple
  const ltv = avgCustomerValueCad * ltvMultiple

  const coverage   = mv.questions_covered / mv.questions_total
  const aiPool     = (mv.augmented_volume_total ?? 0) * aiShare

  const capturedPoint  = coverage * aiPool * ltv
  const potentialPoint = POTENTIAL_CEILING * aiPool * ltv
  const upsidePoint    = Math.max(0, potentialPoint - capturedPoint)
  const atRiskPoint    = Math.max(0, (1 - coverage) * aiPool * ltv)

  return {
    resolved: {
      vertical,
      monthlyNewOnlineCustomers: inputs.monthlyNewOnlineCustomers ?? 0,
      monthlyNewOnlineCustomersFromOwner: inputs.monthlyNewOnlineCustomers != null,
      avgCustomerValueCad,
      avgCustomerValueFromOwner: inputs.avgCustomerValueCad != null,
      ltvMultiple,
      ltvFromOwner: inputs.ltvMultipleOverride != null,
      aiShare,
      score: inputs.score,
    },
    formulaSource: 'B',
    aiInfluencedCustomersPerMonth: aiPool,
    lifetimeValueCad: ltv,
    exposureMonthly:  toRange(capturedPoint),
    atRiskMonthly:    toRange(atRiskPoint),
    potentialMonthly: toRange(potentialPoint),
    upsideMonthly:    toRange(upsidePoint),
  }
}
