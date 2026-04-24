-- ============================================================
-- Seed: Default business_settings for existing businesses
-- Run once after migration 007 to backfill existing records.
-- Safe to re-run — ON CONFLICT DO NOTHING skips duplicates.
-- ============================================================

INSERT INTO business_settings (
    business_id,
    tone_preference,
    business_description,
    auto_draft_enabled,
    response_language,
    response_length,
    cta_enabled,
    delay_acknowledgment,
    contact_info_in_response
)
SELECT
    b.id,
    'casual'::tone_preference_enum,
    CASE b.type
        WHEN 'salon'      THEN 'We are a welcoming hair and beauty salon dedicated to making every client feel their best. Our team of experienced stylists offers cuts, colour, and treatments in a relaxing atmosphere.'
        WHEN 'restaurant' THEN 'We are a family-friendly restaurant serving fresh, made-from-scratch meals. We take pride in our warm hospitality and our commitment to quality ingredients sourced locally wherever possible.'
        WHEN 'cafe'       THEN 'We are a cozy neighbourhood café offering specialty coffee, fresh pastries, and light meals. Our goal is to be your favourite place to start the day or catch up with friends.'
        WHEN 'clinic'     THEN 'We are a patient-centred health clinic providing compassionate, professional care. Our team is committed to your well-being and ensures every visit is comfortable and thorough.'
        WHEN 'plumber'    THEN 'We are a licensed plumbing company serving the local community with fast, reliable, and honest service. No job is too big or too small — we stand behind our work with a satisfaction guarantee.'
        ELSE              'We are a local Canadian small business committed to delivering excellent service and building lasting relationships with our community.'
    END,
    TRUE,   -- auto_draft_enabled
    'match_reviewer'::response_language_enum,
    'medium',
    TRUE,   -- cta_enabled
    FALSE,  -- delay_acknowledgment (opt-in only)
    FALSE   -- contact_info_in_response
FROM businesses b
WHERE NOT EXISTS (
    SELECT 1 FROM business_settings s WHERE s.business_id = b.id
);