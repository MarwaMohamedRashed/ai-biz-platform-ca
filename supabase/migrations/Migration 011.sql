CREATE TABLE aeo_content (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    description  TEXT,
    faq          JSONB,
    schema_markup TEXT,
    social_bio   TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE aeo_content ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Members can manage their content" ON aeo_content
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );