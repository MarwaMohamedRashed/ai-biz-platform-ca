# Billing — Technical Documentation

## Overview

LeapOne uses Stripe for subscription billing. The integration uses Stripe Checkout (hosted payment page) and the Stripe Customer Portal (self-serve management). Subscriptions are tracked in the Supabase `subscriptions` table, kept in sync via webhooks.

---

## Architecture

```
Browser
  └─ POST /api/v1/billing/checkout-session  → FastAPI → Stripe API
                                            ← { url }
  └─ window.location.href = url  →  Stripe Checkout (hosted)
                                  ↓ (on complete)
                         Stripe webhook → POST /api/v1/billing/webhook
                                        → Supabase subscriptions table
```

---

## Database Schema

Table: `subscriptions`

| Column | Type | Description |
|---|---|---|
| `id` | uuid | Primary key |
| `business_id` | uuid | FK → businesses.id |
| `stripe_customer_id` | text (unique) | Stripe Customer object (`cus_...`) |
| `stripe_subscription_id` | text (unique) | Stripe Subscription (`sub_...`) |
| `status` | text | `trialing` · `active` · `past_due` · `canceled` |
| `plan_tier` | enum | `starter` · `pro` · `business` |
| `current_period_end` | timestamptz | When the current billing period renews |
| `trial_end` | timestamptz | When the 14-day trial expires |
| `cancel_at_period_end` | boolean | User clicked Cancel; access remains until `current_period_end` |

Unique partial index `subscriptions_one_active_per_business` enforces one active/trialing/past_due row per business.

---

## API Endpoints

All endpoints are under `/api/v1/billing/` and require a Bearer token (Supabase JWT).

### `POST /checkout-session`

Creates a Stripe Checkout session for the given plan.

**Request body:**
```json
{ "plan": "starter" | "pro", "locale": "en" | "fr" }
```

**Response:**
```json
{ "url": "https://checkout.stripe.com/..." }
```

**What it does:**
1. Fetches the business from DB via the authenticated user
2. Looks up existing `stripe_customer_id` from `subscriptions`
3. If none exists, creates a Stripe Customer and saves the `cus_...` ID
4. Selects the correct Stripe Price ID based on `plan`
5. Creates a Checkout Session with 14-day trial, `metadata.business_id` on both session and subscription
6. Returns the hosted Checkout URL — frontend does `window.location.href = url`

**After checkout:** Stripe redirects to `/{locale}/dashboard/plan/success`
**On cancel:** Stripe redirects to `/{locale}/dashboard/plan/cancel`

---

### `POST /webhook`

Receives Stripe events. **No auth required** — verified via HMAC signature (`stripe-signature` header + `STRIPE_WEBHOOK_SECRET`).

Register this URL in Stripe Dashboard → Developers → Webhooks.

**Handled events:**

| Event | Action |
|---|---|
| `checkout.session.completed` | Upserts subscription row: sets `status=trialing`, `plan_tier`, `stripe_subscription_id`, `stripe_customer_id` |
| `customer.subscription.updated` | Updates `status`, `plan_tier`, `current_period_end`, `cancel_at_period_end` — covers trial→paid conversion, plan changes, renewals |
| `invoice.payment_failed` | Sets `status=past_due` |
| `customer.subscription.deleted` | Sets `status=canceled` |

**Signature verification:** Uses `stripe.Webhook.construct_event()`. Returns 400 on invalid payload or bad signature. Stripe retries on non-2xx responses.

---

### `POST /portal-session`

Opens the Stripe Customer Portal for the authenticated user to manage their subscription (cancel, change plan, update payment method).

**Request body:**
```json
{ "locale": "en" | "fr" }
```

**Response:**
```json
{ "url": "https://billing.stripe.com/..." }
```

Returns 404 if no Stripe Customer is found for this business (user hasn't subscribed yet).

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `STRIPE_SECRET_KEY` | Stripe secret API key | `sk_test_...` or `sk_live_...` |
| `STRIPE_PRICE_STARTER` | Price ID for Starter plan | `price_abc123` |
| `STRIPE_PRICE_PRO` | Price ID for Pro plan | `price_def456` |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret | `whsec_...` |
| `WEB_BASE_URL` | Frontend base URL (no trailing slash) | `https://leapone.ca` |
| `BILLING_ENABLED` | Gates audits behind subscription check | `false` (dev) · `true` (prod) |

---

## Billing Gate

When `BILLING_ENABLED=true`, two AEO endpoints require an active subscription:

- `POST /api/v1/aeo/audit`
- `POST /api/v1/aeo/generate-content`

The check calls `get_active_subscription(business_id)` which queries for a row with `status IN ('trialing', 'active')`. If none is found, returns `HTTP 402 Payment Required`.

The frontend (`AeoAuditCard.tsx`) detects the 402 and shows an upgrade prompt with a link to `/dashboard/plan`.

**To enable in production:** Set `BILLING_ENABLED=true` in Railway environment variables.
**Default in dev:** `false` — audits run freely during development.

---

## Frontend Components

### `PlanPage.tsx`
Client component. Renders the three pricing tiers with real Upgrade buttons.

- **Upgrade button:** POSTs to `/billing/checkout-session` → redirects to Stripe Checkout
- **Manage subscription button:** POSTs to `/billing/portal-session` → redirects to Stripe Portal (shown only when `hasSubscription=true`, i.e., a Stripe Customer exists)
- Receives `currentTier`, `planStatus`, `hasSubscription`, `locale` from the server component

### `plan/page.tsx` (server component)
Fetches `subscriptions` table for `status`, `plan_tier`, `stripe_customer_id`. Passes `hasSubscription=!!stripe_customer_id` to `PlanPage`.

### `plan/success/page.tsx`
Static confirmation page shown after Stripe Checkout completes. Has a "Back to dashboard" link.

### `plan/cancel/page.tsx`
Shown when user clicks "Back" on the Stripe Checkout page. Links back to `/dashboard/plan`.

### `SettingsPage.tsx`
Settings page has a compact "Plan & Billing" row with a "Manage subscription →" button that triggers the portal session.

### `AeoAuditCard.tsx`
Handles `HTTP 402` from `/aeo/audit` by showing an upgrade prompt inline instead of a generic error.

---

## Local Testing with Stripe CLI

```bash
# 1. Install CLI
# Windows: download from https://github.com/stripe/stripe-cli/releases

# 2. Login
stripe login

# 3. Forward events to local server
stripe listen --forward-to http://localhost:8000/api/v1/billing/webhook

# 4. Copy the webhook signing secret printed by the CLI
# Add it to api/.env as STRIPE_WEBHOOK_SECRET=whsec_...

# 5. Test a checkout (in another terminal)
stripe trigger checkout.session.completed
```

**Test cards:**
| Card | Outcome |
|---|---|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 9995` | Card declined (tests payment_failed) |
| Any future date | Any CVC, any postal code |

---

## Webhook Registration (Production)

1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://your-railway-url/api/v1/billing/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the `whsec_...` signing secret → add to Railway env as `STRIPE_WEBHOOK_SECRET`

---

## Subscription Lifecycle

```
New user signs up
      ↓
Clicks "Upgrade to Starter/Pro"
      ↓
POST /checkout-session → Stripe Checkout (14-day trial)
      ↓
checkout.session.completed webhook fires
      → subscriptions row: status=trialing, plan_tier=starter/pro
      ↓
14 days later — first payment
  ├─ Success → customer.subscription.updated → status=active
  └─ Failure → invoice.payment_failed → status=past_due
      ↓
User clicks "Manage subscription" → Stripe Customer Portal
  ├─ Cancel → cancel_at_period_end=true → customer.subscription.updated
  │           At period end: customer.subscription.deleted → status=canceled
  └─ Change plan → customer.subscription.updated → plan_tier updated
```
