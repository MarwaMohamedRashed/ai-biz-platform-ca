-- ============================================================
-- Migration 018: Custom FAQ seed questions on aeo_content
-- ============================================================
-- Phase 2 of the FAQ generation enhancement. Owner-provided questions
-- they hear from real customers. Used verbatim as the first N entries
-- in the generated FAQ; the remaining (10 - N) slots are filled by
-- the LLM. Persists across regenerations so the owner doesn't retype.
-- ============================================================

ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS custom_faq_seeds JSONB DEFAULT '[]'::jsonb;
