-- 023 — market intelligence layer (Phase 1)
--
-- Cached per-(vertical, city, country) AI-visibility intelligence plus monthly
-- history snapshots. See docs/market-intelligence-architecture.md.
--
-- These are SHARED resources, NOT per-business: a single row for
-- (dentist, Burlington, Canada) serves every dentist customer in Burlington.
-- That's the decision that makes the refresh budget bounded by unique
-- (vertical, city) combos instead of by customer count.
--
-- Access model: reads are open to authenticated users (shared market data);
-- writes happen only through the service-role refresh worker. RLS is enabled
-- with a read-only policy; service_role bypasses RLS for the refresh writes.
--
-- Not built here (per Phase 0 outcome):
--   * business_branded_search — dropped; replaced by category-volume tracking
--     which reuses market_intelligence_history (no new table).
--   * per-audit market_visibility — rides in existing aeo_audits.raw_results
--     JSONB; no DDL needed.

CREATE TABLE market_intelligence (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  vertical        TEXT NOT NULL,                       -- canonical key, e.g. 'dentist'
  city            TEXT NOT NULL,                       -- normalized, e.g. 'Burlington'
  province        TEXT NOT NULL,                       -- e.g. 'ON'
  country         TEXT NOT NULL DEFAULT 'Canada',

  -- Top-N tracked questions: [{ question, intent, search_volume, competition,
  --   cpc, monthly_searches, last_seen, mentions: { chatgpt, perplexity, google_ai } }]
  questions       JSONB NOT NULL DEFAULT '[]'::jsonb,

  -- Leaderboard derived from questions[].mentions:
  --   [{ name, place_id, mention_count, weighted_score, avg_position, sentiment_avg }]
  top_businesses  JSONB NOT NULL DEFAULT '[]'::jsonb,

  -- Vertical benchmarks: { avg_mention_share, p75_mention_share,
  --   top_mention_share, sample_size, computed_at }
  benchmarks      JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- GBP Insights aggregate slot — deferred until Google approval (July 2026).
  -- Designed-for, stays NULL at launch.
  observed_funnel JSONB DEFAULT NULL,

  refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  refresh_status  TEXT NOT NULL DEFAULT 'fresh',       -- fresh | refreshing | stale | failed
  refresh_error   TEXT DEFAULT NULL,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (vertical, city, country)
);

CREATE INDEX market_intelligence_lookup ON market_intelligence (vertical, city, country);
CREATE INDEX market_intelligence_stale  ON market_intelligence (refreshed_at) WHERE refresh_status = 'fresh';

COMMENT ON TABLE market_intelligence IS
  'Shared cached AI-visibility intelligence per (vertical, city, country). One row per market, reused across all customers in that market. Written only by the service-role refresh worker.';


-- Monthly snapshots — the Progress / drift card needs a previous-month
-- baseline. The refresh worker copies the live row here before overwriting.
CREATE TABLE market_intelligence_history (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  market_id      UUID NOT NULL REFERENCES market_intelligence(id) ON DELETE CASCADE,
  snapshot_month DATE NOT NULL,                        -- first of month, e.g. '2026-05-01'
  questions      JSONB NOT NULL,
  top_businesses JSONB NOT NULL,
  benchmarks     JSONB NOT NULL,
  snapshotted_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (market_id, snapshot_month)
);

CREATE INDEX market_intelligence_history_lookup ON market_intelligence_history (market_id, snapshot_month DESC);

COMMENT ON TABLE market_intelligence_history IS
  'Monthly snapshots of market_intelligence rows. Also backs category-volume tracking (demand growth/shrink over time).';


-- ── Access control ──────────────────────────────────────────────────────────
-- Shared read, service-role write. service_role bypasses RLS, so the read-only
-- policy below applies to authenticated clients only; the refresh worker (which
-- uses the service key) is unaffected and can write.
ALTER TABLE market_intelligence         ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_intelligence_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read market intelligence"
  ON market_intelligence FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated can read market intelligence history"
  ON market_intelligence_history FOR SELECT TO authenticated USING (true);

-- Explicit GRANTs — required for projects created after 2026-05-30 (and all
-- projects after 2026-10-30). LeapOne was created 2026-04-13 but the Data API
-- default-access change applies, so new tables need their grants spelled out.
-- See project_supabase_grants_deadline.
GRANT SELECT ON market_intelligence         TO authenticated;
GRANT SELECT ON market_intelligence_history TO authenticated;
GRANT ALL    ON market_intelligence         TO service_role;
GRANT ALL    ON market_intelligence_history TO service_role;
