-- 021 - businesses.user_competitors
--
-- User-confirmed competitor list. Once non-null, every audit scores this exact
-- list instead of re-discovering from the Google local pack. Owners pick during
-- onboarding (see StepConfirmCompetitors) and edit any time from Settings or
-- the Competitors page.
--
--   NULL  - use auto-discovery (legacy behaviour for pre-migration rows)
--   []    - owner explicitly said 'no competitors'
--   [...] - confirmed list, max 5 entries
--
-- Entry shape:
--   {
--     place_id:     "ChIJ...",
--     name:         "ACT Physiotherapy",
--     source:       "auto" | "manual",
--     added_at:     "2026-05-15T10:30:00Z",
--     last_seen_at: "2026-05-22T03:00:00Z",  // updated each audit run if found
--     status:       "active" | "stale" | "closed"
--   }
--
-- Related: businesses.competitor_scope (migration 020) controls how the audit's
-- initial *suggestions* are sourced (local / country / global). user_competitors
-- then locks the owner's curated selection independent of scope.

ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS user_competitors JSONB DEFAULT NULL;

COMMENT ON COLUMN businesses.user_competitors IS
  'User-confirmed competitor list (max 5 entries). NULL = auto-discovery; [] = none; [...] = locked list scored on every audit.';
