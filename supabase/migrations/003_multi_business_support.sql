-- ============================================================
-- Migration 003: Multi-Business Support
-- Removes single-business constraint and updates RLS policies
-- to use business_members as the access control source of truth.
--
-- Safe to run even if businesses table was just created.
-- Run this in your Supabase SQL Editor.
-- ============================================================

-- ─── Step 1: Remove the one-business-per-user constraint ─────────────────────
DROP INDEX IF EXISTS businesses_user_id_idx;


-- ─── Step 2: Auto-create owner row in business_members on business insert ─────
-- When a business is created during onboarding, this trigger automatically
-- creates the owner membership row. No need to do it manually in app code.
CREATE OR REPLACE FUNCTION handle_new_business()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO business_members (business_id, user_id, role)
    VALUES (NEW.id, NEW.user_id, 'owner');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_business_created ON businesses;

CREATE TRIGGER on_business_created
    AFTER INSERT ON businesses
    FOR EACH ROW EXECUTE FUNCTION handle_new_business();


-- ─── Step 3: Replace businesses RLS policies ─────────────────────────────────
-- Old policy checked user_id directly — only worked for single-business.
-- New policies split INSERT (use user_id) from SELECT/UPDATE (use business_members).

DROP POLICY IF EXISTS "Users see own business" ON businesses;

-- Any authenticated user can create a business (user_id must match their own)
CREATE POLICY "Users can create businesses" ON businesses
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Read access: based on business_members membership (works for 1 or many businesses)
CREATE POLICY "Members can view their businesses" ON businesses
    FOR SELECT USING (
        id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

-- Update/delete: only owners and admins
CREATE POLICY "Owners can update their businesses" ON businesses
    FOR UPDATE USING (
        id IN (
            SELECT business_id FROM business_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );


-- ─── Step 4: Update downstream RLS policies to use business_members ───────────
-- Old policies went through businesses.user_id.
-- New policies go directly through business_members — supports multi-business.

DROP POLICY IF EXISTS "Users see own subscriptions" ON subscriptions;
CREATE POLICY "Users see own subscriptions" ON subscriptions
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "Users see own conversations" ON conversations;
CREATE POLICY "Users see own conversations" ON conversations
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );

DROP POLICY IF EXISTS "Users see own notifications" ON notifications;
CREATE POLICY "Users see own notifications" ON notifications
    FOR ALL USING (
        business_id IN (SELECT business_id FROM business_members WHERE user_id = auth.uid())
    );
