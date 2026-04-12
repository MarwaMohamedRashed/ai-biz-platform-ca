-- ============================================================
-- Migration 002: Phase 1 — Review Responder Tables
-- Run AFTER 001_shared_tables.sql
-- ============================================================

-- ─── Google Business Profile connections ──────────────────────────────────────
-- OAuth tokens are stored in Supabase Vault (not as plain text columns).
-- Vault gives encrypted-at-rest storage with access control.
-- Pattern:
--   1. Store token string in vault.secrets → get a UUID secret key
--   2. Store that UUID here in access_token_secret / refresh_token_secret
--   3. Read token: SELECT decrypted_secret FROM vault.decrypted_secrets WHERE id = <secret_id>

CREATE TABLE review_connections (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id            UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    google_place_id        TEXT NOT NULL,
    google_account_name    TEXT,             -- Human-readable display (e.g. "Main St Salon")
    access_token_secret    UUID,             -- vault.secrets reference (not the token itself)
    refresh_token_secret   UUID,             -- vault.secrets reference (not the token itself)
    token_expires_at       TIMESTAMPTZ,
    last_sync              TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT now(),
    updated_at             TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX review_connections_business_idx ON review_connections(business_id);

-- ─── Reviews synced from Google ───────────────────────────────────────────────
CREATE TYPE review_status AS ENUM ('pending', 'responded', 'ignored');

CREATE TABLE reviews (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id      UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    google_review_id TEXT NOT NULL UNIQUE,   -- Google's internal review ID
    author           TEXT,
    rating           INTEGER CHECK (rating BETWEEN 1 AND 5),
    text             TEXT,
    review_date      TIMESTAMPTZ,
    status           review_status DEFAULT 'pending',
    synced_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX reviews_business_status_idx  ON reviews(business_id, status);
CREATE INDEX reviews_business_rating_idx  ON reviews(business_id, rating);

-- ─── AI-generated and owner-approved responses ────────────────────────────────
-- edit_ai_score: quality score (0.0–1.0) the AI assigns to the owner's edited version
-- edit_ai_warnings: any concerns the AI flagged (e.g. "Response sounds defensive")
-- edit_reviewed_at: when the AI finished reviewing the owner's edit
CREATE TYPE response_status AS ENUM ('draft', 'approved', 'posted', 'failed');

CREATE TABLE review_responses (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id          UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE UNIQUE,
    ai_draft           TEXT,                -- What the AI generated first
    final_response     TEXT,                -- What the owner approved (may have been edited)
    status             response_status DEFAULT 'draft',
    edit_ai_score      NUMERIC(3,2),        -- e.g. 0.85 — AI quality rating of owner's edit
    edit_ai_warnings   TEXT[],              -- e.g. {"Response is too long", "Mentions competitor"}
    edit_reviewed_at   TIMESTAMPTZ,         -- When AI finished reviewing the owner's edit
    posted_at          TIMESTAMPTZ,
    created_at         TIMESTAMPTZ DEFAULT now(),
    updated_at         TIMESTAMPTZ DEFAULT now()
);

-- ─── Review insights (internal analysis) ─────────────────────────────────────
-- AI-generated analysis of a business's own review data.
-- Generated periodically (e.g. weekly) and shown to the owner in the chat briefing.
-- Does NOT compare to other LeapOne customers — only analyzes this business's own reviews.
CREATE TABLE review_insights (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    avg_rating      NUMERIC(3,2),
    review_count    INTEGER,
    response_rate   NUMERIC(5,2),       -- % of reviews responded to
    common_topics   TEXT[],             -- ["staff friendly", "wait times", ...]
    sentiment_score NUMERIC(3,2),       -- -1.0 to 1.0
    summary         TEXT,               -- Plain English summary for the owner
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX review_insights_business_period_idx ON review_insights(business_id, period_start);

-- ─── Market benchmarks (external public data only) ───────────────────────────
-- Comparison data pulled from Google Places API / Yelp public APIs.
-- This is NOT cross-comparing LeapOne customers' data.
-- data_source must always be a public API — never another business's private data.
CREATE TABLE market_benchmarks (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id          UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    data_source          TEXT NOT NULL,      -- 'google_places' or 'yelp'
    competitor_name      TEXT,
    competitor_place_id  TEXT,
    avg_rating           NUMERIC(3,2),
    review_count         INTEGER,
    response_rate        NUMERIC(5,2),
    fetched_at           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX market_benchmarks_business_idx ON market_benchmarks(business_id, data_source);

-- ─── RLS Policies ────────────────────────────────────────────────────────────
ALTER TABLE review_connections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews             ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_responses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_insights     ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_benchmarks   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own review connections" ON review_connections
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own reviews" ON reviews
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own review responses" ON review_responses
    FOR ALL USING (
        review_id IN (
            SELECT r.id FROM reviews r
            JOIN businesses b ON b.id = r.business_id
            WHERE b.user_id = auth.uid()
        )
    );

CREATE POLICY "Users see own review insights" ON review_insights
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own market benchmarks" ON market_benchmarks
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

-- ─── Triggers ────────────────────────────────────────────────────────────────
CREATE TRIGGER review_connections_updated_at
    BEFORE UPDATE ON review_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER review_responses_updated_at
    BEFORE UPDATE ON review_responses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
