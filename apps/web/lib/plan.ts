import { PLAN_PRODUCTS, type PlanTier, type Product } from '@/config/plans'

export function can(tier: PlanTier, product: Product): boolean {
  return (PLAN_PRODUCTS[tier] as readonly string[]).includes(product)
}