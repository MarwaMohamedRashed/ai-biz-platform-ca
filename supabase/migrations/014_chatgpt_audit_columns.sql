-- ============================================================
-- Migration 014: ChatGPT audit columns
-- ============================================================
-- Adds two columns to aeo_audits to store the ChatGPT citation
-- result alongside the existing Perplexity and Google AI fields.
-- ============================================================
ALTER TABLE aeo_audits ADD COLUMN IF NOT EXISTS chatgpt_mentioned boolean;
ALTER TABLE aeo_audits ADD COLUMN IF NOT EXISTS chatgpt_snippet   text;
