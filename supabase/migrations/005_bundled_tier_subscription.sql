-- ============================================================
-- Migration 005: Bundled Tier Subscription Model (Option B)
-- ============================================================
-- What changes:
--   • Remove per-product model (product column + per-product unique index)
--   • Replace generic stripe_id with stripe_subscription_id
--   • Convert plan_tier from free text → enum (starter | pro | business)
--   • Enforce ONE active subscription per business via partial unique index
--
-- NOTE: subscription_product enum TYPE is intentionally kept because
--       the conversations table still uses it.  Drop it later when
--       conversations is also refactored.
-- ============================================================


-- ── Step 1: Add stripe_subscription_id ─────────────────────────────────────────
-- Named specifically for Stripe subscription objects (prefix: sub_).
-- Replaces the generic stripe_id column.
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT UNIQUE;


-- ── Step 2: Copy existing Stripe subscription IDs ──────────────────────────────
-- Only rows where stripe_id already contains a Stripe subscription ID.
UPDATE subscriptions
  SET stripe_subscription_id = stripe_id
  WHERE stripe_id LIKE 'sub_%';


-- ── Step 3: Create plan_tier enum ──────────────────────────────────────────────
-- Three tiers for Phase 1.  Add more values later with ALTER TYPE ... ADD VALUE.
CREATE TYPE plan_tier_enum AS ENUM ('starter', 'pro', 'business');


-- ── Step 4: Add new enum column alongside the old text column ──────────────────
ALTER TABLE subscriptions
  ADD COLUMN plan_tier_new plan_tier_enum;


-- ── Step 5: Backfill — map existing text values → enum ─────────────────────────
-- Any NULL or unrecognised value defaults to 'starter'.
UPDATE subscriptions SET plan_tier_new =
  CASE
    WHEN plan_tier = 'pro'       THEN 'pro'::plan_tier_enum
    WHEN plan_tier = 'business'  THEN 'business'::plan_tier_enum
    ELSE 'starter'::plan_tier_enum
  END;


-- ── Step 6: Swap old text column for new enum column ───────────────────────────
ALTER TABLE subscriptions DROP COLUMN plan_tier;
ALTER TABLE subscriptions RENAME COLUMN plan_tier_new TO plan_tier;


-- ── Step 7: Make plan_tier NOT NULL with a safe default ────────────────────────
ALTER TABLE subscriptions
  ALTER COLUMN plan_tier SET NOT NULL,
  ALTER COLUMN plan_tier SET DEFAULT 'starter';


-- ── Step 8: Drop the per-product unique index ──────────────────────────────────
-- This enforced one subscription per (business, product).
-- The bundled model no longer uses product, so this index is removed.
DROP INDEX IF EXISTS subscriptions_business_product_idx;


-- ── Step 9: Drop the product column ────────────────────────────────────────────
ALTER TABLE subscriptions DROP COLUMN IF EXISTS product;


-- ── Step 10: Drop the old stripe_id column ─────────────────────────────────────
-- Fully replaced by stripe_subscription_id from Step 1.
ALTER TABLE subscriptions DROP COLUMN IF EXISTS stripe_id;


-- ── Step 11: One active subscription per business (partial unique index) ────────
-- Allows a canceled row to remain while a new subscription is created.
-- Only 'trialing', 'active', and 'past_due' rows are constrained.
CREATE UNIQUE INDEX subscriptions_one_active_per_business
  ON subscriptions (business_id)
  WHERE status IN ('trialing', 'active', 'past_due');