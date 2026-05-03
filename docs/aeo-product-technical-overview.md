# LeapOne AEO — Technical Overview

**Last updated:** 2026-05-01
**Audience:** Engineers, security review, due diligence
**Length:** ~10 minute read

---

## 1. System architecture (one diagram in words)

```
       Vercel Cron (1st of month, 09:00 UTC)
                  │
                  ▼
    ┌──────────────────────────────┐
    │  Next.js  (apps/web)          │
    │  - SSR dashboard              │
    │  - Cron proxy route           │
    │  - Supabase Auth (browser)    │
    └─────────────┬─────────────────┘
                  │  HTTPS + JWT
                  ▼
    ┌──────────────────────────────┐
    │  FastAPI   (api/)             │
    │  - /api/v1/aeo/*              │
    │  - /api/v1/reviews/*          │
    │  - /api/v1/insights/*         │
    └──┬───────────┬───────────┬────┘
       │           │           │
       ▼           ▼           ▼
 Perplexity    SerpApi     Supabase   Resend    Anthropic
 (AI search)  (Google +   (Postgres  (Email)   (Claude —
              maps reviews) + Auth +            type norm,
                            RLS + RT)           content gen)
```

**Two deployable units:**
- `apps/web` → Next.js 15 app, deployed to Vercel
- `api/` → FastAPI app, deployed to Railway (Dockerfile pending)

**One database:** Supabase Postgres, accessed by both services. RLS is enforced for user-facing queries. The FastAPI service uses the service-role key for backend-only operations (cron audits, admin tasks).

---

## 2. The audit pipeline — how a score is produced

`api/aeo/router.py` ⇒ `_run_audit_core(business)` orchestrates the following 4 phases:

### Phase 1 — Query construction
For a business in `(name, type, city, province, website)`, build 3 query variants:

```python
QUERY_TEMPLATES = [
    "best {type} in {city}, {province}",
    "{type} near {city}",
    "top {type} {city} {province}",
]
```

If the raw business type is outside `KNOWN_TYPES = {"restaurant", "salon", "retail", "plumber", "cafe"}`, Claude (haiku-4-5) is called once to translate it to a clean English search phrase (e.g. "studio de photographie" → "photography studio"). This avoids running searches in the wrong language.

### Phase 2 — Multi-engine signal collection (concurrent in production logic, sequential in code today)

For each of the 3 queries, the system makes:
- **1 Perplexity `sonar` chat-completion call** → returns natural-language answer; we substring-match the business name to detect citation.
- **1 SerpApi Google search call** → one call returns 4 distinct signals: Google AI Overview text, `local_results` (Maps 3-pack), `organic_results`, and (rarely for category queries) `knowledge_graph`.

Result aggregation rule: **any-of-3** — if any of the 3 query variants returns a hit, the signal fires. Reasoning: a single category query has high run-to-run variance; 3 variants stabilize the score.

If the 3 category queries all fail to return review/rating data (common — `knowledge_graph` only fires on name searches), the system makes **a 4th SerpApi call** with the exact business name + city. This is the "name lookup" fallback added to fix the historical "Reviews=0 even when reviews exist" bug.

If the knowledge graph returns a `place_id`, we make **one more SerpApi call** to the `google_maps_reviews` engine to fetch the most recent review's date. Stale reviews (>90 days) trigger a recommendation.

Total API calls per audit, worst case:
- Perplexity: 3
- SerpApi (Google): 3 + 1 name lookup = 4
- SerpApi (maps_reviews): 0 or 1
- Claude: 0 or 1
- Website: 1 HTTP GET (httpx, 10s timeout)

**Cost per audit: ~$0.06–$0.09** (SerpApi at ~$0.015/call dominates).

### Phase 3 — Website check
`httpx.AsyncClient` GETs the user's website with a `User-Agent` of `"Mozilla/5.0 (LeapOne AEO Audit Bot)"`, follows redirects, has a 10-second timeout. On any non-200 / network / SSL error, the website is marked unreachable.

If it loads, we lowercase the HTML and substring-search for two markers:
- `"@type":"localbusiness"` (LocalBusiness schema)
- `"@type":"faqpage"` (FAQ schema)

This is intentionally crude — substring matching, not real JSON-LD parsing. It catches 95% of cases. Replacing with the `extruct` library is on the roadmap (Sprint F10).

### Phase 4 — Scoring + recommendations
`calculate_score()` applies the deterministic 5-pillar formula:

```
GBP (max 25):
  +10  has_gbp                         (knowledge_graph found OR in local_pack)
  + 5  effective_rating > 0
  + 5  has GBP category                (kg.type or has_gbp as proxy)
  + 5  has phone OR website OR business.website

Reviews (max 22):
  +12  effective_reviews >= 50
  + 6  effective_reviews >= 10
  +10  effective_rating >= 4.5
  + 5  effective_rating >= 4.0

Website (max 20):
  + 8  website reachable (HTTP 200)
  + 6  LocalBusiness JSON-LD present
  + 6  FAQPage JSON-LD present

Local Search (max 15):
  +10  in Google Maps 3-pack
  + 5  in organic results

AI Citation (max 18):
  +10  cited by Perplexity
  + 8  cited by Google AI Overview

TOTAL = sum of pillars (max 100)
```

`generate_recommendations()` is a long if/else that maps each negative signal to one of 16 pre-written recommendations, each with a fixed `impact` value. The list is sorted by impact descending and returned.

---

## 3. Endpoints (contract)

All endpoints are mounted under `/api/v1/aeo`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/audit` | JWT | Run a fresh audit for the caller's business; insert into `aeo_audits`; alert if Δ ≥ 10 pts |
| GET  | `/recommendations/{business_id}` | JWT | Read most recent audit's recommendations + score |
| POST | `/cron-monthly` | `Bearer ${CRON_SECRET}` | Re-audit every business in the DB; insert + alert |
| POST | `/generate-content` | JWT | Generate description, FAQ, schema, bio via Claude; save to `aeo_content` |

JWT auth is via `Depends(get_current_user)` in `api/core/auth.py` — Supabase token validation. The cron endpoint uses a shared secret in the `Authorization` header.

---

## 4. Cron / monthly auto-audit

```
Vercel Cron (GET /api/cron/monthly-audit, monthly schedule)
  └─> apps/web/app/api/cron/monthly-audit/route.ts
        - validates Authorization: Bearer ${CRON_SECRET}
        - POSTs to ${NEXT_PUBLIC_API_URL}/api/v1/aeo/cron-monthly
        - returns the FastAPI response straight back
              └─> /api/v1/aeo/cron-monthly
                    - re-validates Bearer ${CRON_SECRET}
                    - SELECT * FROM businesses
                    - for each business:
                          fetch previous audit's score
                          run _run_audit_core
                          insert new audit row
                          if |Δ| >= 10:
                                lookup owner email via supabase_admin.auth.admin.get_user_by_id
                                send_score_change_alert(...)
```

**Two layers of secret validation** (Next.js + FastAPI) is intentional: the Next.js route is publicly addressable (`/api/cron/...`) so we don't want it forwarding arbitrary requests to the backend.

`vercel.json` to enable the schedule is **not yet committed** — see roadmap.

---

## 5. Data model

### `aeo_audits` (migrations 010 + 012)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK |
| `business_id` | UUID FK → `businesses` (CASCADE) |
| `score` | INTEGER | 0–100 |
| `score_breakdown` | JSONB | `{gbp, reviews, website, local_search, ai_citation}` |
| `perplexity_mentioned` | BOOLEAN | denormalized for quick reporting |
| `perplexity_snippet` | TEXT | 500-char excerpt when mentioned |
| `google_ai_mentioned` | BOOLEAN | |
| `google_ai_snippet` | TEXT | |
| `raw_results` | JSONB | full per-query data + recommendations |
| `created_at` | TIMESTAMPTZ DEFAULT now() |

RLS: `business_id` must belong to the caller's business.
Index: `(business_id)`.

### `aeo_content` (migration 011)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK |
| `business_id` | UUID FK → `businesses` (CASCADE) |
| `description` | TEXT | 150–200 word AEO-optimized blurb |
| `faq` | JSONB | array of `{question, answer}` |
| `schema_markup` | TEXT | JSON-LD LocalBusiness markup |
| `social_bio` | TEXT | 150-char social bio |
| `created_at` | TIMESTAMPTZ DEFAULT now() |

RLS: members can manage their own content.

### Other touched tables
- `businesses` — has `id`, `user_id`, `name`, `type`, `city`, `province`, `website`. The audit pipeline reads from here.
- `auth.users` — Supabase-managed; we look up email via `supabase_admin.auth.admin.get_user_by_id(user_id)` for alerts (we do not duplicate emails into `profiles`).

---

## 6. Frontend

Stack: Next.js 15 App Router, TypeScript, Tailwind, `next-intl` (en/fr), Supabase JS client.

**Server components** (data-fetching):
- `apps/web/app/[locale]/dashboard/page.tsx` — fetches business, last 6 audits, renders chat layout + AeoAuditCard + ScoreHistoryChart in the right panel.
- `apps/web/app/[locale]/dashboard/content/page.tsx` — fetches business + latest `aeo_content` row, renders ContentPage.

**Client components** (interactive):
- `AeoAuditCard.tsx` — shows score + pillar bars + delta vs previous, "Run audit" button, calls `POST /api/v1/aeo/audit` directly with the user's JWT.
- `RecommendationsList.tsx` — expandable accordion of recommendations sorted by impact, color-coded by pillar.
- `ScoreHistoryChart.tsx` — pure SVG line chart, no chart library. Renders gridlines, filled area, dots, latest-score label, ±delta vs previous.
- `ContentPage.tsx` — renders the 4 generated content blocks with copy-to-clipboard buttons; calls `POST /api/v1/aeo/generate-content`.

**Sidebar nav (current):** Chat, Content, Settings. Reviews / Bookings / Guide are commented out until Phase 3 (Google API approval expected July 2026).

---

## 7. APIs and external services

### Perplexity API
- **Used for:** AI citation signal (10 of the 18 AI Citation pts).
- **Model:** `sonar`
- **Endpoint:** `POST https://api.perplexity.ai/chat/completions`
- **Detection:** substring-match the business name in the assistant's reply; capture first 500 chars as snippet.
- **Cost:** ~$0.002–$0.005 per call × 3 calls/audit ≈ $0.006–$0.015/audit.

### SerpApi
- **Used for:** Google search results — local pack, organic, AI Overview, knowledge graph, and recent reviews.
- **Engines used:**
  - `google` — main search (3 queries + 1 name fallback per audit)
  - `google_maps_reviews` — review recency check (when `place_id` available)
- **Why a third party:** Scraping Google directly is fragile and ToS-violating. SerpApi handles proxies/captchas and returns clean JSON. **One Google call returns 4+ signals** (AI Overview, local pack, organic, KG) on a single charge — this is the entire reason we use it instead of separate APIs.
- **Endpoint:** `GET https://serpapi.com/search`
- **Locale:** `gl=ca&hl=en` (Canadian-localized).
- **Cost:** ~$0.015/call × 4 (or 5) calls/audit ≈ $0.06–$0.075/audit. Dominant cost.

### Anthropic (Claude)
- **Used for:** Two narrow tasks via internal `core.ai_engine` wrapper:
  1. **Type normalization** — translate non-English/non-standard business types into clean search phrases.
  2. **Content generation** — description, FAQ, JSON-LD schema, social bio (the `/generate-content` endpoint).
- **Model:** `claude-haiku-4-5-20251001` (fastest/cheapest in family; quality is fine for these tasks).
- **Endpoint:** Anthropic SDK (`anthropic` Python package) → `https://api.anthropic.com/v1/messages`.
- **Cost:** Sub-cent per audit for type normalization. Content generation is ~$0.005–$0.01 per call (only run on user-initiated "Generate Content" click).

### OpenAI / Gemini (configured, not currently in the AEO path)
The `core.ai_engine` abstraction supports OpenAI (gpt-4o-mini) and Google Gemini (1.5-flash) as alternatives. They are wired for the legacy review-response generation path; the AEO product currently routes through Claude.

### Resend
- **Used for:** Transactional email — score-change alerts, future review notifications.
- **Endpoint:** Resend SDK (`resend` Python package).
- **Cost:** Free tier covers 100 emails/day. Score-change emails will be far below this for the foreseeable future.
- **Production blocker:** The sender domain must be verified in Resend. Until then, alerts will fail silently.

### Supabase
- **Used for:** Postgres (audits, content, businesses), Auth (JWT validation, user lookup), Row-Level Security.
- **Two clients:**
  - `supabase_admin` — service-role key, bypasses RLS, used by FastAPI.
  - `supabase_client` (browser) — anon key, RLS-protected, used by Next.js client components.
- **Cost:** Free tier sufficient for early stage.

### Stripe
- **Configured but not active in AEO flow.** Used by the broader subscription model. AEO product currently free for testing.

### httpx (website crawler)
- **Used for:** Direct GET on the user's own website to detect schema and reachability. Not a third-party API.
- **Cost:** $0.

---

## 8. Backend libraries (`api/requirements.txt`)

| Library | Version | Why we use it |
|---|---|---|
| **fastapi** | 0.115.0 | Async-first Python web framework. Auto-generates OpenAPI docs. Type-driven validation via Pydantic. |
| **uvicorn[standard]** | 0.30.6 | ASGI server that runs FastAPI in production. The `[standard]` extras give us `uvloop`, `httptools`, `websockets`. |
| **pydantic** | 2.9.2 | Type-safe request/response models. Validates incoming JSON automatically (`AuditRequest`). |
| **pydantic-settings** | 2.5.2 | Loads env vars into typed config classes. |
| **httpx** | 0.27.2 | Async HTTP client. Used for outbound calls to Perplexity, SerpApi, and the website-crawler check. |
| **supabase** | 2.29.0 | Official Python client for Supabase Postgres + Auth + Storage. Wraps PostgREST + GoTrue. |
| **openai** | 1.45.0 | OpenAI Python SDK (gpt-4o-mini); behind `ai_engine` provider abstraction. |
| **google-generativeai** | 0.7.2 | Google Gemini Python SDK; alternate AI provider. |
| **anthropic** | 0.40.0 | Anthropic Python SDK (Claude); used for type normalization + AEO content generation. |
| **stripe** | 10.9.0 | Stripe SDK for subscription management. |
| **resend** | 2.3.0 | Resend SDK for transactional email. |
| **pytest / pytest-asyncio** | 8.3.3 / 0.24.0 | Test runner; `pytest-asyncio` enables `async def test_*` functions. |
| **python-dotenv** | 1.0.1 | Loads `.env` files into `os.environ` for local dev. |

---

## 9. Frontend libraries (notable in `apps/web/package.json`)

| Library | Why |
|---|---|
| **next** (15) | React framework, App Router with React Server Components. |
| **react / react-dom** | UI primitive. |
| **tailwindcss** | Utility-first styling. All dashboard styling is Tailwind. |
| **@supabase/supabase-js**, **@supabase/ssr** | Browser + SSR clients for Supabase Auth and queries. |
| **next-intl** | i18n (English / French). All user-facing text is keyed in `messages/en.json` / `messages/fr.json`. |
| **lucide-react** (or inline SVG) | Iconography. |

No chart library is used — `ScoreHistoryChart` is hand-rolled SVG to keep the bundle small.

---

## 10. Environment variables

Defined in `api/.env.example`. Production values live in Vercel + Railway environment settings.

```
# AI providers
AI_PROVIDER=openai|gemini|claude
OPENAI_API_KEY, OPENAI_MODEL
GEMINI_API_KEY, GEMINI_MODEL
ANTHROPIC_API_KEY, CLAUDE_MODEL

# Supabase
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

# Stripe
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET

# Email
RESEND_API_KEY, FROM_EMAIL

# AEO data sources
PERPLEXITY_API_KEY
SERPAPI_KEY

# Cron (shared secret between Next.js and FastAPI)
CRON_SECRET

# App
ENVIRONMENT=development|production
ALLOWED_ORIGINS
```

The Next.js side additionally needs `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `CRON_SECRET`.

---

## 11. Cost model (per audit)

| Component | Calls | Approx. cost |
|---|---|---|
| Perplexity (3 queries) | 3 | $0.006–$0.015 |
| SerpApi google (3 queries + 1 name fallback) | 3–4 | $0.045–$0.060 |
| SerpApi google_maps_reviews (recency) | 0–1 | $0.000–$0.015 |
| Claude (type normalization) | 0–1 | ~$0.001 |
| Website crawl | 1 | $0 |
| **Total** | — | **$0.05–$0.09** |

At $19/mo Starter (4 audits/mo) the API spend per customer is ~$0.20 worst case. **Margin is comfortable** at every tier.

---

## 12. What's instrumented today

- **Backend logs** via Python `logging` + raw `print(...)` — every per-query Perplexity/SerpApi result is logged with mentioned/local/organic/kg flags.
- **Backend insert side-effects** are logged.
- **Cron-monthly summary** returned in the response body (per-business `{score, status: ok|error}`).

Not yet instrumented: structured logging (e.g. `structlog`), request tracing (OpenTelemetry), error reporting (Sentry). All on the roadmap for production.

---

## 13. Known issues / production blockers

| Issue | Where | Severity |
|---|---|---|
| `vercel.json` cron schedule not committed | `apps/web/` | Medium — auto-audits won't fire until added |
| Resend sender domain not verified | Resend dashboard | Medium — alert emails will fail silently |
| Railway Dockerfile not yet written | `api/Dockerfile` | High — cannot deploy backend |
| Audit re-run not rate-limited | `/api/v1/aeo/audit` | Medium — abuse risk + cost risk |
| Schema detection uses substring match, not parsed JSON-LD | `check_website()` | Low — replace with `extruct` later |
| Recommendation strings hardcoded English | `generate_recommendations()` | Low — i18n keys to be added in F9 |

These are tracked in `docs/aeo-roadmap.md`.

---

## 14. Where to look next

| For… | Read… |
|---|---|
| Score formula | `api/aeo/router.py` → `calculate_score()` |
| Recommendation rules | `api/aeo/router.py` → `generate_recommendations()` |
| Audit orchestration | `api/aeo/router.py` → `_run_audit_core()` |
| Cron entry point | `apps/web/app/api/cron/monthly-audit/route.ts` |
| Dashboard data fetch | `apps/web/app/[locale]/dashboard/page.tsx` |
| Score chart | `apps/web/components/dashboard/ScoreHistoryChart.tsx` |
| Database schema | `supabase/migrations/010_*`, `Migration 011*`, `012_*` |
| Roadmap | `docs/aeo-roadmap.md` |
| Sprint history | `docs/aeo-sprint-f6-f7-summary.md` |