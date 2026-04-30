CREATE TABLE aeo_audits (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id          UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    score                INTEGER NOT NULL DEFAULT 0,
    perplexity_mentioned BOOLEAN DEFAULT FALSE,
    perplexity_snippet   TEXT,
    google_ai_mentioned  BOOLEAN DEFAULT FALSE,
    google_ai_snippet    TEXT,
    raw_results          JSONB,
    created_at           TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE aeo_audits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Members can view their audits" ON aeo_audits
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

CREATE INDEX aeo_audits_business_id_idx ON aeo_audits(business_id);