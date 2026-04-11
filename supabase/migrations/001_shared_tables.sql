-- ============================================================
-- Migration 001: Shared Tables
-- Run this in your Supabase SQL Editor
-- These tables are used by ALL THREE products
-- ============================================================

-- Note for C#/.NET developers:
-- This is standard PostgreSQL. Your SQL skills transfer directly.
-- "uuid_generate_v4()" = like NEWID() in SQL Server
-- "now()" = like GETDATE() in SQL Server
-- "jsonb" = a JSON column with indexing support (no equivalent in standard SQL Server)

-- Enable UUID generation (Supabase enables this by default)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users ────────────────────────────────────────────────────────────────────
-- Supabase Auth manages this table automatically.
-- You don't create users here — Supabase does it when they sign up.
-- Your other tables reference auth.users(id) as a foreign key.

-- ─── Business profiles ────────────────────────────────────────────────────────
CREATE TABLE businesses (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,    -- e.g. 'salon', 'restaurant', 'plumber'
    address      TEXT,
    city         TEXT,
    province     TEXT DEFAULT 'ON',
    phone        TEXT,
    email        TEXT,
    hours        JSONB,            -- {"monday": "9-5", "tuesday": "9-5", ...}
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- One business per user (for now — can expand to multi-location later)
CREATE UNIQUE INDEX businesses_user_id_idx ON businesses(user_id);

-- ─── Subscriptions ────────────────────────────────────────────────────────────
CREATE TYPE subscription_product AS ENUM ('reviews', 'bookings', 'startup');
CREATE TYPE subscription_status  AS ENUM ('trialing', 'active', 'past_due', 'canceled');

CREATE TABLE subscriptions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    product      subscription_product NOT NULL,
    stripe_id    TEXT UNIQUE,      -- Stripe subscription ID
    status       subscription_status DEFAULT 'trialing',
    plan_tier    TEXT,             -- 'starter', 'pro', etc.
    trial_ends   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- A business can subscribe to each product once
CREATE UNIQUE INDEX subscriptions_business_product_idx ON subscriptions(business_id, product);

-- ─── Conversations (shared AI conversation log) ────────────────────────────────
CREATE TABLE conversations (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    product      subscription_product NOT NULL,
    messages     JSONB DEFAULT '[]',   -- Array of {role, content, timestamp}
    status       TEXT DEFAULT 'active',
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- ─── Notifications log ────────────────────────────────────────────────────────
CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'whatsapp');

CREATE TABLE notifications (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    channel      notification_channel NOT NULL,
    recipient    TEXT NOT NULL,    -- Email address or phone number
    subject      TEXT,
    body         TEXT,
    status       TEXT DEFAULT 'pending',  -- pending, sent, failed
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ─── Row Level Security (RLS) ─────────────────────────────────────────────────
-- This is Supabase's equivalent of applying user-based WHERE clauses automatically.
-- Once enabled, a logged-in user can ONLY see their own data — the database enforces it.
-- C#/.NET equivalent: imagine if Entity Framework automatically added
--   .Where(x => x.UserId == currentUser.Id) to every query.

ALTER TABLE businesses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Users can only see their own business
CREATE POLICY "Users see own business" ON businesses
    FOR ALL USING (auth.uid() = user_id);

-- Users can see subscriptions for their own business
CREATE POLICY "Users see own subscriptions" ON subscriptions
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

-- Users see their own conversations
CREATE POLICY "Users see own conversations" ON conversations
    FOR ALL USING (
        business_id IN (SELECT id FROM businesses WHERE user_id = auth.uid())
    );

-- ─── Auto-update updated_at timestamps ───────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
