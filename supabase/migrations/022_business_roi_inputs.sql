-- 022 — ROI inputs on businesses
--
-- Customer-provided numbers used by the dashboard ROI hero card and the
-- per-recommendation dollar tags. See leapone-roi-framework.md (simple
-- formula 3a) and project_roi_mvp memory.
--
-- All fields nullable: if the owner skips them at onboarding we fall back
-- to industry defaults from apps/web/lib/roi-defaults.ts. Settings will
-- let them update these values later.

ALTER TABLE businesses
  ADD COLUMN IF NOT EXISTS avg_customer_value_cad      numeric(10, 2),
  ADD COLUMN IF NOT EXISTS monthly_new_online_customers integer,
  ADD COLUMN IF NOT EXISTS ltv_multiple_override        numeric(6, 2);

COMMENT ON COLUMN businesses.avg_customer_value_cad IS
  'Average per-transaction customer value in CAD. Used in ROI formula. Nullable -- falls back to vertical default.';
COMMENT ON COLUMN businesses.monthly_new_online_customers IS
  'Owner-estimated new customers per month found via online channels. Nullable -- falls back to vertical default.';
COMMENT ON COLUMN businesses.ltv_multiple_override IS
  'Optional override for the vertical default LTV multiple. Nullable.';

-- Forward-looking GRANTs (no-op today, required for projects created after
-- 2026-05-30 and all projects after 2026-10-30). See project_supabase_grants_deadline.
-- businesses table already has full grants on the existing role grid; these
-- ALTERs preserve column-level access by default. No action needed here.
