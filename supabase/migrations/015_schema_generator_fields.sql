-- ============================================================
-- Migration 015: Schema generator profile fields
-- ============================================================
-- Adds the structured fields the deterministic JSON-LD schema
-- builder needs. The existing `address` column on `businesses`
-- holds the full single-line address pulled from SerpApi during
-- the audit pipeline -- it is intentionally left alone here.
-- These four fields are user-edited via the business profile
-- form and feed Schema.org `streetAddress`, `postalCode`,
-- `image`, and `priceRange`.
-- ============================================================

ALTER TABLE businesses ADD COLUMN IF NOT EXISTS street_address TEXT;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS postal_code    TEXT;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS image_url      TEXT;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS price_range    TEXT;

-- Constrain price_range to the four Schema.org-accepted symbols
-- (or NULL). Postgres does not support ADD CONSTRAINT IF NOT EXISTS,
-- so we guard with a DO block that swallows duplicate_object.
DO $$
BEGIN
    ALTER TABLE businesses
        ADD CONSTRAINT businesses_price_range_chk
        CHECK (price_range IS NULL OR price_range IN ('$', '$$', '$$$', '$$$$'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
