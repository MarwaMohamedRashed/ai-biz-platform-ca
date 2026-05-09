-- ============================================================
-- Migration 019: existing_faqs on aeo_content (Phase 4)
-- ============================================================
-- Owner-provided Q+A pairs already published on their website. Used
-- VERBATIM in the final FAQ list (we don't rewrite their existing
-- content). The LLM then generates new Q+As that DON'T duplicate any
-- topic already covered, filling out to a target of 15 total.
--
-- Stored as a list of {question, answer} objects:
--   [{"question": "Do you take Sunlife?", "answer": "Yes..."}, ...]
-- ============================================================

ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS existing_faqs JSONB DEFAULT '[]'::jsonb;
