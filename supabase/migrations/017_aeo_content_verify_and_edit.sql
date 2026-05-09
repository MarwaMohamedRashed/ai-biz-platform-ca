-- ============================================================
-- Migration 017: Verify-and-edit support on aeo_content
-- ============================================================
-- Adds two columns supporting the AI-proposes-then-user-edits-and-
-- verifies flow. The pattern mirrors what already works on the reviews
-- module (review_drafts table): AI generates, user reviews/edits/
-- accepts, system stores the audit trail.
--
-- Columns:
--   verified        -- jsonb map of item-key -> bool, where item-key is
--                      a dotted path like "description.website" or
--                      "social_bio" or "faq.0".
--   last_edited_at  -- last time any item was edited via PATCH endpoint.
--                      Helps "what's been touched since last regenerate"
--                      diagnostics.
-- ============================================================

ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS verified       JSONB DEFAULT '{}'::jsonb;
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMPTZ;
