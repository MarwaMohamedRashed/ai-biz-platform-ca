# AEO Router Refactor — Status

**Started:** 2026-05-19
**Current state:** COMPLETE — all six tiers landed. `router.py` is down
to **608 lines** (route handlers + request models + profile-field
cleaners only), from 4,841. The audit pipeline now lives in
`audit/engine.py`; `audit/`, `coach/`, `content/`, `reputation/`,
`competitors.py`, and `integrations/` hold everything else. All 280
tests green at every tier. The only remaining `integrations/` work is
`dataforseo.py`, which is net-new for Phase 1 (not part of this
extraction).

The original `api/aeo/router.py` was 4,841 lines of mixed concerns (audit
engine, scoring, recommendations, content generation, AI coach, reputation
fetchers, competitor logic, route handlers). This doc tracks the
incremental split into the structure proposed in conversation.

---

## Done in this pass (router.py: 4,841 → 3,304 lines, -32%)

### `api/aeo/coach/`
- `prompts.py` — `build_coach_system_prompt` + `CoachRecommendation` model
- `handler.py` — `POST /recommendation-help` endpoint, message/request
  Pydantic models, coach LLM instance, tier-gating logic
- Mounted via `router.include_router(_coach_router)` at the bottom of `router.py`

### `api/aeo/content/`
- `prompts.py` — `build_content_prompts`, `build_regenerate_prompts`,
  `FAQ_TARGET_COUNT`
- `validators.py` — `clean_bio`, `clean_description`, `truncate_at_word`,
  `validate_content`
- `generator.py` — `POST /generate-content`, `PATCH /content/{id}`,
  `POST /content/{id}/verify`, `POST /content/{id}/regenerate-item`,
  all Pydantic models, the SerpApi PAA fetcher, the patch/verify
  regex tables, content LLM instance
- Mounted via `router.include_router(_content_router)` at the bottom

### `api/aeo/audit/`
- `recommendations.py` — `generate_recommendations` (419 lines on its
  own). Uses **lazy imports** at the top of the function to pull
  `_is_*_business`, `_user_directories_only`, `_city_to_subreddit_url`,
  and `CITY_SUBREDDITS` from `router.py` without creating an import
  cycle. Re-exported from `router.py` so existing tests (`from aeo.router
  import generate_recommendations`) keep working.

### `api/integrations/`
- Empty package with `__init__.py`. Created as the destination for the
  HTTP client extractions but no calls have been moved yet.

### Verification
- All four files pass `ast.parse` syntax check
- `from aeo.router import router` still resolves with 12 routes registered
  (same as before; the include_routers preserve URLs)
- `from aeo.router import generate_recommendations` returns the same
  object as `from aeo.audit.recommendations import generate_recommendations`
- **All 90 existing tests pass** (`test_canadian_verticals.py`,
  `test_reddit_linkedin.py`, `test_trades_recs.py`)

---

## Remaining work (~3,300 lines still in `router.py`)

Grouped by what should move where. **Order matters** — items earlier in
the list are safer to extract first because they have fewer outbound
dependencies on the rest of `router.py`.

### Tier 1 — pure / leaf code (cheapest moves, do first)

- **`api/aeo/audit/signals.py`** — extract `_extract_text_signals`,
  `_is_specific_type_for_subspecialty`, `_detect_cuisine`,
  `KNOWN_TYPES`, `_SPECIFIC_TYPES_BODY_TAGS_SKIPPED`, `_TITLE_TAG_RE`.
  Pure regex/text processing, no external API calls.

- **`api/aeo/audit/verticals.py`** — extract `_is_trades_business`,
  `_is_healthcare_business`, `_is_dentist_business`, `_is_food_business`,
  `_is_legal_business`, `_is_realtor_business`, `_is_b2b_business`,
  `_user_directories_only`, `_detect_directory_presence`,
  `_city_to_subreddit_url`, `CITY_SUBREDDITS`, `_domain_from_url`,
  `_name_short`. Move so `recommendations.py` can switch from lazy
  imports to a clean top-level import.

- **`api/aeo/audit/queries.py`** — extract `build_queries`. Pure function
  that builds the SerpApi query list from business context. Used by
  `run_perplexity_multi`, `run_google_multi`, `run_chatgpt_multi`.

- **`api/aeo/audit/scoring.py`** — extract `calculate_score`,
  `score_competitor`, `match_competitor_ai_citations`. Pure scoring
  logic, no I/O.

### Tier 2 — country/province helpers + small utilities

- **`api/aeo/audit/geo.py`** (or fold into `signals.py`) — extract
  `country_to_gl`, `province_to_gl`, `address_country_gl`,
  `expand_province`, `COUNTRY_TO_GL`, `_COUNTRY_ISO_TO_GL`,
  `_CA_PROVINCE_CODES`, `extract_search_name`. Used by both audit and
  content modules — currently duplicated in `content/generator.py`
  (`_PAA_COUNTRY_GL`). Once extracted, consolidate the duplicate.

### Tier 3 — integrations (the SerpApi extraction) — **DONE**

- **`api/integrations/serpapi.py`** ✓ — one `search(params, timeout)`
  function that injects `api_key` and returns parsed JSON. Replaced
  every inline `httpx.AsyncClient` + `serpapi.com/search` block. Sites
  migrated:
  - `_check_review_recency` (router.py)
  - `_google_one`
  - `_lookup_competitor_by_place_id`
  - `_resolve_maps_place_id`
  - `_fetch_competitor_reviews`
  - `_fetch_own_reviews`
  - `competitor_search` endpoint
  - `_fetch_people_also_ask` (content/generator.py)

  `_google_name_lookup` was a non-issue: it doesn't call SerpApi
  directly, it delegates to `_google_one`.

- **`api/integrations/perplexity.py`** ✓ — one `chat(query, *, model,
  timeout)` function returning raw JSON. `_perplexity_one` collapsed
  from a 16-line HTTP block to a single call.

- **Side-cleanup** — content/generator.py's duplicated
  `_PAA_COUNTRY_GL` map is gone; the PAA helper now imports
  `COUNTRY_TO_GL` from `audit/geo.py` (single source of truth).

- **`api/integrations/dataforseo.py`** — still pending; lands with
  Phase 1 of the market intelligence layer (see
  `docs/market-intelligence-architecture.md`).

### Tier 4 — reputation analysis — **DONE**

- **`api/aeo/audit/perplexity.py`** ✓ — per-query Perplexity runner
  (`_perplexity_one`) lifted out so reputation/fetcher.py can import it
  without a circular dep into router.py. Re-exported from router.py
  for audit-side back-compat.

- **`api/aeo/audit/maps.py`** ✓ — `parse_relative_date` +
  `resolve_maps_place_id` extracted (Google Maps lookup helpers that
  cross audit/reputation/competitor concerns). Re-exported from
  router.py under the old underscored names.

- **`api/aeo/reputation/fetcher.py`** ✓ — `fetch_own_reviews`,
  `fetch_competitor_reviews`, `fetch_own_perplexity_reputation`,
  `fetch_competitor_perplexity`. All four are thin wrappers around
  `serpapi_client.search` / `_perplexity_one` plus best-effort error
  handling. Citation-source → friendly platform-name map (Yellow Pages,
  Yelp, BBB, RateMDs, HomeStars, …) lives here as `_CITATION_PLATFORM_NAMES`.

- **`api/aeo/reputation/analyzer.py`** ✓ — `analyze_own_reputation`
  + `analyze_competitor_weaknesses`. Each instantiates its own
  `content_llm` (AIEngine) at module load — mirrors the pattern in
  `coach/handler.py` and `content/generator.py`. Both prompts moved
  verbatim, no behaviour change.

- All four fetchers + both analyzers re-exported from router.py under
  the old underscored names so `_run_audit_core` and the
  `/own-reputation` endpoint still resolve them via `aeo.router`.

### Tier 5 — competitor management — **DONE**

- **`api/aeo/competitors.py`** ✓ — single 474-line module owning:
  - `extract_location_from_address` (city / region / country parsed
    out of SerpApi address strings, with postal-code-shape country
    inference for cross-border leakage)
  - `extract_competitors` (top-N local pack with cross_city flagging)
  - `check_competitor_websites` (parallel `check_website()` over every
    URL-bearing competitor; lazy-imports `check_website` from router.py
    to dodge a circular import)
  - `lookup_competitor_by_place_id` (google_maps `place_results` for
    owner-added competitors)
  - `score_user_competitor` (end-to-end: lookup + website + AI citation
    match + 5-pillar formula)
  - `CompetitorEntry` + `CompetitorListRequest` Pydantic models
  - Sub-router with `GET /competitor-search` + `POST /competitors`,
    mounted via `router.include_router(_competitor_router)` so URLs
    stay stable
- `_resolve_maps_place_id` already lives in `audit/maps.py` (extracted
  during Tier 4); the competitors module didn't need it directly.
- All public + underscored names re-exported from router.py so
  `_run_audit_core`, `test_address_parsing.py`, and any other callers
  keep working without import-path churn.

### Tier 6 — audit engine + remaining endpoints — **DONE**

- **`api/aeo/audit/website.py`** ✓ — `check_website` (the static-HTML
  schema + signal scraper) + the `_LB_SUBTYPES` schema set. Pulled out
  first so both the engine and competitors.py import it cleanly;
  competitors.py's lazy `from .router import check_website` workaround
  (added in Tier 5) is now a normal top-level import.

- **`api/aeo/audit/engine.py`** ✓ — the whole audit pipeline:
  `normalize_business_type`, `run_perplexity_multi` / `run_chatgpt_multi`
  / `run_google_multi` (+ their `_*_one` helpers), the SerpApi response
  parsers (`check_organic`, `check_knowledge_graph`, `check_local_pack`),
  `_check_review_recency`, and `_run_audit_core`. The two module-level
  LLM clients (`audit_llm`, `content_llm`) moved here too. Cross-package
  siblings (`competitors`, `reputation.analyzer`) are imported at
  function scope inside `_google_one` / `_run_audit_core` to keep the
  import graph one-way now that router.py is no longer the exchange hub.

- **What stays in `router.py` (608 lines)** ✓ — exactly as planned: the
  five route handlers (`/audit`, `/business` GET+PUT,
  `/recommendations/{id}`, `/own-reputation`, `/cron-monthly`), the
  matching request-shape Pydantic models (`AuditRequest`,
  `BusinessProfileRequest`), `send_score_change_alert`, the
  profile-field cleaners (`_clean_postal`, `_clean_image_url`,
  `_clean_price_range`, `_clean_hours`), and the re-export blocks +
  sub-router mounts that hold the package together. Unused imports
  (`httpx`, `json`, `AIEngine`, `ai_engine`, `schema_builder`, `kb`,
  the integration clients) were dropped.

---

## Sequencing recommendation

I'd do Tier 1 + Tier 2 in one focused session (~3-4 hours of careful
work). Those moves don't touch any HTTP I/O, so the regression risk is
near-zero — the test suite either passes or it doesn't, and the existing
tests cover most of the moved code.

Tier 3 onwards becomes more invasive (changes response-parsing
behaviour as we wrap the HTTP clients) and is a better fit for a
separate session — ideally right before Phase 1 of the market
intelligence layer, since the `integrations/dataforseo.py` work needs
the same scaffolding.

Tiers 4-6 can happen any time before launch as polish work.

---

## What this gave us already

| | Before | Tier 1+2 | Tier 3 | Tier 4 | Tier 5 | Tier 6 |
|---|---|---|---|---|---|---|
| `api/aeo/router.py` | 4,841 | 2,417 (-50%) | 2,131 (-56%) | 1,762 (-64%) | 1,360 (-72%) | **608** (-87%) |
| `api/aeo/competitors.py` | (in router) | — | — | — | 474 | 472 |
| `api/aeo/content/generator.py` | (in router) | 620 | 510 | 510 | 510 | 510 |
| `api/aeo/audit/` package | (didn't exist) | 7 files, 1,553 | 7 files, 1,553 | 9 files, 1,654 | unchanged | **11 files, 2,336** |
| `api/aeo/coach/` package | (didn't exist) | 3 files, 254 | unchanged | unchanged | unchanged | unchanged |
| `api/aeo/content/` package | (didn't exist) | 4 files, 1,040 | 4 files, 930 | 4 files, 930 | unchanged | unchanged |
| `api/aeo/reputation/` package | (didn't exist) | empty | empty | 3 files, 429 | unchanged | unchanged |
| `api/integrations/` package | (didn't exist) | empty | 2 files, 91 | unchanged | unchanged | unchanged |
| Tests passing | 280 | 280 | 280 | 280 | 280 | **280** (all green) |

`audit/` package after Tier 6: `engine.py` (755), `recommendations.py`
(419), `verticals.py` (265), `signals.py` (213), `scoring.py` (185),
`geo.py` (147), `queries.py` (127), `website.py` (111), `maps.py` (62),
`perplexity.py` (39), `__init__.py` (13).

The refactor is purely structural. No behaviour changed; no endpoints
moved; no Pydantic models renamed. The point was to get the easy
extractions out of the way so Phase 1 work (the DataForSEO integration
+ market-intelligence layer) lands in a smaller, easier-to-reason-about
file.

### Test imports preserved via re-exports

A handful of tests import `_is_*_business`, `_extract_text_signals`,
`build_queries`, `_clean_bio`, `_build_coach_system_prompt`,
`_apply_content_patch`, `generate_recommendations`, etc. directly from
`aeo.router`. To avoid churning the test suite, those names are
re-exported from `router.py` via aliased imports:

```python
from .audit.verticals import is_trades_business as _is_trades_business
from .content.validators import truncate_at_word as _truncate_at_word
# ...etc
```

New code (Phase 1 work, future refactors) should import directly from
the submodule (`from api.aeo.audit.verticals import is_trades_business`)
and skip the underscore alias.

### Refactor complete

All six tiers are landed. `router.py` went 4,841 → 608 lines (-87%)
with the test suite (280) green at every step and zero endpoint-URL or
Pydantic-model changes. The mixed-concerns monolith is now eight
focused modules:

- `audit/` — the scoring/recommendation/query/signal/geo helpers plus
  the `engine.py` pipeline and the `website.py` scraper
- `coach/` — the AI execution coach endpoint
- `content/` — content generation endpoints + prompts + validators
- `reputation/` — review/Perplexity fetchers + LLM analyzers
- `competitors.py` — competitor extraction/scoring + the two endpoints
- `integrations/` — thin SerpApi + Perplexity HTTP wrappers
- `router.py` — route handlers, request models, profile-field cleaners,
  and the re-export/mount glue

### Next: Phase 1 (not part of this refactor)

The one open `integrations/` item is `dataforseo.py`, which is net-new
for the market-intelligence layer (see
`docs/market-intelligence-architecture.md`) — it lands with Phase 1,
not as an extraction. The smaller router + the existing
`integrations/` scaffolding were the whole point: Phase 1 work now
drops into a codebase that's an order of magnitude easier to reason
about.
