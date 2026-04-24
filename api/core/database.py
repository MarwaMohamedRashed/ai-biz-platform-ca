"""
Database — Supabase Client Setup
==================================
Supabase is PostgreSQL with an API layer.
Your SQL skills transfer directly — same queries, same schema design.

C#/.NET equivalent:
    This file is like your DbContext in Entity Framework, but lighter.
    Supabase gives you two clients:
    - supabase_client: For auth-aware queries (respects row-level security)
    - supabase_admin:  Service role — bypasses RLS. Use for backend-only ops.
"""

import os
from supabase import create_client, Client

SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY    = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise EnvironmentError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file"
    )

# ─── Service role client (backend use only) ───────────────────────────────────
# Use this for operations that should bypass row-level security
# e.g. syncing Google reviews, sending notifications, admin tasks
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ─── Helper: get a user-scoped client from a JWT ─────────────────────────────
def get_user_client(jwt_token: str) -> Client:
    """
    Returns a Supabase client that respects row-level security for this user.
    Use this for any user-facing query so users can only see their own data.

    C#/.NET equivalent: passing the user's claims principal to a scoped DbContext
    """
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.auth.set_session(access_token=jwt_token, refresh_token="")
    return client


# ─── Common query helpers ─────────────────────────────────────────────────────

async def get_business_by_id(business_id: str) -> dict | None:
    """Fetch a business profile. Returns None if not found."""
    result = supabase_admin.table("businesses").select("*").eq("id", business_id).single().execute()
    return result.data


async def get_business_by_user(user_id: str) -> dict | None:
    """Fetch the business profile belonging to a user."""
    result = supabase_admin.table("businesses").select("*").eq("user_id", user_id).single().execute()
    return result.data


async def get_active_subscription(business_id: str) -> dict | None:
    """
    Check if a business has an active subscription.
    Bundled tier model — any active/trialing subscription grants access.
    """
    result = (
        supabase_admin.table("subscriptions")
        .select("*")
        .eq("business_id", business_id)
        .in_("status", ["trialing", "active"])
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
