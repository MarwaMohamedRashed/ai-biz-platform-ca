-- 020 - businesses.competitor_scope
--
-- Per-business preference for how broadly competitors are identified during
-- the audit. Matches the four-option mental model owners asked for, minus
-- 'specific distance' which would require a paid geocoding API and is
-- deferred to a later sprint.
--
--   local   - same city  (current default behaviour, city-scoped SerpApi `location`)
--   country - same country, ignore city/province (broader, good for thin local markets)
--   global  - any country, no scope filter (good for SaaS / online services where
--             real competitors aren't local)
--
-- Drives `run_google_multi` location-string construction and the cross-border
-- competitor filter in api/aeo/router.py.
--
-- Default 'local' preserves existing behaviour for every current account.

ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS competitor_scope text
  NOT NULL DEFAULT 'local'
  CHECK (competitor_scope IN ('local', 'country', 'global'));

COMMENT ON COLUMN businesses.competitor_scope IS
  'Scope for competitor detection during the audit. local=same city, country=same country, global=worldwide.';
