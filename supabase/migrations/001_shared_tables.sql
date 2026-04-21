-- ============================================================
-- Migration 001: Shared Tables
-- Run this in your Supabase SQL Editor
-- These tables are used by ALL THREE products
-- ============================================================

-- Enable UUID generation (Supabase enables this by default)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Profiles ────────────────────────────────────────────────────────────────
-- Extends auth.users (managed by Supabase Auth).
-- Created automatically by trigger when a user signs up.
-- We do NOT duplicate email here — always read from auth.users.
CREATE TABLE profiles (
    id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name    TEXT,
    avatar_url   TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- Auto-create a profile row when a new user signs up
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ─── Businesses ───────────────────────────────────────────────────────────────
-- user_id = the user who created the business (used for INSERT policy only).
-- Access control for SELECT/UPDATE uses business_members, not user_id directly.
-- This means one user can own or be a member of multiple businesses.
-- A trigger (handle_new_business) auto-creates the owner row in business_members.
CREATE TABLE businesses (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,    -- e.g. 'salon', 'restaurant', 'plumber'
    address      TEXT,
    city         TEXT,
    country      TEXT DEFAULT 'Canada',
    province     TEXT DEFAULT 'ON',
    phone        TEXT,
    email        TEXT,
    hours        JSONB,            -- {"monday": "9-5", "tuesday": "9-5", ...}
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- NOTE: No unique index on user_id — one user can own multiple businesses.
-- (unique index was removed by migration 003_multi_business_support.sql)

-- ─── Business Members ────────────────────────────────────────────────────────
-- Source of truth for who has access to which business.
-- Created automatically by trigger when a business is inserted.
-- Phase 2: used for team invitations (admin/member roles).
-- title: the person's role within the business (e.g. "Owner", "Manager", "Receptionist")
CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member');

CREATE TABLE business_members (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role         member_role NOT NULL DEFAULT 'member',
    title        TEXT,             -- Job title within the business
    invited_at   TIMESTAMPTZ DEFAULT now(),
    accepted_at  TIMESTAMPTZ,
    UNIQUE (business_id, user_id)
);

-- ─── Subscriptions ────────────────────────────────────────────────────────────
CREATE TYPE subscription_product AS ENUM ('reviews', 'bookings', 'startup');
CREATE TYPE subscription_status  AS ENUM ('trialing', 'active', 'past_due', 'canceled');

CREATE TABLE subscriptions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    product      subscription_product NOT NULL,
    stripe_id    TEXT UNIQUE,      -- Stripe subscription or payment intent ID
    status       subscription_status DEFAULT 'trialing',
    plan_tier    TEXT,             -- 'starter', 'pro', etc.
    trial_ends   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- A business can subscribe to each product once
CREATE UNIQUE INDEX subscriptions_business_product_idx ON subscriptions(business_id, product);

-- ─── Conversations ────────────────────────────────────────────────────────────
-- Shared AI conversation log across all products.
-- messages: array of {role: "user"|"assistant", content: "...", timestamp: "..."}
CREATE TABLE conversations (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id  UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    product      subscription_product NOT NULL,
    messages     JSONB DEFAULT '[]',
    status       TEXT DEFAULT 'active',
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- ─── Notifications ────────────────────────────────────────────────────────────
-- Log of every notification sent to business owners.
-- regarding_type + regarding_id: polymorphic reference to what triggered the notification.
-- Example: regarding_type='review', regarding_id=<review UUID>
CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'whatsapp');

CREATE TABLE notifications (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id      UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    channel          notification_channel NOT NULL,
    recipient        TEXT NOT NULL,       -- Email address or phone number
    subject          TEXT,
    body             TEXT,
    status           TEXT DEFAULT 'pending',  -- pending, sent, failed
    regarding_type   TEXT,                -- 'review', 'booking', 'payment', etc.
    regarding_id     UUID,                -- ID of the related record
    sent_at          TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX notifications_business_id_idx    ON notifications(business_id);
CREATE INDEX notifications_regarding_idx      ON notifications(regarding_type, regarding_id);

-- ─── Row Level Security ───────────────────────────────────────────────────────
-- Once enabled, Supabase automatically filters every query by the logged-in user.
-- Users can only read/write their own data — enforced at the database level.

ALTER TABLE profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE businesses       ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own profile" ON profiles
    FOR ALL USING (auth.uid() = id);

-- Businesses: INSERT uses user_id check; SELECT/UPDATE use business_members
-- (supports multi-business — a user can own or belong to many businesses)
CREATE POLICY "Users can create businesses" ON businesses
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Members can view their businesses" ON businesses
    FOR SELECT USING (
        id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

CREATE POLICY "Owners can update their businesses" ON businesses
    FOR UPDATE USING (
        id IN (
            SELECT business_id FROM business_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

CREATE POLICY "Users see own memberships" ON business_members
    FOR ALL USING (auth.uid() = user_id);

-- Downstream tables: access via business_members (not businesses.user_id)
CREATE POLICY "Users see own subscriptions" ON subscriptions
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own conversations" ON conversations
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own notifications" ON notifications
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

-- ─── Auto-update updated_at timestamps ───────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
