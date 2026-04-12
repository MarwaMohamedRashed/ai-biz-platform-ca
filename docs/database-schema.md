# LeapOne — Database Schema

## Overview

PostgreSQL via Supabase. Row-Level Security (RLS) is enabled on every table — users can only read and write their own data. All tables use UUID primary keys.

Migrations are in `supabase/migrations/` and must be run in order in the Supabase SQL Editor.

---

## Migration 001 — Shared Tables (all products)

### `profiles`
Extends `auth.users`. Created automatically by trigger on sign-up.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | References auth.users(id) |
| full_name | TEXT | From Google OAuth or sign-up form |
| avatar_url | TEXT | Google profile photo URL |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

**Decision:** Email and phone are NOT duplicated here — always read from `auth.users`. Keeping a single source of truth prevents sync bugs.

---

### `businesses`
One business per user in Phase 1.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | References auth.users(id) |
| name | TEXT | Business display name |
| type | TEXT | e.g. 'salon', 'restaurant', 'plumber' |
| address | TEXT | |
| city | TEXT | |
| province | TEXT | Default: 'ON' |
| phone | TEXT | |
| email | TEXT | Business contact email |
| hours | JSONB | `{"monday": "9-5", ...}` |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

**Unique index:** `(user_id)` — one business per user. Remove in Phase 2 for multi-location.

---

### `business_members`
Team member access — defined now, activated in Phase 2.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| user_id | UUID FK | References auth.users(id) |
| role | ENUM | owner / admin / member |
| title | TEXT | Job title (e.g. "Manager", "Receptionist") |
| invited_at | TIMESTAMPTZ | |
| accepted_at | TIMESTAMPTZ | NULL until invitation accepted |

**Decision:** `title` lives here, not in `profiles`. A person can have different titles at different businesses.

---

### `subscriptions`
One row per product per business.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| product | ENUM | reviews / bookings / startup |
| stripe_id | TEXT | Stripe Subscription ID or Payment Intent ID |
| status | ENUM | trialing / active / past_due / canceled |
| plan_tier | TEXT | 'starter', 'pro', etc. |
| trial_ends | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

**Unique index:** `(business_id, product)` — one subscription per product.

---

### `conversations`
Shared AI chat log across all three products.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| product | ENUM | reviews / bookings / startup |
| messages | JSONB | Array of `{role, content, timestamp}` |
| status | TEXT | 'active', 'archived' |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

---

### `notifications`
Log of all notifications sent to business owners.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| channel | ENUM | email / sms / whatsapp |
| recipient | TEXT | Email address or phone number |
| subject | TEXT | Email subject line |
| body | TEXT | Full message body |
| status | TEXT | pending / sent / failed |
| regarding_type | TEXT | 'review', 'booking', 'payment' |
| regarding_id | UUID | ID of the related record |
| sent_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

**Decision:** `regarding_type + regarding_id` is a polymorphic reference. Allows querying "all notifications about this review" without separate join tables for each product.

---

## Migration 002 — Phase 1 Review Responder

### `review_connections`
Stores the Google Business Profile OAuth connection for a business.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| google_place_id | TEXT | Google's Place ID |
| google_account_name | TEXT | Display name (e.g. "Main St Salon") |
| access_token_secret | UUID | Vault secret reference — NOT the token |
| refresh_token_secret | UUID | Vault secret reference — NOT the token |
| token_expires_at | TIMESTAMPTZ | |
| last_sync | TIMESTAMPTZ | Last time reviews were pulled |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

**Decision:** Tokens are stored in Supabase Vault. These UUID columns are pointers to vault secrets, not the tokens themselves. Reading a token requires: `SELECT decrypted_secret FROM vault.decrypted_secrets WHERE id = <secret_id>`.

---

### `reviews`
Reviews synced from Google Business Profile API.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| google_review_id | TEXT UNIQUE | Google's internal review ID |
| author | TEXT | Reviewer display name |
| rating | INTEGER | 1–5, CHECK constraint |
| text | TEXT | Full review text |
| review_date | TIMESTAMPTZ | When the review was written on Google |
| status | ENUM | pending / responded / ignored |
| synced_at | TIMESTAMPTZ | When we last pulled this review |

**Indexes:** `(business_id, status)`, `(business_id, rating)` — supports filter tabs and star-rating charts.

---

### `review_responses`
AI draft + owner-approved final response for each review.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| review_id | UUID FK UNIQUE | References reviews(id) — one response per review |
| ai_draft | TEXT | Original AI-generated response |
| final_response | TEXT | What the owner approved (may be edited) |
| status | ENUM | draft / approved / posted / failed |
| edit_ai_score | NUMERIC(3,2) | 0.0–1.0 AI quality score of owner's edit |
| edit_ai_warnings | TEXT[] | e.g. `{"Response sounds defensive"}` |
| edit_reviewed_at | TIMESTAMPTZ | When AI finished reviewing the edit |
| posted_at | TIMESTAMPTZ | When posted to Google |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto-updated by trigger |

**Decision:** When an owner edits the AI draft before approving, the app sends the edited version back to the AI for a quality check. The AI scores it and flags any issues (too long, sounds defensive, mentions competitor). The owner sees this feedback before posting. This adds value beyond simple approve/reject.

---

### `review_insights`
AI-generated analysis of a business's own review history. Shown in the chat briefing.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| period_start | DATE | |
| period_end | DATE | |
| avg_rating | NUMERIC(3,2) | Average star rating in this period |
| review_count | INTEGER | Total reviews in this period |
| response_rate | NUMERIC(5,2) | % of reviews responded to |
| common_topics | TEXT[] | Recurring themes from review text |
| sentiment_score | NUMERIC(3,2) | -1.0 (very negative) to 1.0 (very positive) |
| summary | TEXT | Plain English summary for the owner |
| created_at | TIMESTAMPTZ | |

**Important:** This table only analyzes this business's own review data. It does NOT compare to other LeapOne customers.

---

### `market_benchmarks`
Competitor comparison data from public APIs (Google Places, Yelp). NOT customer data.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK | References businesses(id) |
| data_source | TEXT | 'google_places' or 'yelp' — always public APIs |
| competitor_name | TEXT | |
| competitor_place_id | TEXT | External place ID |
| avg_rating | NUMERIC(3,2) | |
| review_count | INTEGER | |
| response_rate | NUMERIC(5,2) | % of reviews with responses (public data) |
| fetched_at | TIMESTAMPTZ | |

**Decision:** Comparing a business's performance against public competitors is a high-value feature (enterprise tools charge $300–500/mo for this). `data_source` must always be a public API — cross-comparing LeapOne customers' private data would be a conflict of interest and is not allowed.

---

## RLS Policy Summary

| Table | Policy |
|---|---|
| profiles | User sees/edits own profile only |
| businesses | User sees/edits own business only |
| business_members | User sees own membership rows |
| subscriptions | User sees subscriptions for own business |
| conversations | User sees conversations for own business |
| notifications | User sees notifications for own business |
| review_connections | User sees connections for own business |
| reviews | User sees reviews for own business |
| review_responses | User sees responses for own reviews |
| review_insights | User sees insights for own business |
| market_benchmarks | User sees benchmarks for own business |

---

## Future Migrations (Phase 2+)

- `003_phase2_bookings.sql` — services, bookings, availability, booking_conversations
- `004_phase3_startup_guide.sql` — business_plans, requirements, checklist_items
- Team access: expand RLS policies to check `business_members` when Phase 2 team feature is built
