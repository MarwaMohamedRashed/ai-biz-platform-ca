-- ============================================================
-- Migration 007: Business AI Settings
-- ============================================================
-- Stores per-business preferences that control how the AI
-- generates review responses. Kept separate from the businesses
-- table so profile data and AI config don't mix.
--
-- One row per business. Created on first save; read with defaults
-- when the row doesn't exist yet (handled in application code).
-- ============================================================

-- ─── Enum types ───────────────────────────────────────────────────────────────

CREATE TYPE tone_preference_enum AS ENUM (
    'casual',           -- Warm, friendly, conversational
    'professional',     -- Formal, polished, business-like
    'playful'           -- Light humour, energetic, fun
);

CREATE TYPE response_language_enum AS ENUM (
    'match_reviewer',   -- Detect reviewer language and reply in kind (recommended)
    'english',          -- Always reply in English regardless of review language
    'french',           -- Always reply in French regardless of review language
    'both'              -- Reply in both English and French
);

-- ─── Table ────────────────────────────────────────────────────────────────────

CREATE TABLE business_settings (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id                 UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,

    -- AI tone & voice
    tone_preference             tone_preference_enum NOT NULL DEFAULT 'casual',
    business_description        TEXT,                       -- Context the AI uses when drafting responses

    -- Response behaviour
    auto_draft_enabled          BOOLEAN NOT NULL DEFAULT TRUE,   -- Auto-generate drafts when review arrives
    response_language           response_language_enum NOT NULL DEFAULT 'match_reviewer',
    response_length             TEXT NOT NULL DEFAULT 'medium'
                                    CHECK (response_length IN ('short', 'medium', 'long')),

    -- CTA (Call to Action — closing line encouraging reviewer to return/share)
    cta_enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    cta_custom_text             TEXT,                       -- If set, use this instead of AI-generated CTA

    -- Negative review handling
    delay_acknowledgment        BOOLEAN NOT NULL DEFAULT FALSE,  -- Add apology if review >3 days old
    contact_info_in_response    BOOLEAN NOT NULL DEFAULT FALSE,  -- Include phone/email in negative responses

    created_at                  TIMESTAMPTZ DEFAULT now(),
    updated_at                  TIMESTAMPTZ DEFAULT now(),

    UNIQUE (business_id)        -- One settings row per business
);

-- ─── Auto-update updated_at ───────────────────────────────────────────────────

CREATE TRIGGER business_settings_updated_at
    BEFORE UPDATE ON business_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── Row Level Security ───────────────────────────────────────────────────────

ALTER TABLE business_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Members can manage their business settings" ON business_settings
    FOR ALL USING (
        business_id IN (
            SELECT business_id FROM business_members WHERE user_id = auth.uid()
        )
    );