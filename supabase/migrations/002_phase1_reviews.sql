-- ============================================================
-- Migration 002: Phase 1 — Review Responder Tables
-- Run AFTER 001_shared_tables.sql
-- ============================================================

-- ─── Google Business Profile connections ──────────────────────────────────────
CREATE TABLE review_connections (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id    UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    google_place_id TEXT NOT NULL,
    access_token   TEXT,           -- Encrypted OAuth token
    refresh_token  TEXT,           -- For refreshing the access token
    last_sync      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT now()
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

CREATE INDEX reviews_business_status_idx ON reviews(business_id, status);

-- ─── AI-generated and owner-approved responses ────────────────────────────────
CREATE TYPE response_status AS ENUM ('draft', 'approved', 'posted', 'failed');

CREATE TABLE review_responses (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id      UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE UNIQUE,
    ai_draft       TEXT,           -- What the AI generated
    final_response TEXT,           -- What the owner approved (may have edited)
    status         response_status DEFAULT 'draft',
    posted_at      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

-- ─── RLS Policies ────────────────────────────────────────────────────────────
ALTER TABLE review_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews            ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_responses   ENABLE ROW LEVEL SECURITY;

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

-- ─── Trigger for updated_at ───────────────────────────────────────────────────
CREATE TRIGGER review_responses_updated_at
    BEFORE UPDATE ON review_responses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
