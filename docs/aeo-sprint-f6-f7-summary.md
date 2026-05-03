# AEO Sprints F6 + F7 — Change Summary

**Date completed:** 2026-05-01
**Branch:** main
**Scope:** Phase 1 AEO product — scoring rebuild + recommendations engine

---

## TL;DR

We rebuilt the AEO audit from a binary "are you in AI search?" check into a **6-pillar AEO Readiness Score** that small businesses can actually act on. Each gap in the score now produces a specific, prioritized recommendation telling the user exactly what to do next. The system also now runs **3 search-query variants** instead of 1 to stop the score from swinging wildly between runs.

If the scoring model was wrong before, this sprint fixed the **product**, not just the code — what we measure now matches what small businesses can actually control.

---

## What changed (high-level)

| Before | After |
|---|---|
| Single binary check: 50 pts if in Perplexity, 50 pts if in Google AI | 5-pillar weighted score (GBP, Reviews, Website, Local Search, AI Citation) |
| One query (`best X in Y`) — results swung wildly between runs | 3 query variants run + aggregated, much more stable |
| Score only reflects famous businesses; SMBs always got 0 | New SMB businesses realistically score 30–60 with clear path to 80+ |
| Just a number — no actions | Each gap → specific recommendation with impact pts, difficulty estimate, and link |

---

## The new scoring model

**Total: 100 pts across 5 pillars**

### 1. Google Business Profile — 25 pts
The single strongest local-search signal. Google trusts its own data first.

| Signal | Pts |
|---|---|
| Has a claimed GBP (found in local pack OR knowledge graph) | 10 |
| Has a star rating | 5 |
| Has a primary business category set | 5 |
| Has phone or website on the listing | 5 |

### 2. Reviews & Reputation — 22 pts
Tiered, so even small businesses can earn partial credit.

| Signal | Pts |
|---|---|
| 50+ reviews | 12 |
| 10–49 reviews | 6 |
| Rating ≥ 4.5 | 10 |
| Rating 4.0–4.4 | 5 |

### 3. Website & Schema — 20 pts
Site must actually be reachable — no credit for just having a URL on file.

| Signal | Pts |
|---|---|
| Website is reachable (HTTP 200) | 8 |
| `LocalBusiness` JSON-LD schema present | 6 |
| `FAQPage` JSON-LD schema present | 6 |

### 4. Local Search Presence — 15 pts
Are you visible in the regular Google search results for your category?

| Signal | Pts |
|---|---|
| Appears in Google's Maps "3-pack" (local results) | 10 |
| Appears in regular blue-link organic results | 5 |

### 5. AI Citation — 18 pts
The classic AEO signal — but no longer dominates the score.

| Signal | Pts |
|---|---|
| Cited by Perplexity for category query | 10 |
| Cited by Google AI Overview for category query | 8 |

> **Note**: We had a "Content Foundation" pillar (5 pts for clicking the content generator) but removed it — it didn't measure real-world AEO readiness, just engagement with our tool.

---

## What's new in the audit pipeline

### Multi-query aggregation
The audit now runs **3 query variants** for each business and aggregates the results:

1. `best {type} in {city}, {province}` (the base query)
2. `{type} near {city}` (location-intent variant)
3. `top {type} {city} {province}` (alternate phrasing)

**Aggregation rule:** "any-of-3" — if the business is mentioned in **any** of the 3 query results, that pillar fires. This eliminates the random "the score swung from 33 to 15 between runs" problem.

**Cost implication:** 3× more API calls per audit. See cost section below.

### Recommendations engine (Sprint F7)
The backend now generates a sorted list of specific, actionable recommendations based on which pillars scored low. Each recommendation has:

- **pillar** — which score pillar it improves
- **title** — short headline ("Get to 10+ Google reviews")
- **description** — why it matters
- **action** — specific instruction ("Send a review request link to your last 10 customers...")
- **difficulty** — easy / medium / hard (5–10 min / 30–60 min / multi-week)
- **impact** — points it would unlock
- **url** — optional deep link (e.g., business.google.com)

Recommendations are sorted by impact (highest first), so users see the biggest wins at the top.

The frontend renders them as an **expandable checklist** below the audit card, with colored pillar tags and difficulty estimates.

---

## APIs used by the AEO product

### 1. Perplexity API
**What it is:** Perplexity is an AI search engine that crawls the live web and answers questions with citations. We use their `sonar` model to ask category-style questions.

**Why we use it:** Perplexity is one of the major answer engines our customers want to be cited by. It's also the easiest to influence through directory listings and structured content — making it the strongest "controllable" AI signal.

**How we use it:** We send a chat-completion request with each query variant (`best clinic in Milton, ON`, etc.) and check whether the business name appears in the response text. We capture the first 500 characters as a snippet for context.

**Cost:** Roughly $0.002–$0.005 per query × 3 queries per audit ≈ **$0.006–$0.015 per audit**.

**Endpoint we call:** `POST https://api.perplexity.ai/chat/completions`

---

### 2. SerpApi (Google Search)
**What it is:** SerpApi is a Google Search results scraper as a service. We give it a query and it returns structured JSON with **everything Google shows** — organic results, local pack ("Maps 3-pack"), AI Overview, knowledge graph (the GBP sidebar), ads, related searches, and more.

**Why we use it:** Scraping Google directly is fragile and against ToS. SerpApi handles all the proxy/captcha nonsense and gives us a clean, stable JSON response. Critically, **one SerpApi call returns 4+ different signals** we use in the score — all on a single API charge.

**How we use it:** For each query variant, we make one SerpApi call and extract:
- `ai_overview` — Google AI Overview text (when present, which isn't always)
- `local_results.places` — the 3 businesses in the Maps pack, with rating and review counts
- `organic_results` — regular blue-link results
- `knowledge_graph` — sidebar info if Google shows a GBP card

We also pass `gl=ca` and `hl=en` so we get Canadian-localized results.

**Cost:** SerpApi charges per search. Their free tier is 100 searches/month; paid plans start at $75/month for 5,000 searches. With 3 queries per audit, **one audit = 3 SerpApi credits**.

**Endpoint we call:** `GET https://serpapi.com/search`

---

### 3. Anthropic Claude (via internal `ai_engine`)
**What it is:** Anthropic's Claude (Sonnet) — used through our internal `core.ai_engine` wrapper. Same model that powers this assistant.

**Why we use it:** For two narrow AI tasks where Perplexity/SerpApi don't apply.

**How we use it:**
1. **Business type normalization** (`normalize_business_type`) — if a user enters "studio de photographie" or anything outside our `KNOWN_TYPES` list, Claude translates it to a clean English search phrase like "photography studio" so the search queries work.
2. **Content generation** (`/generate-content` endpoint, Sprint F6) — Claude writes the optimized business description, FAQ Q&A pairs, JSON-LD schema markup, and social media bio that users can paste onto their website.

**Cost:** Per-token, but each call is small. Roughly **$0.001–$0.01 per audit** for the type-normalization call. Content generation is a separate, on-demand action.

---

### 4. Custom website crawler (httpx)
Not a third-party API — just `httpx` fetching the user's own website with a 10-second timeout, looking for JSON-LD schema markers in the HTML.

**Why:** AI engines like Perplexity heavily favor sites with structured data. We need to know if the user has it.

**Cost:** $0 — direct HTTP requests.

---

## Total per-audit cost estimate

| API | Calls per audit | Approx. cost |
|---|---|---|
| Perplexity (3 queries) | 3 | $0.006–$0.015 |
| SerpApi (3 queries) | 3 | ~$0.045 (at $75 / 5,000 = $0.015 each) |
| Claude (type normalization, only for non-standard types) | 0–1 | $0.001 |
| Website crawl | 1 | $0 |
| **Total per audit** | — | **~$0.05–$0.07** |

**Implication for pricing:** if our Starter tier offers 1 audit/month and 1 re-audit, we're spending ~$0.10/customer/month on API costs. Profitable at $19/month easily. Monthly auto-audits over 6 months = $0.30/customer in API costs.

---

## File-by-file change list

### Backend — `api/aeo/router.py` (rewritten)

**New helpers:**
- `build_queries()` — generates the 3 query variants from one template list
- `_perplexity_one()` — runs a single Perplexity query (unchanged logic, extracted from old function)
- `run_perplexity_multi()` — runs all 3 queries in sequence, aggregates with any-of-3
- `_google_one()` — runs a single SerpApi query (extracted)
- `run_google_multi()` — runs all 3 SerpApi queries, aggregates
- `check_local_pack()` — extracts business presence + rating + reviews from Maps pack
- `check_organic()` — checks if business appears in regular search results
- `check_knowledge_graph()` — extracts GBP card data when present
- `check_website()` — fetches website and detects schema markup
- `calculate_score()` — applies the new 5-pillar weighted model
- `generate_recommendations()` — builds the actionable to-do list

**Updated endpoints:**
- `POST /api/v1/aeo/audit` — now returns `score`, `breakdown`, `recommendations`, plus the raw signal data
- `GET /api/v1/aeo/recommendations/{business_id}` — **new** — returns recommendations from the most recent audit (lets the dashboard fetch them server-side)
- `POST /api/v1/aeo/generate-content` — unchanged

### Database — `supabase/migrations/012_aeo_audit_score_breakdown.sql`
Added `score_breakdown JSONB` column to `aeo_audits`. Recommendations are stored inside `raw_results` (JSONB), so no schema change needed for them.

### Frontend — `apps/web/components/dashboard/`
- `AeoAuditCard.tsx` — replaced binary engine display with 5 pillar progress bars; renders `<RecommendationsList />` below the score card after an audit completes
- `RecommendationsList.tsx` — **new** — expandable accordion showing each recommendation with pillar tag, impact points, difficulty estimate, description, and action steps

### Frontend — `apps/web/app/[locale]/dashboard/page.tsx`
- Server query now reads `latestAudit.raw_results.recommendations` and passes it to `<AeoAuditCard initialRecommendations={...} />`
- Right side panel updated to show pillar breakdown bars instead of the old static "Perplexity ✓ / Google AI ✗" text

---

## Known issues to fix in the next sprint

These were noted during testing and are deferred (per your call):

### 1. Reviews still occasionally show 0 even when the business has reviews
**Symptom:** Sometimes Reviews scores 0/22 even though the business clearly has Google reviews.
**Cause:** When the local pack doesn't return the business in any of the 3 queries (rare but happens), and Google doesn't return a `knowledge_graph` (which it almost never does for category queries), we have nowhere to read review data from.
**Fix:** Add a 4th SerpApi call specifically searching the **business name** (not category) to force the knowledge graph to appear. Adds ~$0.015 per audit.

### 2. Website score gives partial credit even when site is down
**Symptom:** Audit gives Website 5/20 even when the website returns a 5xx error.
**Cause:** This was supposed to be fixed already (we added `raise_for_status()`). Need to verify the live behavior.
**Fix:** Add explicit logging of the website fetch result and double-check the exception handling path.

Both are queued as the first tasks for the next sprint.

---

## What's next (proposed sprint plan)

### Sprint F8 — Reliability fixes + Monthly monitoring
1. Fix the two known issues above
2. Add a 4th name-specific SerpApi query to reliably populate review/GBP data
3. Add `cron` job (Vercel scheduled function) to re-audit every business monthly
4. Add audit history table + score-over-time chart
5. Email alert when score changes by ±10 points

### Sprint F9 — Onboarding + production deploy
1. Capture "Have you claimed your GBP?" yes/no in onboarding
2. Allow user to enter their primary GBP category directly
3. Production deploy of audit endpoint to Railway
4. Marketing page screenshots reflecting the new pillar UI
5. Pricing page with confirmed cost-per-audit numbers

### Optional / "if there's time"
- **Competitor benchmarking** — run audit on 1–2 competitors, show "you score 45 vs. top competitor 78"
- **Sentiment analysis** — when AI mentions you, is the tone positive/negative? HubSpot weights this 40%
- **Schema upgrade** — replace substring matching with `extruct` library for accurate JSON-LD parsing

Then **Phase 2 — Sales Agent** kicks off.

---

## Design decisions worth remembering

1. **Why we use SerpApi `local_pack` data as the primary GBP signal** instead of `knowledge_graph` — Google only returns `knowledge_graph` when you search for a specific business name, not a category. Since our queries are category-style ("best clinic in Milton"), `knowledge_graph` is almost always empty. The local pack always returns rating/reviews when the business is in it, so we use that as the source of truth.

2. **Why we dropped the "Content Foundation" pillar** — it only measured whether the user clicked our "Generate Content" button. That's an engagement metric, not an AEO signal. The actual schema appearing on their website is what matters, and that's already covered by the Website pillar.

3. **Why "any-of-3" aggregation instead of majority vote** — small businesses are unlikely to be cited consistently across all 3 query variants. Majority vote (2-of-3) would still leave most SMBs at 0. "Any-of-3" gives benefit of the doubt while still requiring real signal.

4. **Why we stripped the "you have a website URL saved" credit** — entering a URL during onboarding is just data entry, not an AEO improvement. A 5xx site is functionally invisible to AI engines, so it should score the same as no site at all.
