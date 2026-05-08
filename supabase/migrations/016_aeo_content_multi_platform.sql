-- ============================================================
-- Migration 016: Multi-platform descriptions + FAQ schema + language
-- ============================================================
-- Path A rebuild of the Content tab. Adds columns to support:
--   * descriptions (website / gbp / yelp variants in one JSONB)
--   * faq_schema   (FAQPage JSON-LD wrapping the Q&A list)
--   * language     ('en' | 'fr' for the bilingual content tab)
--   * paa_questions (the SerpApi People-Also-Ask seeds used at gen time,
--                    stored for transparency)
-- ============================================================

ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS descriptions   JSONB;
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS faq_schema     TEXT;
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS language       TEXT DEFAULT 'en';
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS paa_questions  JSONB;
