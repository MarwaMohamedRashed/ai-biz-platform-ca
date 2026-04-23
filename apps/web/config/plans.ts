export const PLAN_PRODUCTS = {
  starter:  ['reviews'],
  pro:      ['reviews', 'bookings'],
  business: ['reviews', 'bookings', 'guide'],
} as const

export type PlanTier = keyof typeof PLAN_PRODUCTS
export type Product  = 'reviews' | 'bookings' | 'guide'

export const PHASE1_TIER: PlanTier = 'starter'