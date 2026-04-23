-- ============================================================
-- Migration 006: Review Insights — Replace common_topics
-- ============================================================
-- common_topics TEXT[] was too generic — the AI needs to classify
-- topics as positive or negative separately.
-- Replace with strengths TEXT[] and weaknesses TEXT[].
-- ============================================================

ALTER TABLE review_insights
  ADD COLUMN strengths  TEXT[],
  ADD COLUMN weaknesses TEXT[];

ALTER TABLE review_insights
  DROP COLUMN common_topics;