// Vertical defaults for the LeapOne ROI calculation. Sourced from the
// LeapOne ROI Framework (leapone-roi-framework.md, draft v1, 2026-05-15).
//
// These are starting-point estimates. The framework calls for quarterly
// revalidation once we have real customer accounting/POS data — until
// then we present ranges, never precise figures, and always show the
// "How we calculate this" disclosure.
//
// Adding a new vertical:
//   1. Add an entry below with the four numbers from the framework table.
//   2. Add detection patterns to VERTICAL_PATTERNS so we can map the
//      free-form business.type string to the right vertical.
//   3. Update the en/fr translations in messages/*.json under
//      dashboard.roi.verticals.<key>.

export interface VerticalDefault {
  /** Stable key — matches the i18n bundle and never changes. */
  key: string
  /** Average per-transaction customer value in CAD. */
  avgCustomerValueCad: number
  /** Multiplier converting first-transaction value into expected LTV. */
  ltvMultiple: number
  /** Conversion rate. Original Formula C (3a) doesn't use it; ROI v2 Formula
   *  A/B (computeRoiV2 in roi.ts) use it as the search -> customer factor that
   *  turns category search volume into an estimated monthly customer pool. */
  conversionRate: number
  /** AI Overview / citation appearance rate for "best X" queries in this vertical. */
  aiOverviewRate: number
}

// Order: most-common verticals first so picker UIs put them at the top.
export const VERTICAL_DEFAULTS: VerticalDefault[] = [
  { key: 'restaurant',          avgCustomerValueCad:  40,    ltvMultiple:  6,   conversionRate: 0.20, aiOverviewRate: 0.45 },
  { key: 'cafe',                avgCustomerValueCad:  15,    ltvMultiple: 12,   conversionRate: 0.25, aiOverviewRate: 0.40 },
  { key: 'dentist',             avgCustomerValueCad: 200,    ltvMultiple: 12,   conversionRate: 0.40, aiOverviewRate: 0.40 },
  { key: 'physio',              avgCustomerValueCad:  90,    ltvMultiple: 10,   conversionRate: 0.35, aiOverviewRate: 0.35 },
  { key: 'family_doctor',       avgCustomerValueCad:  50,    ltvMultiple: 15,   conversionRate: 0.50, aiOverviewRate: 0.30 },
  { key: 'veterinarian',        avgCustomerValueCad: 250,    ltvMultiple:  8,   conversionRate: 0.40, aiOverviewRate: 0.30 },
  { key: 'plumber',             avgCustomerValueCad: 400,    ltvMultiple:  2.5, conversionRate: 0.30, aiOverviewRate: 0.35 },
  { key: 'auto_repair',         avgCustomerValueCad: 450,    ltvMultiple:  3,   conversionRate: 0.35, aiOverviewRate: 0.35 },
  { key: 'cleaning_service',    avgCustomerValueCad: 180,    ltvMultiple:  6,   conversionRate: 0.30, aiOverviewRate: 0.30 },
  { key: 'roofer',              avgCustomerValueCad: 4500,   ltvMultiple:  1.3, conversionRate: 0.15, aiOverviewRate: 0.30 },
  { key: 'lawyer',              avgCustomerValueCad: 2500,   ltvMultiple:  2,   conversionRate: 0.20, aiOverviewRate: 0.30 },
  { key: 'accountant',          avgCustomerValueCad: 1800,   ltvMultiple:  4,   conversionRate: 0.25, aiOverviewRate: 0.25 },
  { key: 'realtor',             avgCustomerValueCad: 12000,  ltvMultiple:  1.2, conversionRate: 0.08, aiOverviewRate: 0.35 },
  { key: 'salon',               avgCustomerValueCad:  80,    ltvMultiple:  8,   conversionRate: 0.30, aiOverviewRate: 0.35 },
  { key: 'personal_trainer',    avgCustomerValueCad: 120,    ltvMultiple:  9,   conversionRate: 0.30, aiOverviewRate: 0.30 },
  { key: 'daycare',             avgCustomerValueCad: 1400,   ltvMultiple: 18,   conversionRate: 0.25, aiOverviewRate: 0.25 },
  { key: 'retail',              avgCustomerValueCad:  60,    ltvMultiple:  4,   conversionRate: 0.25, aiOverviewRate: 0.30 },
  // Generic fallback — moderate values across the board so we don't show
  // anyone $0. Anchored to "skilled service" averages.
  { key: 'other',               avgCustomerValueCad: 150,    ltvMultiple:  4,   conversionRate: 0.25, aiOverviewRate: 0.25 },
]

const VERTICALS_BY_KEY: Record<string, VerticalDefault> = Object.fromEntries(
  VERTICAL_DEFAULTS.map(v => [v.key, v]),
)

// Free-form business.type strings → vertical key. Order matters: more-
// specific patterns first. Patterns are case-insensitive, applied via
// String.match.
const VERTICAL_PATTERNS: Array<{ pattern: RegExp; key: string }> = [
  // Healthcare — dental is its own bucket (very different LTV from generic doctor)
  { pattern: /\b(dent(ist|al)|orthodontist|periodontist|endodontist)\b/i, key: 'dentist' },
  { pattern: /\b(physio(therap(y|ist))?|physical therap(y|ist)|chiropract(or|ic)|massage therap(y|ist)|osteopath)\b/i, key: 'physio' },
  { pattern: /\b(veterin(ary|arian)|vet clinic|animal hospital)\b/i, key: 'veterinarian' },
  { pattern: /\b(family doctor|family physician|gp clinic|general practitioner|walk-?in clinic|medical clinic|naturopath|optometr(y|ist)|audiologist|psychologist|counsell?ing)\b/i, key: 'family_doctor' },
  // Food
  { pattern: /\b(restaurant|bistro|diner|steakhouse|pizz(a|eria)|sushi|grill|kitchen|eatery|brasserie|gastropub)\b/i, key: 'restaurant' },
  { pattern: /\b(caf[eé]|coffee|bakery|patisserie|tea\s?(house|room))\b/i, key: 'cafe' },
  // Trades
  { pattern: /\b(plumb(er|ing)|hvac|heating|cooling|electrician|electrical contractor|handyman)\b/i, key: 'plumber' },
  { pattern: /\b(roof(er|ing)|general contractor|renovation|construction|paving)\b/i, key: 'roofer' },
  { pattern: /\b(auto repair|mechanic|garage|tire shop|body shop|automotive)\b/i, key: 'auto_repair' },
  { pattern: /\b(cleaning service|maid|janitor(ial)?|housekeep(ing|er))\b/i, key: 'cleaning_service' },
  // Professional services
  { pattern: /\b(law(yer|\s?firm|\s?office)|attorney|paralegal|notary)\b/i, key: 'lawyer' },
  { pattern: /\b(accountant|bookkeep(ing|er)|cpa|tax preparer)\b/i, key: 'accountant' },
  { pattern: /\b(realtor|real estate|realty|brokerage)\b/i, key: 'realtor' },
  // Wellness / personal care
  { pattern: /\b(salon|barber|spa|esthetic|nail(s)?|hair)\b/i, key: 'salon' },
  { pattern: /\b(personal trainer|fitness|gym|crossfit|yoga|pilates)\b/i, key: 'personal_trainer' },
  { pattern: /\b(daycare|preschool|nursery|child ?care|montessori)\b/i, key: 'daycare' },
  // Retail
  { pattern: /\b(retail|shop|store|boutique)\b/i, key: 'retail' },
]

/**
 * Map a free-form business type string (whatever the owner typed in onboarding
 * or whatever Google's Knowledge Graph returned) to a vertical key.
 * Returns 'other' if no pattern matches.
 */
export function resolveVerticalKey(businessType: string | null | undefined): string {
  if (!businessType) return 'other'
  for (const { pattern, key } of VERTICAL_PATTERNS) {
    if (pattern.test(businessType)) return key
  }
  return 'other'
}

/** Look up the default settings for a vertical (or 'other' if unknown). */
export function getVerticalDefault(businessType: string | null | undefined): VerticalDefault {
  return VERTICALS_BY_KEY[resolveVerticalKey(businessType)] ?? VERTICALS_BY_KEY['other']
}
