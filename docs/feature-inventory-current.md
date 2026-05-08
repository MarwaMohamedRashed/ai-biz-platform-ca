# LeapOne — Built Feature Inventory (as-of 2026-05-06)

**Purpose:** A factual snapshot of what is *actually shipped in code today*. Use this as the comparison sheet when researching competitors. No roadmap items, no aspirations — only what exists in the repo right now.

**How to read this:** Every feature listed below has working code. Items in **Part 9 — Not yet built** are explicitly *not* shipped (use that section to spot competitor advantages).

---

## Part 1 — Product positioning (what we sell today)

LeapOne is an **Answer Engine Optimization (AEO) platform for Canadian small businesses**. A user signs up, fills in a business profile, and gets:

- A scored audit (0–100) of how their business appears across AI search engines and local search.
- Plain-language recommendations to improve the score.
- Generated content (description, FAQ, schema markup, social bio) to act on those recommendations.
- A monthly auto-audit that re-scores them, with email alerts if the score moves significantly.

**Pricing tiers (v1 plan picker):** Starter $19/mo, Pro $49/mo. Agency tier was removed from the v1 plan picker on 2026-05-08 — it requires multi-location UI + white-label reports + agency dashboard work that isn't in scope for v1. Translation strings are kept in `en.json`/`fr.json` for re-introduction in Phase 2. Stripe-integrated, billing gate optional via `BILLING_ENABLED` env flag.

**Languages:** English + French (full UI translations, including dashboard).

**Geography:** Canada-first — phone formats, postal codes, provinces, country defaults.

---

## Part 2 — User-facing pages (frontend surfaces)

| Route | Page | What it does |
|---|---|---|
| `/` | Landing page | Public marketing page, EN/FR, with Open Graph + LocalBusiness schema, Google Analytics. |
| `/[locale]/methodology` | Methodology page | Public explanation of how the score is calculated. Trust-building page. |
| `/[locale]/(auth)/signup` | Signup | Email/password + email verification. |
| `/[locale]/(auth)/login` | Login | Standard. |
| `/[locale]/(auth)/forgot-password` + `reset-password` + `auth/reset-callback` | Password reset flow | Full email-link reset. |
| `/[locale]/(auth)/verify-email` | Verify email | Click-through verification. |
| `/[locale]/onboarding` | Business onboarding | Multi-step form: name, type, city, services, website. Saves to `businesses` and creates `business_members` row. |
| `/[locale]/dashboard` | Dashboard home | Top-level audit card + insights overview. |
| `/[locale]/dashboard/insights` | Insights | Audit results, score breakdown, recommendations. |
| `/[locale]/dashboard/competitors` | Competitors | Top-3 local competitors + own reputation card (pulled from SerpApi). |
| `/[locale]/dashboard/content` | Content generator | Description, FAQ, schema markup (JSON-LD), social bio. **Currently being rebuilt — see `path-a-content-rebuild-plan.md`.** |
| `/[locale]/dashboard/reviews` | Reviews | Review list + AI-drafted responses (built but Google API approval pending until July 2026). |
| `/[locale]/dashboard/profile` | Profile | User profile (name, avatar). |
| `/[locale]/dashboard/settings` | Settings | Business info form, notification settings, plan & billing card with Manage Subscription link. |
| `/[locale]/dashboard/plan` | Plan/pricing | Stripe Checkout entry point. Tiers + upgrade buttons + manage button. |
| `/[locale]/dashboard/plan/success` + `/cancel` | Post-checkout pages | Stripe redirects land here. |

---

## Part 3 — AEO audit engine (the core product)

### 3.1 — Score model
- **Total score: 0–100**, broken into 5 pillars:
  - **GBP (Google Business Profile)** — 25 pts
  - **Reviews** — 22 pts
  - **Website** — 20 pts
  - **Local Search** — 15 pts
  - **AI Citations** — 18 pts (split 6+6+6 across ChatGPT, Perplexity, Google AI Overview)

### 3.2 — Audit pipeline (per `_run_audit_core`)
For each audit, the backend runs **in parallel via `asyncio.gather`**:
- **3 ChatGPT queries** via OpenAI `gpt-4o-mini` (temperature 0.0)
- **3 Perplexity queries** via Perplexity `sonar`
- **3 Google AI Overview lookups** via SerpApi
- **1 GBP / local search lookup** via SerpApi (`local_results` + `knowledge_graph`)
- **1 reviews snapshot** via SerpApi `google_maps_reviews`
- **1 website check** via `httpx` (status, response time, schema-tag substring scan)

Audit duration: ~10–15s (parallel). Cost: ~$0.027/audit.

### 3.3 — Query templates
Three templates per audit (`build_queries`):
1. `Best [business type] in [city], [province]`
2. `[business type] near [city]`
3. `Top [business type] [city] [province]`

Aggregation: business is "mentioned" if matched in **any** of the 3 queries.

### 3.4 — Audit results stored
Every audit writes a row to `aeo_audits`:
- Total score + per-pillar breakdown
- `chatgpt_mentioned` + `chatgpt_snippet`
- `perplexity_mentioned` + `perplexity_snippet`
- `google_ai_mentioned` + `google_ai_snippet`
- Full `raw_results` JSONB (every query's answer for transparency)

### 3.5 — Recommendations engine
`generate_recommendations()` produces a ranked action list per audit. Each rec has: `pillar`, `impact_pts`, `difficulty` (easy/medium/hard), `title`, `body`, `actions[]`.

Recommendations are conditional — only produced for pillars where the score is below threshold.

### 3.6 — Score history + alerts
- **Score history chart** on the dashboard (line chart of all past audits).
- **Score-change email alerts** via Resend when score moves ≥10 points (built; Resend domain verification is the only blocker).
- **Monthly auto-audit** via `/cron-monthly` endpoint — re-runs every business's audit, writes new row, triggers alerts on movement.

### 3.7 — Audit transparency
- "Why this score?" drawer on the audit card: shows per-pillar breakdown + the actual snippets from each AI engine.
- "ChatGPT training data" note explains why ChatGPT improvements take 6–12 months.
- Public `/methodology` page explains the entire formula.

---

## Part 4 — Competitor intelligence (current state)

What's built today:
- **Top-3 competitor scoring.** For each user audit, we pull `local_results` from SerpApi and score the top 3 competitors using the same formula.
- **Own reputation card.** Shows the user's GBP rating, review count, business type, and whether they show up in AI citations.
- **Per-competitor AI mention scan.** `match_competitor_ai_citations()` scans ChatGPT/Perplexity/Google AI answers for competitor names and flags which engines cite which competitor.
- **Competitors page** in the dashboard renders the table.

**Not yet built (deferred to F11):** Side-by-side pillar comparison table, competitor weak-point mining (review sentiment), citation gap analysis (which directories competitors are on that we are not).

---

## Part 5 — Content generation

`POST /api/v1/aeo/generate-content` returns 4 pieces of content:

| Content | What it is | Status |
|---|---|---|
| **Description** | 150–200 word business description | Working (basic) |
| **FAQ** | 5 question/answer pairs | Working but **no `FAQPage` JSON-LD wrapper** |
| **Schema markup** | LocalBusiness JSON-LD | **Being rebuilt** (see Path A plan) — current version generic, no validation |
| **Social bio** | 150-char bio | Working |

All four are generated via `ai_engine.generate()` (Claude/Gemini/OpenAI depending on `AI_PROVIDER`). Saved to `aeo_content` table.

**Known limitations** (documented in `honest-evaluation-content-feature.md`):
- FAQ not grounded in real "People Also Ask" queries
- One generic description (no per-platform variants)
- No FR generation
- Schema generator has hallucination risk and missing fields

---

## Part 6 — Billing (Stripe)

Built and tested:
- **Checkout flow** — `/billing/checkout-session` creates Stripe Checkout, redirects user.
- **Customer Portal** — `/billing/portal-session` redirects user to Stripe-hosted self-serve portal (cancel, change card, etc.).
- **Webhook handler** — `/billing/webhook` processes `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`.
- **Subscription state** stored in `subscriptions` table: `status` (trialing/active/past_due/canceled), `plan_tier`, `current_period_end`, `cancel_at_period_end`, `stripe_customer_id`.
- **Billing gate** — `BILLING_ENABLED=true` env flag forces `/audit` and `/generate-content` to return HTTP 402 for users without an active subscription. Frontend detects 402 and shows an upgrade prompt linking to `/dashboard/plan`.
- **Locale-aware return URLs** — Stripe redirects respect `?locale=fr`.

Tiers (configured via Stripe Price IDs in env):
- Starter — $19/mo (1 audit/day per F6 plan, billing-gated)
- Pro — $49/mo (3 audits/day, future)
- ~~Agency — contact sales~~ — removed from v1 plan picker (deferred to Phase 2)

**Not yet wired:** per-tier daily audit rate-limits (Phase 6 of original billing plan).

---

## Part 7 — Reviews module (Phase 3, partially shipped)

Built but **gated on Google API approval (reapply July 2026)**:
- Review list UI (`/dashboard/reviews`)
- AI-drafted response generation per review
- Review insights (sentiment, strengths/weaknesses extracted via AI — `006_review_insights_strengths_weaknesses.sql`)
- Bulk auto-draft endpoint
- Approve/edit response endpoint
- Google Auth OAuth flow (`/google_auth/connect` + callback)

The pipeline works against mock data; live posting blocked until Google approves the OAuth scope.

---

## Part 8 — Operational features

- **Monthly cron** — `/api/v1/aeo/cron-monthly` re-audits every business. Triggered externally (Vercel Cron or Railway scheduler — wiring still pending in `vercel.json`).
- **Score-change email alerts** via Resend on ±10pt movement.
- **Multi-business support** — a user can own multiple businesses; access via `business_members` table.
- **Row-Level Security (RLS)** on `businesses`, `subscriptions`, `aeo_audits`, etc. Members-only access enforced in Postgres.
- **Idle timeout** — frontend logs the user out after inactivity.
- **i18n** — full EN/FR translations for all dashboard surfaces.

---

## Part 9 — NOT yet built (so you can spot competitor advantages)

These are real gaps. Use this list when researching what competitors offer that we don't:

### Content / schema
- Deterministic schema generator with industry-specific Schema.org subtypes (Path A — in progress)
- FAQ schema (`FAQPage` JSON-LD) wrapping
- Per-platform descriptions (website / GBP / Yelp / social)
- "People Also Ask" grounding for FAQ generation
- French content generation
- "Test in Google Rich Results" deep link
- Address / postal code / image / hours / price range fields in profile (migration 015 written, form not yet updated)

### Competitive intelligence
- Side-by-side pillar comparison (you vs top 3)
- Competitor review sentiment + complaint-theme mining
- Citation gap analysis (which directories competitors are on that we are not)
- Real-time competitor alerts ("competitor X just got 12 new reviews")

### Top-of-funnel / marketing
- Free public AEO grader at `leapone.ca/grade?biz=...` (HubSpot-equivalent lead gen)
- 3 case studies on landing page
- Sample audit PDF download
- Score guarantee ("if your score doesn't move in 60 days, you don't pay")

### Engagement loop
- Action tracking ("mark recommendation as done" → re-check that pillar)
- Weekly email digest
- In-app activity feed

### Tracking depth
- Prompts-over-time tracking (Otterly-style — show how mention rate for a query changes weekly)
- AI-crawler analytics (GPTBot / PerplexityBot / ClaudeBot traffic from server logs)
- Share-of-voice dashboards (Athena/Profound style)

### Distribution / scale
- PDF / shareable-link audit report
- Multi-location dashboard (schema supports it; UI does not)
- White-label / agency tier (managed-by-X views, custom-branded reports)

### Reliability / production
- Railway Dockerfile + deploy config
- Resend sender-domain verification (DNS)
- `vercel.json` cron schedule
- Audit rate limiting (per-tier, per-day)
- Privacy policy + terms of service pages
- Sentry error tracking

### Schema generator commodity features
- 100+ Schema.org subtype support (Rank Math has 840)
- Validation (Pydantic + extruct + Rich Results Test)
- `<script type="application/ld+json">` wrapper on copy

---

## Part 10 — Tech stack reference (for technical comparison)

- **Backend:** Python 3.11 + FastAPI + asyncio. Hosted target: Railway.
- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind. Hosted on Vercel (`leapone.ca` live).
- **Database:** Supabase PostgreSQL (with Auth, RLS, JSONB).
- **AI providers (configurable):** OpenAI (always for ChatGPT audit), Anthropic Claude, Google Gemini.
- **Search APIs:** SerpApi (Google local results, Google AI Overviews, Maps reviews), Perplexity (`sonar`).
- **Payments:** Stripe (Checkout + Customer Portal + Webhooks).
- **Email:** Resend (domain verification pending).
- **i18n:** `next-intl`.

---

## Use this doc for competitor research

Suggested workflow when looking at a competitor:

1. Read their feature list / pricing page.
2. For each feature they advertise, check Parts 2–8 here. If we have it → we match. If we don't → check Part 9 — is it a known gap? If so, where does it sit on `aeo-competitive-gaps.md`?
3. For each feature *we* have that *they* don't advertise → that's a positioning angle. The bilingual EN/FR + Canadian focus + cross-engine audit at sub-$50 + transparency / methodology page is the current set.
4. If a competitor has something not in Part 9 → it's a new gap. Add it.

---

## File pointers (for code archeology)

- Audit core: [api/aeo/router.py](api/aeo/router.py) (`_run_audit_core`, `calculate_score`, `generate_recommendations`)
- Stripe: [api/billing/router.py](api/billing/router.py)
- Frontend dashboard: [apps/web/components/dashboard/](apps/web/components/dashboard/)
- Migrations: [supabase/migrations/](supabase/migrations/)
- Methodology page (public): [apps/web/app/[locale]/methodology/page.tsx](apps/web/app/[locale]/methodology/page.tsx)
- Honest content-feature evaluation: [docs/honest-evaluation-content-feature.md](docs/honest-evaluation-content-feature.md)
- Competitive gaps: [docs/aeo-competitive-gaps.md](docs/aeo-competitive-gaps.md)
- Path A plan: [docs/path-a-content-rebuild-plan.md](docs/path-a-content-rebuild-plan.md)
