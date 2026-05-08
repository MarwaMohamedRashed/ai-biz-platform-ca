# LeapOne Billing — Business Documentation

## What We Sell

LeapOne offers subscription plans for Canadian small businesses that want to improve their visibility on AI search engines (ChatGPT, Perplexity, Google AI Overview).

---

## Pricing Tiers

| Plan | Price | Target Customer |
|---|---|---|
| **Starter** | $19 CAD/month | Single-location businesses that want to establish AI search presence |
| **Pro** | $49 CAD/month | Growth-focused businesses that want weekly monitoring and deeper reporting |
| **Agency** | $149 CAD/month | Marketing agencies managing multiple client locations |

All prices are in Canadian dollars. Billing is monthly, recurring.

---

## Free Trial

Every new customer gets a **14-day free trial** — no credit card required at signup. The trial begins when they start a Checkout session (click "Upgrade"). After 14 days, Stripe automatically charges the plan price and the subscription becomes active.

If payment fails at trial end, the subscription moves to `past_due` status. The customer has a grace period before access is revoked.

---

## What Each Plan Includes

### Starter — $19/month
- Full AEO readiness audit (once per month, auto-scheduled)
- 5-pillar score with per-signal breakdown
- Top 3 competitor benchmarking
- Competitor weak-point analysis (AI-powered)
- Score-change email alerts
- AI content generator (GBP description, FAQ, schema markup)
- 6-month score history
- 1 business location

### Pro — $49/month
Everything in Starter, plus:
- Weekly audits (instead of monthly)
- Action tracking (mark a recommendation done → re-checks that pillar)
- Downloadable PDF audit report
- Weekly email digest
- 12-month score history
- Priority support

### Agency — $149/month
Everything in Pro, plus:
- Up to 10 business locations
- White-label PDF reports
- Agency dashboard (all clients in one view)
- Dedicated account manager

---

## Customer Flow

### Signing Up
1. Customer creates a free account at leapone.ca
2. Completes their business profile (name, city, type)
3. Runs a free AEO audit during the trial (no gate in trial)
4. Clicks "Upgrade" on the Plan & Billing page
5. Chooses Starter or Pro → redirected to Stripe hosted checkout
6. Enters payment info → 14-day trial begins
7. After trial ends, first charge is processed automatically

### Managing Their Subscription
Customers can manage everything through the **Stripe Customer Portal**, accessible from:
- **Plan & Billing page** → "Manage subscription"
- **Settings page** → "Manage subscription"

From the portal, customers can:
- Cancel (access continues until end of current billing period)
- Switch plans (Starter ↔ Pro, effective next billing cycle)
- Update payment method
- Download invoices and receipts

### Cancellation
- Customer cancels via the Stripe Customer Portal
- Access continues until the end of their current paid period
- No refunds for partial months (standard SaaS terms)
- After period ends, audit endpoint returns an upgrade prompt

---

## Revenue Model

- **Monthly recurring revenue (MRR)** — all plans are monthly subscriptions
- No annual billing currently (can be added later for ~20% discount)
- No per-seat pricing — one subscription covers the business owner and any team members they share access with
- Agency plan revenue scales with referrals to other business owners

### Target MRR milestones
| Customers | MRR (all Starter) | MRR (mixed) |
|---|---|---|
| 50 | $950 | ~$1,500 |
| 100 | $1,900 | ~$3,000 |
| 500 | $9,500 | ~$15,000 |

---

## Billing Infrastructure

### Stripe
All payment processing is handled by Stripe (PCI DSS Level 1 certified). LeapOne never stores credit card numbers. Stripe handles:
- Payment processing
- Subscription lifecycle (trials, renewals, failures)
- Invoicing and receipts
- Fraud detection

### What LeapOne Stores
The Supabase `subscriptions` table stores:
- Stripe Customer ID and Subscription ID (references to Stripe objects)
- Subscription status (`trialing`, `active`, `past_due`, `canceled`)
- Plan tier (`starter`, `pro`, `business`)
- Trial end date and current period end date

No payment information is stored in our database.

---

## Refund and Cancellation Policy

- **Free trial:** No charge during the 14-day trial. Cancel before trial ends = no charge.
- **Monthly subscriptions:** No refunds for partial months. Access continues until period end after cancellation.
- **Dispute handling:** Managed through Stripe's dispute resolution process.

---

## Upgrade Path

The current roadmap does not include Agency plan Stripe checkout (it shows "Contact us"). Starter and Pro are fully self-serve. Agency sales are handled manually for now.

---

## Key Dates

| Event | Date |
|---|---|
| Stripe integration built | 2026-05-05 |
| Billing gate enabled (target) | After Stripe testing is complete |
| Annual billing option | Phase 4 roadmap |
| Agency self-serve checkout | Phase 4 roadmap |

---

## Testing Before Going Live

Before enabling the billing gate in production (`BILLING_ENABLED=true`):

1. Complete Phase 2 — register the webhook URL in Stripe dashboard
2. Run a test checkout with card `4242 4242 4242 4242` — confirm subscription row is created in Supabase
3. Test cancellation via Customer Portal — confirm `status` updates to `canceled`
4. Test payment failure with card `4000 0000 0000 9995` — confirm `status` updates to `past_due`
5. Test the 402 gate: set `BILLING_ENABLED=true` locally, cancel a subscription, try to run an audit — should show the upgrade prompt

See `docs/billing-technical.md` for full testing instructions.
