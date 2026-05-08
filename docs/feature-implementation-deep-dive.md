# LeapOne — Built Functionality, Implementation & Competitive Notes

**Date:** 2026-05-07
**Audience:** Founder / sales conversations / competitive comparisons
**Companion docs:**
[feature-inventory-current.md](feature-inventory-current.md) (what exists, by surface) ·
[honest-evaluation-content-feature.md](honest-evaluation-content-feature.md) (vs competitors)

This doc goes deeper than the inventory: for each shipped feature, it explains
**what it does**, **how it's implemented** (libraries, APIs, file pointers), and
**what makes it competitively notable**. Use it when you're comparing LeapOne
against another tool's marketing page — the "implementation" column lets you
verify whether their claim matches their actual build.

---

## Quick stack reference

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | FastAPI 0.115 | Async-first, OpenAPI auto-spec, type-hinted |
| Async HTTP | `httpx` 0.27 | Used for SerpApi, Perplexity, Resend, website fetches |
| LLM SDKs | `openai` 1.45, `anthropic` 0.40, `google-generativeai` 0.7 | Provider-pluggable via `core/ai_engine.py`; ChatGPT audit hard-pinned to OpenAI |
| Validation | Pydantic 2.9 | Request bodies, response shapes, env config |
| Data | Supabase (Postgres + Auth + RLS) `supabase-py` 2.29 | Single source of truth, RLS at row level |
| Payments | `stripe` 10.9 | Checkout + Portal + webhooks |
| Email | `resend` 2.3 | Score-change alerts |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | `next-intl` for EN/FR, Vercel hosted |
| Analytics | Google `gtag.js` on landing | None on dashboard yet (privacy-aware default) |
| Concurrency primitive | `asyncio.gather` | Single most leveraged tool — every multi-API operation runs in parallel |

---

## 1. AEO Audit Engine

### What it does
Scores a business on a 0–100 readiness scale across five pillars by querying
ChatGPT, Perplexity, Google AI Overview, Google Knowledge Graph, Google Maps
local pack, organic results, and the customer's own website — in parallel —
then aggregates the answers into a transparent breakdown.

### Five-pillar score model
Code: [api/aeo/router.py](../api/aeo/router.py) — `calculate_score()`

| Pillar | Max | Signals |
|---|---|---|
| Google Business Profile (GBP) | 25 | KG presence, rating, category, contact details |
| Reviews & Reputation | 22 | Volume tiers (50+ / 10–49) + rating tiers (≥4.5★ / ≥4.0★) |
| Website & Schema | 20 | HTTP 200, LocalBusiness schema, FAQ schema |
| Local Search Presence | 15 | Local pack rank + organic-result presence |
| AI Citations | 18 | ChatGPT 6 + Perplexity 6 + Google AI 6 (equal-weight redistribution) |

### Implementation highlights

- **Three AI engines in parallel via `asyncio.gather`** — adding ChatGPT to the
  pipeline added zero wall-clock time because the gather already waits on the
  longest of the three.
  ```python
  perplexity_result, google_result, chatgpt_result = await asyncio.gather(
      run_perplexity_multi(...), run_google_multi(...), run_chatgpt_multi(...)
  )
  ```
- **3-query aggregation per engine.** Each engine runs three local-search
  query templates (`Best <type> in <city>`, `<type> near <city>`, `Top <type>
  <city> <province>`); business is "mentioned" if any of the three hits.
- **Country-aware SerpApi calls.** `gl` / `hl` derived from the business's
  country (`COUNTRY_TO_GL` map). Province/state expanded to full names because
  SerpApi's geocoder accepts those reliably; abbreviations don't.
- **Dedicated OpenAI client for ChatGPT pillar.** The `_audit_openai`
  `AsyncOpenAI` instance is hard-coded so the audit always queries OpenAI
  regardless of `AI_PROVIDER` env (which can be Claude/Gemini for content
  generation). Cost: ~$0.001 per 3-query ChatGPT pass with `gpt-4o-mini` at
  `temperature=0.0` (deterministic).
- **Place_id resolution for Google Maps reviews.** SerpApi returns numeric
  CIDs in `local_results` but `google_maps_reviews` requires ChIJ-format ids
  — we run a `google_maps` engine lookup to resolve the ChIJ id when needed.
- **Review recency check.** Most-recent review date is parsed from SerpApi's
  relative-date strings ("3 days ago", "a month ago") into approximate
  `days_since_last`.
- **Website schema detection** (today). Substring scan for `"@type":"LocalBusiness"`
  and `"@type":"FAQPage"`. **Roadmap:** replace with `extruct` for full JSON-LD
  parsing — eliminates an entire class of false positives.

### Cost per audit (May 2026)
| Call | Approximate cost |
|---|---|
| 3× ChatGPT (`gpt-4o-mini`) | ~$0.001 |
| 3× Perplexity (`sonar`) | ~$0.006 |
| 4× SerpApi (3 query + 1 name lookup) | ~$0.020 |
| 1× SerpApi `google_maps_reviews` (recency) | ~$0.005 |
| Website check (httpx) | $0 |
| **Total** | **~$0.032** per audit |

### Competitive notes
- **Most direct AEO/GEO competitors run 1 engine per query.** We run 3 in
  parallel without a time penalty. Cross-engine consistency is a verifiable
  signal — a citation in 3/3 engines is meaningfully different from 1/3.
- **Otterly Lite ($29/mo, 15 prompts/month total).** Our $19/mo includes
  unlimited audits today (rate limiting in F9). Different product shape — they
  track prompt drift over time, we benchmark the audit per business.
- **Most tools at our price point don't run all 5 pillars.** BrightLocal
  ($39–59) does GBP + citation tracking but not AI citations. HubSpot AEO
  ($50/mo) does AI citations across 3 engines but no local-pack/GBP scoring.
  We're the only tool at the SMB price tier that does both halves of the
  equation.

---

## 2. Deterministic Schema.org JSON-LD Generator

### What it does
Generates valid, industry-specific `LocalBusiness`-tree JSON-LD schema for the
customer's website — no LLM, no hallucinated phone numbers, no missing fields,
guaranteed valid by construction.

### How it's implemented
Code: [api/aeo/schema_builder.py](../api/aeo/schema_builder.py)
(258 lines, pure-Python, no network calls).

Three-stage resolution for `@type`:
1. Exact match against onboarding type values (`restaurant` → `Restaurant`,
   `cafe` → `CafeOrCoffeeShop`, etc.) — **5 mappings**.
2. Keyword-pattern match against free-form `customType` strings — **47+ regex
   patterns** covering medical, food, beauty, fitness, trades, auto,
   professional services, retail, hospitality, daycare, etc.
3. Fallback to generic `LocalBusiness`.

The `build_schema(business, description)` function:
- Reads only stored profile fields (name, image_url, phone, price_range,
  street_address, postal_code, city, province, country, hours).
- Emits ONLY keys that have data — no `null` fields cluttering output.
- Builds nested `PostalAddress` only when at least one address field is
  present.
- Converts our `{"monday": "09:00-17:00", "sunday": "closed"}` JSONB into
  Schema.org's `OpeningHoursSpecification[]` array (closed days dropped per
  Schema.org convention).
- Outputs `addressCountry: "Canada"` (full name) — verified against Google
  Rich Results Test on 2026-05-06.

`find_missing_required_fields(business)` returns the list of profile fields
the user still needs to fill in for Google rich-result eligibility (`name`,
`image_url`, `street_address`, `city`, `phone`). Drives the amber
"Complete your profile" CTA on the Content tab.

### Why deterministic, not LLM-generated
Three concrete bugs the previous LLM-based generator produced before we
replaced it (real production output, kept as test cases):
- `addressCountry: "CA"` (Google requires "Canada" or full name)
- `servesCuisine: []` for a Physiotherapy clinic (invented field)
- Generic `LocalBusiness` for every vertical (not Schema.org subtype)

The deterministic builder is **structurally incapable** of producing those
errors. Test coverage: 26 pytest cases in
[api/tests/test_schema_builder.py](../api/tests/test_schema_builder.py).

### Competitive notes
- **Rank Math (840+ types) is the standard for raw schema-type breadth** —
  we cover 50ish, focused on SMB-relevant verticals.
- **AISchemaGen, Digispot, etc. are also LLM-based.** Our deterministic
  approach is safer for production sites where wrong schema is worse than
  none.
- **SMB AEO competitors (Otterly, AthenaHQ, Profound, HubSpot) don't
  generate schema at all** — they only track AI citations. Our schema
  generator is a feature they can't easily match without building it.
- **Schema.org subtype precision matters more after Feb 2026.** Google's core
  update prioritizes "verified entities" with industry-specific types
  (`Dentist`, `Physiotherapy`, `Plumber`) over generic `LocalBusiness`. Our
  type resolver wins this signal automatically.

---

## 3. AI Content Generator (Path A)

### What it does
For each business, produces a complete content kit on demand:
- 3 platform-tailored descriptions (Website 300–400 words, Google Business
  Profile ≤700 chars, Yelp 200–250 words)
- 1 social media bio (≤150 chars, hard-capped)
- 10 FAQ Q&As (40–80 words per answer), grounded in real "People Also Ask"
  questions from Google
- Deterministic `LocalBusiness` schema (above)
- Deterministic `FAQPage` schema wrapping the Q&A list
- All available in EN or FR
- Ready-to-paste copy buttons that wrap JSON-LD in proper `<script>` tags

### How it's implemented
Code: [api/aeo/router.py](../api/aeo/router.py) `generate_content()` endpoint
(~150 lines after refactor). Frontend:
[apps/web/components/dashboard/ContentPage.tsx](../apps/web/components/dashboard/ContentPage.tsx)

Five LLM calls in parallel via `asyncio.gather`:
1. Website description
2. GBP description (capped at 700 chars via `_truncate_at_word`)
3. Yelp description
4. Social bio (capped at 150 chars)
5. FAQ JSON (10 items, 40–80 words/answer, system prompt enforces JSON-only)

`_build_content_prompts(language, base_context, services, paa_questions)`
returns per-platform prompts with:
- **Services injection** — every description prompt includes the user's
  comma-separated services with "Mention these services specifically: ..."
- **PAA grounding** — when `paa_questions` is non-empty, the FAQ prompt
  prefixes "Use these real customer questions as inspiration: …".
- **Fully bilingual** — EN and FR prompt templates for all 5 calls.

`_fetch_people_also_ask(business_type, city, country, language)` queries
SerpApi with `q="<business_type> in <city>"`, `engine=google`, locale-aware
`gl`/`hl`, returns up to 8 questions from `related_questions`. Best-effort:
empty list on any failure, FAQ generation falls back to LLM-only.

`_validate_content(descriptions, faq, social_bio)` returns warnings (not
blockers) for: short website, missing/oversized GBP, too few FAQs, oversized
social bio. Warnings render as a non-blocking amber Note on the UI.

`build_faq_schema(faq_items)` produces a Schema.org `FAQPage` JSON-LD by
deterministic transform — same safety guarantee as the LocalBusiness builder.

### Storage
[supabase/migrations/016_aeo_content_multi_platform.sql](../supabase/migrations/016_aeo_content_multi_platform.sql)
adds 4 columns to `aeo_content`: `descriptions JSONB`, `faq_schema TEXT`,
`language TEXT`, `paa_questions JSONB`. Legacy `description` column kept
populated for backward compat.

### Cost per generation
| Call | Approximate cost |
|---|---|
| 4× LLM descriptions | ~$0.004 |
| 1× LLM FAQ (~2500 tokens out) | ~$0.005 |
| 1× SerpApi PAA | ~$0.005 |
| **Total** | **~$0.014** per Regenerate click |

### Competitive notes
- **Writesonic GEO ($49–499/mo) leads on volume but is monolithic** — one
  description per generation, not platform-tailored. Our per-platform variants
  are differentiated.
- **HubSpot AEO ($50/mo) does NOT include content generation.** Pure
  monitoring product.
- **PAA-grounded FAQ generation is genuinely rare at any price point.** Most
  tools either generate FAQ from a generic prompt or pull questions verbatim
  from a separate scrape — we ground LLM output in real user search behaviour
  for the customer's exact category + city.
- **EN/FR variant generation** is differentiated against US tools generally.
  Most don't ship a French setting at all.

---

## 4. Competitor Intelligence

Three sub-features. F11 (benchmarking) and F12 (weak-point mining) ship
already. F11 polish (citation gaps) added 2026-05-07.

### 4.1 — Top-3 competitor benchmarking
Code: `extract_competitors`, `score_competitor`, `match_competitor_ai_citations`
in [api/aeo/router.py](../api/aeo/router.py).

**What:** For each audit, the top 3 same-country competitors (pulled from
SerpApi local pack) get scored on the same 5-pillar formula. Apples to apples.

**How:**
- `extract_competitors` walks the local pack (max 5), filters by same country
  and ideally same region, ranks by Google's local position.
- `score_competitor` runs the full pillar formula on each — including AI
  citation matching across all 3 engines (free — pure text scan over data we
  already paid SerpApi for).
- `check_competitor_websites` fetches all 3 competitor sites in parallel
  via `httpx.AsyncClient`.
- Country-aware fallback: if fewer than 3 same-country competitors, pad with
  cross-border ones (badged as "🌍 Different country" in UI).

**Frontend:** Side-by-side `ComparisonTable` (YOU + top-3 in columns) +
per-competitor rows with "you +X" pillar deltas.

### 4.2 — Competitor weak-point mining (sentiment analysis)
Code: `_analyze_competitor_weaknesses` in
[api/aeo/router.py](../api/aeo/router.py) (~150 lines).

**What:** For each competitor with a Google place_id, fetches up to 60 of
their most recent reviews and runs an LLM sentiment pass to extract:
- `themes`: list of `{theme, count, example}` sorted by count
- `avg_competitor_rating`
- `opportunity_summary`: plain-language strategic recommendation

**How:**
- SerpApi `google_maps_reviews` per competitor (parallel via `asyncio.gather`)
- LLM prompt asks for JSON output with theme/count/example shape
- Cheap LLM (Claude Haiku-tier acceptable) since it's pure analysis on
  text we already have

**Why this is rare:** Competitor review sentiment is something marketing
agencies charge $2k/month to do manually. Most AEO tools don't touch the
competitor side at all.

### 4.3 — Citation gap analysis (new 2026-05-07)
Code: `_detect_directory_presence` in
[api/aeo/router.py](../api/aeo/router.py).
Test coverage: 21 pytest cases.

**What:** Walks the organic results from each Google audit query, identifies
which directory listings (Yelp, BBB, Yellow Pages, TripAdvisor, Healthgrades,
Houzz, Thumbtack, etc.) appear, and computes which directories competitors
are listed on that the user is not. Frontend renders this with "Claim listing →"
deep links to the right vendor signup page.

**How:**
- 22 known directory domains in `DIRECTORY_DOMAINS` (Canadian + US +
  international + niche health/professional)
- Each organic result's URL is bucketed to its directory label via
  endswith-matching for subdomains
- Business presence is detected via lenient name matching (first 3 words,
  case-insensitive) against the title + snippet of each result
- Aggregated across all 3 Google queries
- Output: `{user: [...], competitors: {name: [...]}, gaps: [...]}`
- Cost: $0 (pure text scan over already-fetched SerpApi data)

**Frontend:** `CitationGapSection` on the Competitors page. Two-part display:
green "✓ You appear on" pill list + amber "Gaps — competitors here, you not"
list with claim links.

### Competitive notes
- **No SMB-tier AEO tool we're aware of does competitor benchmarking +
  weak-point mining + citation gap analysis under $99/mo.** Athena and Profound
  do enterprise versions of pieces of this.
- **The combination is the moat.** Citation gaps drive concrete actions
  ("claim a Yelp profile"), weak-point mining gives strategic angles
  ("emphasize 'no wait' since 14 of their reviews complain"), benchmarking
  gives the comparative dashboard. Together → a Monday-meeting-ready
  competitive briefing per business per month.

---

## 5. "Why this score?" — radical transparency layer

### What it does
Every score and recommendation is auditable. Customers can see exactly which
queries we ran, what each engine actually said, and how each pillar was
calculated.

### Implementation surfaces
- **Audit card "Why this score?" drawer** — each pillar listed with
  signals + points awarded. AI Citations section shows three engine dots
  (ChatGPT/Perplexity/Google AI) with the actual snippet when mentioned.
- **`raw_results` JSONB on every audit row** — every query's actual answer
  preserved, viewable via Supabase or the UI drawer. Schema:
  ```
  perplexity, google, chatgpt, website, recommendations,
  competitors, competitor_insights, citation_gaps
  ```
- **Public methodology page** at [apps/web/app/[locale]/methodology/page.tsx](../apps/web/app/[locale]/methodology/page.tsx)
  — the entire formula in plain language. EN + FR. No login required.
- **ChatGPT training-data note** — when a business isn't cited by ChatGPT,
  we explicitly explain that ChatGPT uses training data (not live search),
  so improvements take 6–12 months. Sets honest expectations vs Perplexity
  (real-time).

### Competitive notes
- Most SMB tools hide the formula behind "proprietary AI scoring".
  Transparent scoring is differentiation when SMBs have been burned by
  black-box SEO tools.
- HubSpot AEO Grader does sentiment + presence-quality scoring with
  written interpretation — closest to our transparency. Their methodology
  isn't on a public page though.

---

## 6. Recommendations Engine

### What it does
For each weak pillar, generates concrete actions with impact estimates +
difficulty ratings.

### Implementation
Code: `generate_recommendations()` in
[api/aeo/router.py](../api/aeo/router.py).

- **Conditional generation.** Only weak pillars produce recs. A perfect-25/25
  GBP score will not generate a GBP recommendation.
- **Per-pillar impact + difficulty** so users prioritize. Impact in points,
  difficulty in `easy / medium / hard`.
- **ChatGPT-specific recommendation text** explains the training-data
  timeline (6–12 months) and gives concrete actions: claim Yelp/TripAdvisor/
  Yellow Pages, get a Chamber of Commerce listing, get a local press mention,
  add an FAQ page.
- **All Python-generated** today (not LLM). Pros: deterministic, cheap, no
  hallucination. Cons: less personalized.

### Roadmap
Action tracking — when a user marks a recommendation done, re-check that
pillar within minutes. Closes the engagement loop.

---

## 7. Score history + monthly auto-audit

### What it does
- Time-series chart of every audit's score on the dashboard
- Monthly auto-audit re-runs every business via cron
- Email alert when score moves ±10 points

### Implementation
- `ScoreHistoryChart` component reads from `aeo_audits` table.
- `/api/v1/aeo/cron-monthly` endpoint protected by `Authorization: Bearer
  <CRON_SECRET>`. Iterates every business, runs `_run_audit_core`, persists,
  fires email alerts on score deltas. Designed for Vercel Cron / external
  scheduler.
- `send_score_change_alert(email, name, prev, curr)` via Resend API.
- Resilient — per-business try/except, one failed business doesn't kill the
  job.

### Competitive notes
- Continuous monthly tracking with email alerts at $19/mo is undercut by
  almost no one. BrightLocal Track ($39) is the closest local-SEO equivalent,
  but it doesn't track AI citations.

---

## 8. Authentication, RLS, multi-business support

### What it does
Standard email+password auth via Supabase, with row-level security making
cross-tenant data leaks impossible at the database level.

### Implementation
- `supabase.auth` for sessions, password reset, email verification
- `business_members` join table — a user can own/admin/member multiple
  businesses
- All RLS policies in [supabase/migrations/001_shared_tables.sql](../supabase/migrations/001_shared_tables.sql)
  use `business_members` (not `businesses.user_id`) for SELECT/UPDATE so
  the multi-business model works without policy rewrites
- `IdleTimeout` component logs the user out after inactivity
- All authenticated API endpoints depend on `get_current_user`; failure
  → 403, never reaches business logic

### Competitive notes
- **RLS at the DB level is genuinely safer than middleware-only auth**
  — even an SQL injection in our code couldn't leak across tenants.
- Multi-business architecture is roughed in but not surfaced (single-business
  UI today). Schema is ready when we ship the agency tier.

---

## 9. Stripe Billing Integration

### What it does
Self-serve checkout + customer portal for the Starter ($19) and Pro ($49)
tiers. Agency is contact-sales. Audit endpoints can be gated via env flag.

### Implementation
Code: [api/billing/router.py](../api/billing/router.py) (174 lines).

Endpoints:
- `POST /billing/checkout-session` — creates a Stripe Checkout Session,
  returns the URL. Locale-aware return URLs (`?locale=fr`).
- `POST /billing/portal-session` — creates a Stripe Customer Portal session,
  returns the URL. Same locale handling.
- `POST /billing/webhook` — HMAC signature verified via
  `stripe.Webhook.construct_event`. Handles:
  - `checkout.session.completed`
  - `customer.subscription.updated` (status, plan_tier, current_period_end,
    cancel_at_period_end)
  - `customer.subscription.deleted` (status='canceled')
  - `invoice.payment_failed` (status='past_due')

The `_price_to_tier(price_id)` helper maps Stripe price IDs to our enum
(`'starter' | 'pro'`). The `_get_stripe_customer_id(business_id)` helper uses
`.limit(1)` (not `.single()`) to safely handle businesses with no
subscription row yet.

Audit gate via `BILLING_ENABLED=true` env. When enabled, `/audit` and
`/generate-content` return HTTP 402 if no active subscription. Frontend
handles 402 and shows an upgrade CTA linking to `/dashboard/plan`.

### Competitive notes
- Stripe-standard implementation, no special advantage here. The point of
  shipping it cleanly is enabling billing without it dragging launch
  schedule.

---

## 10. Reviews module (built but Google API blocked)

### What it does (today)
- Read reviews via SerpApi (mocked from audit data right now)
- AI-draft a response per review with tone/length/language matching customer
  settings
- Bulk auto-draft + edit + approve flow
- Strengths/weaknesses extraction from review corpus
  ([migrations/006](../supabase/migrations/006_review_insights_strengths_weaknesses.sql))

### What it does once Google API approval comes through (~July 2026)
- Read reviews live from Google
- Post approved responses back to Google
- Two-way sync of review status

### Implementation
Code: [api/reviews/router.py](../api/reviews/router.py) (~284 lines).

- 5 endpoints (list, generate, regenerate, auto-draft, approve)
- AI-engine adapter pattern (`core/ai_engine.py`) lets us switch
  Claude/Gemini/OpenAI per `AI_PROVIDER` env without code changes
- Tone preference is a free-form prompt suffix; tested against `casual`,
  `professional`, `playful`
- Language matching: `match_reviewer` parses the review's language via
  the LLM, replies in same; `english`/`french` overrides

### Competitive notes
- Once Google API unlocks, this becomes a Phase 3 product. For now, the
  scaffolding's all there.

---

## 11. Bilingual EN/FR

### What it does
Full UI translation for the dashboard and landing page. Content generation
supports French variants. Audit queries respect locale.

### Implementation
- `next-intl` for the React side. Translation files: `apps/web/messages/{en,fr}.json`.
- Server-side `getLocale()` for SSR pages.
- Locale-aware Stripe redirect URLs (`?locale=fr`).
- LLM prompts switched at request time via `language: 'en' | 'fr'` field on
  `GenerateContentRequest`.
- SerpApi calls use locale-derived `hl=fr` for French queries.

### Competitive notes
- **Real differentiation in the Canadian market.** Quebec SMBs are an
  underserved segment. Most US AEO tools don't ship FR at all.

---

## 12. Operational + reliability

### Cron, alerts, error handling
- `/cron-monthly` is idempotent and resilient — try/except per business.
- Resend failures are logged but don't crash audits.
- All external API calls have timeouts (`httpx.AsyncClient(timeout=10.0)`).
- Per-query failures inside `asyncio.gather` are caught and recorded as
  zero-mention rather than aborting the audit.

### Test infrastructure
- `api/tests/` (added 2026-05-07) — 91 pytest cases covering schema builder,
  validators, citation gaps, content helpers. Pure-Python, no auth needed.
- Run: `pytest tests/ -v` (~2.2s).

### What's deliberately missing today (gaps you should know about)
| Feature | Why deferred |
|---|---|
| AI-crawler analytics (GPTBot/PerplexityBot/ClaudeBot traffic) | Requires server logs / pixel / Cloudflare API. Multi-week feature, no SerpApi shortcut. |
| Per-tier audit rate limiting | Not yet wired; once `BILLING_ENABLED=true`, Starter is unbounded. F9 sprint. |
| `extruct` library for schema parsing on customer websites | Substring scan today — modest accuracy improvement when upgraded. |
| Free public AEO grader at `leapone.ca/grade` | Counter to HubSpot's funnel. F10. |
| Action tracking (mark recommendation as done → re-check pillar) | Engagement-loop polish. F13. |
| PDF export of audit reports | Distribution / agency-friendly. F10–F13. |
| Multi-location / agency tier UI | Schema ready (`business_members`), UI not built. F14. |
| Sentry / error tracking | F9 pre-launch. |

---

## How to use this doc against a competitor's marketing page

For each feature they advertise:

1. **Find the matching section here.** Most claims are covered.
2. **Check the "Implementation" detail.** If they say "AI-powered audit" and
   the implementation here says "3 engines in parallel via asyncio.gather, $0.032/audit"
   — that's a more honest answer than they're giving.
3. **Check the "Competitive notes."** Each one calls out where we genuinely
   beat the competition vs where we're commodity.
4. **If they have something not in this doc**, add it to
   [aeo-competitive-gaps.md](aeo-competitive-gaps.md) Part 9. That's the
   running gap list.

If you find anyone advertising:
- Deterministic schema generation with industry-specific Schema.org subtypes
- Competitor weak-point mining (review sentiment + complaint themes)
- Citation gap analysis with claim-listing deep links
- 5-pillar audit + 3 AI engines + bilingual EN/FR

…at sub-$50/mo, send me their pricing page — I'll re-evaluate. As of today,
no SMB-tier tool combines all four.
