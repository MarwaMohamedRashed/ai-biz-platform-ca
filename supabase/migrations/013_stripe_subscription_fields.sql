
-- ============================================================
-- Migration 013: Stripe subscription fields
-- ============================================================
-- Adds the four columns the Stripe webhook handler updates:
--   trial_end             — 14-day trial expiry, null after conversion
--   current_period_end    — when the current paid period renews
--   cancel_at_period_end  — true when user clicked Cancel; access until period_end
--   stripe_customer_id    — links to Stripe Customer object (cus_...)
-- ============================================================
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_end timestamptz;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS current_period_end timestamptz;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end boolean default false;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT UNIQUE;