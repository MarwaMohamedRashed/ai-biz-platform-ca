# Market Intelligence Architecture — Cached AI Visibility Layer + ROI v2

**Date:** 2026-05-19 (Phase 0 validation complete; ready for Phase 1 implementation)
**Status:** Phase 0 validated — DataForSEO confirmed as data source with adjustments below.
**Owner:** Mohamed Saleh
**Companion docs:**
[feature-implementation-deep-dive.md](feature-implementation-deep-dive.md) (what's shipped) ·
[dataforseo-test-plan.md](dataforseo-test-plan.md) (the validation plan — Phase 0 executed 2026-05-19) ·
[aeo-roadmap.md](aeo-roadmap.md) (sequencing)

---

## Phase 0 Validation — Outcome (2026-05-19)

The DataForSEO test plan was executed against 5 GTA businesses (dentist
in Burlington, restaurant in Mississauga, multi-disciplinary clinic in
Milton, salon in Oakville, plumber in Brampton). Full results in
`scripts/dataforseo_test/results/2026-05-19T04-49-57Z/SUMMARY.md`.
Final verdict: **PROCEED_WITH_CAVEATS**. Total Phase 0 cost: ~$3.50.

### What was validated

- **Question discovery at CITY level works** — via the `keywords_data`
  family endpoint `keywords_for_keywords/live` with `location_code`
  (integer). Returns 1,400-3,500 keywords per (vertical, city) with
  city-specific search volumes. Burlington dentist: 1,473 keywords,
  578 with volume. Oakville salon: 3,500 keywords, 2,402 with volume.
- **Mid-city density is 50-77% of Toronto** — sufficient for Formula A.
  Burlington 50%, Mississauga 61%, Milton 62% (with right seeds),
  Oakville 73%, Brampton 77%. Every mid-city has 500+ keywords with
  city-level volume.
- **PAA at city level works** via SERP advanced — 4/5 verticals
  returned PAA. Healthcare in mid-cities sometimes returns no PAA;
  architecture must handle this gracefully.
- **Trend stability via `monthly_searches`** — most keywords show
  <25% MoM swing, supporting **quarterly question-list refresh +
  monthly mention refresh** cadence.
- **`keywords_for_site` works for the customer's website** — Burlington
  Family Dentists site indexed for 102,840 keywords, top 50 returned
  per call at $0.015.

### What changed vs the original plan

1. **Discovery endpoint changed.** The original design assumed
   `dataforseo_labs/google/keyword_ideas/live` at city level. **This
   does not work** — Labs API supports only country-level locations
   (94 total worldwide, only "Canada" for us). Switched to
   `keywords_data/google_ads/keywords_for_keywords/live` with integer
   `location_code` for city-level support. Same per-call cost
   ($0.075), city-level granularity, similar response shape.

2. **City `location_code` mapping required.** Cities are referenced
   by integer code in Keywords Data API (Burlington = 1002197,
   Mississauga = 1002350, etc.). Maintain a hardcoded mapping in code
   plus a fallback lookup via
   `/v3/keywords_data/google_ads/locations` for new cities.

3. **Per-vertical seed templates are not enough alone — sub-type
   augmentation is required.** James Snow Physiotherapy returned 3
   keywords with the seed set `[physiotherapy, physiotherapist,
   physio clinic]` (clinical names that real customers don't search).
   With multi-disciplinary seeds reflecting actual services offered
   (`[massage therapy, rmt near me, chiropractor, acupuncture,
   naturopath, mva rehabilitation, sports injury, back pain
   treatment]`), the same business returned 1,642 keywords with 903
   having city-level volume. **The seed set must reflect the
   services the business actually offers and how Canadians search
   for them**, not the vertical's textbook name. See "Per-business
   sub-type augmentation" below.

4. **Phase 6 (Branded Search Tracking) is dropped as designed.**
   Google Ads returns `null` volume for almost all SMB branded
   queries (below the ~10/mo exposure threshold). The few that
   return non-null are often cross-brand contamination — "Masrawy
   Egyptian Kitchen" returned 12,100/mo which is implausibly high
   for a single Mississauga restaurant, likely matching a broader
   brand or chain. Replaced with **category-volume tracking** —
   tracking the city-vertical question volumes themselves over time,
   which IS reliable. See "Category-volume tracking" section.

5. **Q6 redefined.** Was "raw keyword count vs Toronto." Now
   "count of keywords WITH non-null volume vs Toronto" — measures
   actual usable data density, not endpoint-pagination breadth.

6. **All 18 verticals supported uniformly.** No tier-based vertical
   restrictions. Healthcare verticals (physio, chiro, optometrist,
   dentist) need careful service-based seed augmentation;
   restaurants need cuisine/dietary augmentation; both leverage
   existing signal extraction (commits `bc7ec1a` for restaurant
   dietary/cuisine, `325334f` for clinic services).

---

## Purpose

The current LeapOne dashboard is a one-time audit report. After the owner
exhausts the Action Plan, there's no fresh-every-month reason to keep
the subscription. Customer testing in May 2026 made this risk concrete:
the dentist owner said *"I don't care about visibility, I care about
revenue and ROI"* — and even with the ROI MVP, the data behind the ROI
is composed from upstream signals (schema, GBP completeness) rather
than directly-observable AI behavior.

This doc captures the architecture for a **cached market intelligence
layer** that:

1. Replaces the score-based ROI primitive with an **observed AI
   visibility share** primitive
2. Gives every paying customer a fresh-every-month "what changed in my
   area" data point — the retention hook
3. Builds a defensible cache as a natural byproduct, without trying to
   reproduce DataForSEO from scratch
4. Stays cheap enough to launch on (~$50/mo data cost at 100 customers)
5. Doesn't require integration with the customer's booking / CRM /
   internal systems

---

## Scope

### In
- Per-(vertical, city) cached market intelligence: top ~50 questions,
  search volume, AI mention data, top mentioned businesses
- Branded search volume tracking per business
- Position + recommendation-strength + sentiment extraction on AI
  mentions (better parsing of existing query results)
- ROI v2 formula based on observed visibility share, not composite
  score
- Vertical benchmarks (your business vs the average / top-quartile in
  your vertical)
- Monthly scheduled refresh for combos with active customers
- Scope-aware fallback for non-local businesses (skip cached layer,
  use basic mention path)

### Out (deferred)
- GBP Insights API integration (gated on Google approval; reapply
  scheduled July 2026) — design a slot in the schema, don't build
- Call tracking integration (CallRail / similar)
- Booking system integration (Calendly, Jane.app, etc.)
- Tracking pixels / referrer attribution
- Public-facing market reports / SEO content from the cache
- Province-level / country-level scope tiers with separate query
  templates (defer until a real customer with this need signs up)

---

## Core architectural decision

**The data unit is `(vertical, city, country)`, not per-business.**

This is the single insight that makes the architecture affordable.
- New customer in (dentist, Burlington, CA)? Cache hit if any prior
  dentist in Burlington has signed up. Cost per new customer in a
  warm cache = $0.
- 100 customers don't generate 100 cache entries — they probably
  generate 30-40, because customers cluster.
- Refresh budget is bounded by the number of unique combos with
  active customers, not by customer count.

The competitor model is also redefined here. The current curated
competitor list is who the owner *thinks* competes. The cached
intelligence reveals who **actually wins the AI conversation** in their
area, which may be a different set. We keep both:
- `user_competitors` (owner-curated, existing) — the comparison the
  owner wants to track
- `top_mentioned_businesses` (cached, new) — who actually shows up in
  AI answers for the area, regardless of who the owner picked

---

## Schema

### New table: `market_intelligence`

```sql
CREATE TABLE market_intelligence (
  id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  vertical            text          NOT NULL,            -- canonical key, e.g. 'dentist'
  city                text          NOT NULL,            -- normalized, e.g. 'Burlington'
  province            text          NOT NULL,            -- e.g. 'ON'
  country             text          NOT NULL DEFAULT 'Canada',

  -- Top ~50 questions tracked for this combo, with volume + intent + observed mentions
  -- Each entry shape (see "Question Layer" below):
  --   { question, intent, search_volume, last_seen, mentions: { chatgpt: [...], perplexity: [...], google_ai: [...] } }
  questions           jsonb         NOT NULL DEFAULT '[]'::jsonb,

  -- Aggregated leaderboard derived from questions[].mentions
  -- Shape: [{ name, place_id, mention_count, weighted_score, avg_position, sentiment_avg }]
  top_businesses      jsonb         NOT NULL DEFAULT '[]'::jsonb,

  -- Vertical-level benchmarks, computed across questions
  -- Shape: { avg_mention_share, p75_mention_share, top_mention_share, sample_size }
  benchmarks          jsonb         NOT NULL DEFAULT '{}'::jsonb,

  -- Slot for GBP Insights aggregated by area (deferred — populated when
  -- Google approval comes through). Shape designed but stays null at launch.
  observed_funnel     jsonb         DEFAULT NULL,

  refreshed_at        timestamptz   NOT NULL DEFAULT now(),
  refresh_status      text          NOT NULL DEFAULT 'fresh',  -- 'fresh' | 'refreshing' | 'stale' | 'failed'
  refresh_error       text          DEFAULT NULL,

  created_at          timestamptz   NOT NULL DEFAULT now(),

  UNIQUE (vertical, city, country)
);

CREATE INDEX market_intelligence_lookup ON market_intelligence (vertical, city, country);
CREATE INDEX market_intelligence_stale ON market_intelligence (refreshed_at) WHERE refresh_status = 'fresh';
```

### Historical snapshots: `market_intelligence_history`

Drift / Progress card depends on having a previous-month baseline. We
snapshot before every refresh.

```sql
CREATE TABLE market_intelligence_history (
  id                  uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id           uuid          NOT NULL REFERENCES market_intelligence(id) ON DELETE CASCADE,
  snapshot_month      date          NOT NULL,            -- first of month, e.g. '2026-05-01'
  questions           jsonb         NOT NULL,
  top_businesses      jsonb         NOT NULL,
  benchmarks          jsonb         NOT NULL,
  snapshotted_at      timestamptz   NOT NULL DEFAULT now(),

  UNIQUE (market_id, snapshot_month)
);

CREATE INDEX market_intelligence_history_lookup ON market_intelligence_history (market_id, snapshot_month DESC);
```

### ~~Per-business branded search tracking~~ — DROPPED post-Phase-0

The `business_branded_search` table is not built. Branded search
tracking is replaced by category-volume tracking, which uses the
existing `market_intelligence` row + `market_intelligence_history`
snapshots. No new table needed.

If GBP Insights API access is granted post-launch, a new table
`business_gbp_insights` will store the per-business observed funnel
(profile views, calls, directions). Designed when approval lands.

### Per-audit visibility snapshot: extend `audits.raw_results`

No new table needed. Add a `market_visibility` block to existing
`audits.raw_results`:

```json
{
  "market_visibility": {
    "market_id": "uuid",
    "questions_covered": 8,
    "questions_total": 50,
    "weighted_mention_share": 0.12,
    "position_avg": 2.3,
    "sentiment_avg": 0.7,
    "vertical_avg_share": 0.18,
    "vertical_p75_share": 0.35
  }
}
```

This is what the dashboard and ROI v2 read at audit time. Snapshotted
on every audit, so historical comparison is a simple SELECT against
the existing `audits` table.

### RLS

`market_intelligence` and `market_intelligence_history` are **NOT
RLS-restricted**. They're shared resources across all customers in
the same (vertical, city). Reads are open to authenticated users;
writes only via service_role from the refresh worker.

`business_branded_search` IS RLS-restricted (per-business). Standard
`user_id = auth.uid()` policy via join on businesses.

---

## Question Layer — how the ~50 questions are discovered

Each `market_intelligence.questions[]` entry:

```json
{
  "question": "massage therapy near me",
  "intent": "commercial",
  "search_volume": 2400,
  "competition": "MEDIUM",
  "cpc": 1.8,
  "monthly_searches": [{"year":2026,"month":3,"search_volumes":2400}, ...],
  "last_seen": "2026-05-19T...",
  "mentions": {
    "chatgpt":    [{ "name": "X1 Clinic", "place_id": "...", "position": 1, "strength": "strong", "sentiment": 0.8 }],
    "perplexity": [...],
    "google_ai":  [...]
  }
}
```

### Discovery sources (in priority order — POST-PHASE-0)

1. **DataForSEO `keywords_for_keywords` (Keywords Data API)** —
   primary discovery path, **city-level**.
   - Endpoint: `/v3/keywords_data/google_ads/keywords_for_keywords/live`
   - Body uses `location_code` (integer) for city granularity, e.g.
     Burlington = 1002197, Toronto = 1002451. See "City location_code
     mapping" below.
   - Seed list: vertical baseline (e.g. `["dentist", "dental clinic",
     "family dentist"]`) — kept minimal because Google Ads' related-
     keyword graph expands them broadly.
   - Returns 1,400-3,500 keywords with city-level volume, competition,
     CPC, and monthly_searches in a single call.
   - Cost: ~$0.075 per (vertical, city) call.

2. **DataForSEO PAA expansion** (`/v3/serp/google/organic/live/advanced`)
   - For the top 3-5 questions from step 1, pull `people_also_ask`.
   - Adds 4-8 follow-on questions per query when Google renders PAA
     (which is not universal — healthcare in mid-cities often
     returns no PAA block).
   - Cost: ~$0.002 per call.

3. **Hand-curated seed templates per vertical** — baseline seeds for
   step 1. Living in `api/integrations/dataforseo.py` (Phase 1):

   ```python
   BASELINE_SEEDS = {
     "dentist":         ["dentist", "dental clinic", "family dentist"],
     "restaurant":      ["restaurant", "dining", "food near me"],
     "physiotherapist": ["physiotherapy", "physiotherapist", "physio clinic",
                         "rehabilitation"],
     "chiropractor":    ["chiropractor", "chiropractic clinic"],
     "optometrist":     ["optometrist", "eye doctor", "eye exam"],
     "family_doctor":   ["family doctor", "walk in clinic", "medical clinic"],
     "veterinarian":    ["veterinarian", "vet clinic", "pet hospital"],
     "salon":           ["hair salon", "beauty salon", "nail salon"],
     "lawyer":          ["lawyer", "law firm", "legal services"],
     "accountant":      ["accountant", "tax preparation", "bookkeeping"],
     "realtor":         ["realtor", "real estate agent", "homes for sale"],
     "plumber":         ["plumber", "plumbing service", "emergency plumber"],
     "auto_repair":     ["auto repair", "mechanic", "car service"],
     "cleaning_service":["cleaning service", "house cleaners", "maid service"],
     "personal_trainer":["personal trainer", "fitness coach", "gym"],
     "cafe":            ["cafe", "coffee shop", "breakfast"],
     "retail":          ["store", "shop"],
     "other":           []   # forces seed augmentation from services field
   }
   ```

### Per-business sub-type augmentation (KEY POST-PHASE-0 ADDITION)

The baseline seed set isn't enough. Phase 0 proved this: James Snow
Physiotherapy returned only 3 keywords with the baseline
`["physiotherapy", "physiotherapist", "physio clinic"]` seeds — clinical
names that real customers don't search. With multi-disciplinary
seeds reflecting **actual services offered** (`["massage therapy",
"rmt near me", "chiropractor", "acupuncture", "naturopath", "mva
rehabilitation", "back pain treatment"]`), the same business returned
1,642 keywords with 903 having city-level volume.

**The rule: the cached (vertical, city) baseline is augmented at
audit time with business-specific seeds derived from the existing
website signal extractor.**

The signal extractor already exists and runs on every audit:
- For restaurants: extracts cuisine + dietary signals (commit
  `bc7ec1a`). Examples: `egyptian`, `halal`, `vegetarian`, `vegan`,
  `gluten-free`, `italian`, `indian`.
- For clinics / multi-service businesses: extracts service categories
  (commit `325334f`). Examples for a clinic: `physiotherapy`,
  `chiropractic`, `massage therapy`, `acupuncture`, `naturopathy`,
  `mva rehabilitation`, `wsib rehabilitation`, `orthotics`. For a
  dentist: `general dentistry`, `cosmetic`, `invisalign`, `implants`,
  `pediatric`, `emergency`.

At audit time, the seed-augmentation step:

```
1. Load cached baseline keywords for (vertical, city).
2. Read business.detected_signals from latest audit
   (services + cuisine + dietary + specialty).
3. Build augmentation seed list: BASELINE_SEEDS[vertical] +
   converted signals (e.g. cuisine="halal" → seed "halal restaurant",
   service="massage" → seed "massage therapy near me").
4. Call keywords_for_keywords ONCE per audit with the augmentation
   seeds + city location_code. Returns ~500-1,500 additional
   business-specific keywords with volume.
5. Merge with cached baseline. Deduplicate by keyword string.
   Re-rank by volume × intent.
6. Use the combined set for the business's audit and ROI math.
```

**Cost per business per audit: +$0.075** for the augmentation call
(one call, regardless of how many services the business offers).
Cache row is unaffected — the augmentation is per-audit overlay, not
written back to the shared cache.

**Why augmentation isn't cached per business:** the business's own
services don't change often, but the keyword graph that Google Ads
returns for those services DOES (volumes shift monthly, new
city-specific variants appear). Re-querying each audit ensures
freshness without inflating the cache to thousands of rows. The
$0.075 is rounded into the per-audit cost.

### Discovery example (real numbers from Phase 0)

For James Snow Physiotherapy (multi-disciplinary clinic, Milton):

| Step | Seeds | Result |
|---|---|---|
| Baseline (vertical cache) | `[physiotherapy, physiotherapist, physio clinic]` | 3 keywords, all null volume |
| **Augmentation from services** | `[massage therapy, rmt near me, chiropractor, acupuncture, naturopath, mva rehabilitation, ...]` | **1,642 keywords, 903 with volume** |
| Top result | — | `massage near me` sv=2,400 in Milton |

Without augmentation: 0 usable signal. With augmentation: 903 keywords
worth of usable signal. The pattern generalizes — every vertical
benefits, but multi-service businesses (clinics, salons, auto repair,
home services) benefit most.

### Question refresh cadence

- Question **list** refreshes quarterly per cached (vertical, city)
  combo (the keyword universe doesn't churn fast)
- Question **mentions** (who AI engines mention for each question)
  refresh monthly
- **Per-business augmentation runs every audit** (≈monthly per
  customer), so business-specific keywords are always fresh
- Each step stored independently; the refresh job knows which
  sub-task is due

### City location_code mapping

Keywords Data API supports city-level via integer codes. Maintained
two ways:

1. **Hardcoded lookup table** in `api/integrations/dataforseo.py` for
   common Ontario cities (Burlington 1002197, Mississauga 1002350,
   Milton 1002347, Oakville 1002371, Brampton 1002191, Toronto
   1002451, Hamilton, Ottawa, etc.) — populated at install time, no
   runtime cost.

2. **Runtime fallback** via
   `/v3/keywords_data/google_ads/locations` (zero cost, returns 5,888
   Canadian locations including 1,048 cities + 1,319 municipalities)
   when a new city signs up that isn't in the hardcoded table.
   Result cached locally to avoid repeated lookups.

---

## Mention Extraction — what we capture per AI response

The audit already runs each question through ChatGPT + Perplexity +
Google AI Overview. We're extending the extraction, not adding new
API calls.

For each AI response, extract for each business mentioned:

- **`name`** — business name as written by the AI
- **`place_id`** — normalized via SerpApi google_maps lookup (so two
  AI mentions of the same business in slightly different name forms
  count as one)
- **`position`** — order of mention in the response (1 = first
  business mentioned, 2 = second, etc.)
- **`strength`** — one of `strong` (e.g. "I recommend X"), `moderate`
  (e.g. "X is well-regarded"), `weak` (e.g. "options include X")
- **`sentiment`** — float 0..1 (LLM-scored, single call per response
  with a structured prompt)

A first-position strong recommendation contributes more to weighted
mention share than a third-position weak mention. Specific weights:

```
weight = position_weight × strength_weight × (0.5 + 0.5 × sentiment)

position_weight: 1 → 1.0, 2 → 0.6, 3 → 0.4, 4+ → 0.2
strength_weight: strong → 1.0, moderate → 0.6, weak → 0.3
```

These constants live in `api/aeo/market_intelligence.py` so they
can be tuned without a migration.

### LLM extraction cost

One Claude / GPT-4o-mini call per AI response to extract the
structured mention data. ~$0.001 per call. At 50 questions × 3
engines per refresh = 150 extractions per refresh = ~$0.15. Trivial.

---

## ROI v2 Formulas

### Variables

- `Q` = the question set for the customer's (vertical, city)
- `V(q)` = search volume for question q
- `M_b(q)` = weighted mention score for business b on question q
  (sum across engines, using the weight formula above)
- `M_total(q)` = sum of weighted mention scores across the top 10
  mentioned businesses for q
- `share_b` = Σ_q (M_b(q) × V(q)) / Σ_q (M_total(q) × V(q))
- `value_per_lead` = (vertical default or owner-provided) × estimated
  conversion rate from view-to-customer
- `ai_share_of_traffic` = 0.22 (existing constant, will revisit)

### Formula A — primary path (volume-weighted)

```
captured = share_b × Σ_q V(q) × value_per_lead × ai_share_of_traffic
potential = POTENTIAL_CEILING × Σ_q V(q) × value_per_lead × ai_share_of_traffic
exposure = potential − captured
upside = (target_share − share_b) × Σ_q V(q) × value_per_lead × ai_share_of_traffic
   where target_share = min(POTENTIAL_CEILING, vertical_p75_share)
```

Display: always as a range with ±20% uncertainty band (current
`formatCadRange` behavior preserved).

### Formula B — fallback when no volume data (SerpApi-only path)

```
question_coverage = |questions where business is mentioned| / |total questions|
captured = question_coverage × industry_default_monthly_volume × value_per_lead × ai_share_of_traffic
... (same downstream math)
```

Less precise but the same shape. The owner sees the same UI; only the
backing math differs.

### Formula C — current composite path (kept as final fallback)

When there is no market_intelligence row at all (new vertical+city,
refresh failed, etc.), fall back to the current score-based formula
exactly as it works today. The UI flags this as "estimated from your
audit signals" so the owner knows it's the less-precise path.

### Why this is better than the current formula

- Removes the dependency on `monthly_new_online_customers` (which
  owners often don't know)
- Grounded in observable AI behavior, not score → revenue
  correlation
- Naturally produces the "top 4 mentioned businesses" leaderboard for
  the dashboard
- Vertical benchmarks (`vertical_avg_share`, `vertical_p75_share`)
  give the owner immediate context for whether their share is good
  or bad

### Owner inputs in v2

`monthly_new_online_customers` becomes **optional and de-emphasized**.
We surface `avg_customer_value_cad` more prominently because it's the
one number the owner reliably knows. Everything else is observable.

---

## Vertical Benchmarks

Computed during refresh and stored in `market_intelligence.benchmarks`:

```json
{
  "avg_mention_share": 0.18,
  "p75_mention_share": 0.35,
  "top_mention_share": 0.62,
  "sample_size": 12,
  "computed_at": "2026-05-18T..."
}
```

Displayed in the dashboard as a horizontal bar with three markers:
- Your share (e.g. 0.12)
- Vertical average (e.g. 0.18)
- Top quartile (e.g. 0.35)

When `sample_size < 5`, we show "Not enough data in your area yet"
instead of misleading benchmarks. This avoids the cold-start problem
where the first dentist in a city sees themselves as "the worst"
because they're the only data point.

---

## Category-Volume Tracking (REPLACES Branded Search Tracking)

### Why branded search was dropped

Phase 0 found that Google Ads returns `null` volume for almost every
SMB branded query (below the ~10/mo exposure threshold):

- Burlington Family Dentists → null
- 4 Seasons Plumbing → 40 (just barely above null)
- Salon West → 320
- James Snow Physiotherapy → null
- Masrawy Egyptian Kitchen → 12,100 (almost certainly cross-brand
  contamination — implausibly high for a single Mississauga
  restaurant; Google is likely matching "Masrawy" against unrelated
  entities)

Two distinct failure modes (null and contamination) make per-business
branded volume an unreliable lagging indicator. **Dropped from the
launch architecture.**

### What replaces it — category-volume tracking

Instead of "did people search your business name?", we track **"did
the category demand in your area grow?"** This uses the same data we
already pull for the question layer — no new API calls, no extra cost.

For each (vertical, city), every monthly refresh stores the
aggregate volume across the top-50 questions:

```json
{
  "category_volume_summary": {
    "month": "2026-05-01",
    "total_volume": 18420,
    "top_5_keywords": [
      { "keyword": "dentist near me", "search_volume": 1300 },
      { "keyword": "family dentist", "search_volume": 590 },
      ...
    ],
    "n_with_volume": 578,
    "rising_keywords": [
      { "keyword": "invisalign burlington", "change_pct": 0.35 },
      ...
    ]
  }
}
```

Snapshotted to `market_intelligence_history` monthly. The Progress
card on the dashboard surfaces:

- "Dental searches in Burlington grew 8% this month"
- "Top rising query: 'invisalign burlington' +35%"
- "Your AI mention coverage stayed at 12% of questions while category
  searches grew — your share is shrinking"

### Why this is better than branded search

| | Branded search | Category-volume |
|---|---|---|
| Coverage | Null for most SMBs | Populated for every active (vertical, city) — we already use this data |
| Cross-brand contamination | Severe (Masrawy example) | None — category-level by design |
| Cost | $10/mo at 100 customers | $0 (reuses question-layer pulls) |
| Signal type | Lagging proxy for own visibility | Direct demand-side measurement |
| Tells owner | "people searched your name" | "category demand grew/shrank; here's where you stand" |

### What's still missing without branded search

Branded search would have answered "did our work CAUSE people to
search you specifically?" Category-volume can't answer that — it
measures demand, not your share of it. To close that gap we still
need:

1. **AI mention frequency over time** (already in scope, no new
   work) — month-over-month change in mentions for the business
   across the question set
2. **GBP Insights** when Google approval lands (post-launch) —
   actual profile views, calls, directions

These two together cover what branded search would have. Track
explicitly during soft launch: do customers find "category grew X%
but my mentions stayed flat" actionable? If yes, no gap. If they
ask "but did people search FOR ME specifically?", revisit.

---

## Scope-aware fallback

The cached intelligence layer assumes a local business with a defined
(vertical, city). Non-local businesses need graceful degradation.

### Gate via existing `businesses.competitor_scope`

- `scope = local`: full cached intelligence path
  - Look up / create market_intelligence row
  - Run audit, populate `market_visibility` block
  - ROI uses Formula A or B
  - Show "top mentioned businesses in your area" leaderboard
  - Show vertical benchmark bar

- `scope = country` or `scope = global`: basic mention path
  - Skip market_intelligence lookup entirely
  - Run the existing 3-6 query audit (current behavior)
  - ROI uses Formula C (current composite path)
  - Hide "top mentioned businesses in your area" UI (replace with a
    note: "Area comparison is shown for businesses serving a defined
    city or region")
  - Hide vertical benchmark bar

### Onboarding signal

Add a one-line note in onboarding Step 2: *"LeapOne works best for
businesses serving a defined city or region — let us know if that's
not you."* Doesn't block signup; just signals fit.

When/if we get enough non-local customers to justify it, build a
`market_intelligence` variant keyed on `(vertical, scope_geo)` where
`scope_geo` can be `'Ontario'`, `'Canada'`, `'global'`, etc. Don't
build it now.

---

## GBP Insights — Deferred Slot

Designed-for but not built. When Google reapproval lands (scheduled
July 2026), GBP Insights becomes a per-business signal that lives in
`audits.raw_results.observed_funnel`:

```json
{
  "observed_funnel": {
    "profile_views": 1890,
    "search_impressions": 4200,
    "calls": 23,
    "direction_requests": 41,
    "website_clicks": 78,
    "month": "2026-05",
    "source": "gbp_insights_api"
  }
}
```

When present, ROI shifts from "estimated exposure" to "observed
funnel ROI": we have profile views, calls, direction requests — real
behavior. The estimated revenue impact becomes:

```
estimated_revenue = (calls × close_rate × avg_customer_value)
                  + (direction_requests × walk_in_close_rate × avg_customer_value)
                  + (website_clicks × site_conversion_rate × avg_customer_value)
```

Each conversion rate has a vertical default; advanced owners can
override in Settings.

**Critical:** do not build the architecture assuming GBP Insights
will be approved. Launch without it. Treat it as a post-launch boost
that slots into a pre-designed schema field.

---

## Refresh Worker Design

A FastAPI scheduled task (Railway cron or APScheduler) that handles:

1. **Monthly mention refresh** — for every `market_intelligence` row
   where any business has scope=local, re-query the questions and
   update mentions. ~150 AI calls per row.

2. **Quarterly question-list refresh** — re-discover questions via
   DataForSEO for each row. ~$0.06 per row.

3. **Monthly branded search refresh** — for every active business,
   pull branded search volume for the current month.

4. **Snapshot before refresh** — copy current `market_intelligence`
   row to `market_intelligence_history` before overwriting.

### Cron schedule

- 1st of every month, 02:00 UTC: monthly mention refresh + branded
  search refresh
- 1st of Jan, Apr, Jul, Oct: quarterly question-list refresh
  (preceded by the monthly refresh)

### On-demand triggers

- Business signup with new (vertical, city) combo → trigger refresh
  immediately, run audit in parallel; merge results when both done
- Cache hit but `refreshed_at > 45 days ago` → trigger background
  refresh, use stale data for the immediate audit, swap in fresh
  data on next audit

### Refresh status state machine

```
fresh → refreshing → fresh (success)
fresh → refreshing → failed (error stored, fresh data still
                              accessible for read)
fresh → stale (auto-flagged at 45 days since refresh)
stale → refreshing → fresh
```

Audits never block on a refresh. Stale data is always served if
fresh isn't ready.

### Idempotency

Refresh jobs are keyed on `(market_id, target_month)`. Re-running a
month's refresh is a no-op if it already succeeded. This is critical
for retry safety.

---

## Cache Lifecycle

| Event | Behavior |
|---|---|
| Business signup with new (vertical, city) | Create row, status=refreshing, trigger async refresh worker, run audit in parallel with current 3-query path. Merge results. |
| Business signup with existing (vertical, city) | Cache hit, status=fresh, use existing data. $0 cost. |
| Monthly cron | For every (vertical, city) with at least 1 active customer, snapshot to history + trigger mention refresh. |
| Quarterly cron | Same set, but also re-discover questions. |
| All customers in (vertical, city) churn | Stop refreshing — row goes stale and stays stale until a new customer signs up there. Not deleted (history is useful). |
| Manual force refresh | Behind a quota — owner can trigger 1 per month per business via dashboard button. |

---

## Cost Model (UPDATED post-Phase-0)

Assumes 100 paying customers, ~30 unique (vertical, city) combos.
Pricing reflects observed DataForSEO costs from Phase 0 testing.

| Item | Frequency | Cost / unit | Monthly | Annual |
|---|---|---|---|---|
| Monthly mention refresh — AI engines × top-50 questions × 30 combos | Monthly | $0.005 SerpApi avg per call | $22.50 | $270 |
| Mention extraction (LLM structured output, 150 per combo × 30) | Monthly | $0.001 | $4.50 | $54 |
| Quarterly question refresh — `keywords_for_keywords` × 30 combos | Quarterly | $0.075 per combo | $0.75 | $9 |
| Per-business sub-type augmentation — every audit | Monthly per business × 100 | $0.075 | $7.50 | $90 |
| Category-volume snapshot — derived from question refresh, no new calls | Monthly | $0 | $0 | $0 |
| ~~Branded search~~ — DROPPED | — | — | $0 | $0 |
| One-time question discovery for new (vertical, city) combo | Per new combo | $0.075 | varies | varies |
| One-time historical trend for top-3 keywords on new combo | Per new combo | $0.075 | varies | varies |

**Total recurring: ~$35/month at 100 customers.** At $3,900 MRR,
that's **~0.9% of revenue**. Per-business augmentation is the new
cost line that didn't exist in the original plan — small ($0.075 per
audit) but it does scale with customer count (not combo count).

### Scaling concerns (updated)

| Customers | Combos | Cache cost | Augment cost | Total / mo | % of revenue |
|---|---|---|---|---|---|
| 100 | 30 | ~$27 | $7.50 | ~$35 | 0.9% |
| 500 | 100 | ~$92 | $37.50 | ~$130 | 0.7% |
| 1,000 | 180 | ~$165 | $75 | ~$240 | 0.6% |
| 5,000 | 600 | ~$550 | $375 | ~$925 | 0.5% |

Cost as % of revenue still **decreases** with scale (combos
saturate), but more slowly than the pre-Phase-0 model because
augmentation scales linearly with customers, not combos.

---

## Build Order

Sequenced for shortest path to a testable end-to-end story. Each
step is independently demoable.

### ~~Phase 0 — Validate~~ ✓ COMPLETE (2026-05-19)
- DataForSEO confirmed as data source with adjustments documented in
  the "Phase 0 Validation — Outcome" section at the top of this doc.
- Total cost: ~$3.50.
- Runner: `scripts/dataforseo_test/runner.py` (reusable for future
  re-validation).

### Phase 1 — Schema + lookup (~1 day)
- Migration 023: `market_intelligence`, `market_intelligence_history`.
  Skip `business_branded_search` (dropped).
- `api/aeo/market_intelligence.py` with `get_or_create(vertical, city,
  country)` (sync read, no refresh yet).
- `api/integrations/dataforseo.py` — thin client wrapping
  `keywords_for_keywords`, `serp_advanced`, `keywords_for_site`,
  `search_volume`, plus the `CITY_LOCATION_CODES` lookup table and
  fallback resolver.

### Phase 2 — Refresh worker (~3 days)
- Question discovery via `keywords_for_keywords` at city level
  (`location_code`). Baseline seeds from the `BASELINE_SEEDS` table.
- PAA expansion via SERP advanced for the top 5 questions.
- Mention extraction (extend existing AI engine call paths with
  structured-output prompts for position / strength / sentiment).
- Top-businesses aggregation.
- Benchmarks computation.
- Category-volume snapshot (computed at end of refresh, written to
  `market_intelligence_history`).
- Idempotent retry-safe job structure.

### Phase 3 — Signup integration + per-business augmentation (~2 days)
- On business creation, async-trigger refresh if new combo.
- Cache-aware audit flow: read market_visibility from row, write
  per-audit snapshot to `audits.raw_results`.
- **Per-business sub-type augmentation**: at audit time, read
  `business.detected_signals` (services / cuisine / dietary /
  specialty — already extracted by the existing pipeline), convert
  to seed terms, run ONE `keywords_for_keywords` call with those
  seeds + city location_code, merge results with baseline cache.
  Critical path — without this, multi-service businesses get
  near-zero usable signal (see James Snow example in Phase 0
  outcome).

### Phase 4 — ROI v2 (~2 days)
- `apps/web/lib/roi.ts` extended with `computeRoiFromMarketVisibility()`
  (Formula A) and `computeRoiFromQuestionCoverage()` (Formula B)
- Existing `computeRoi()` (Formula C) preserved as fallback
- `RoiHeroCard.tsx` updated to display whichever path produced
  numbers, with a small footer indicating data source

### Phase 5 — Monthly Insights card (~3 days)
- New `MarketInsightsCard.tsx` on dashboard
- Shows: top 10 questions in your area, your appearance share per
  question, top 4 mentioned businesses, vertical benchmark bar,
  month-over-month deltas
- Mounted below the Progress card

### Phase 6 — Category-volume tracking + dashboard surface (~1 day)
- Category-volume snapshot writes already happen in Phase 2's
  refresh worker. This phase wires the dashboard reads:
  - "Category demand in {city} grew/shrank X% this month"
  - Top 3 rising queries for the business's area
  - Comparison: their AI mention coverage vs category growth
- **Replaces the original Phase 6 plan (per-business branded search)
  which was dropped post-Phase-0.** No new API costs.

### Phase 7 — Scope-aware fallback (~0.5 day)
- One if-branch in audit pipeline keyed on `competitor_scope`
- UI guards on Monthly Insights card / benchmark bar to hide for
  non-local

### Phase 8 — Monthly scheduled refresh (~1 day)
- Cron entry, snapshot-before-refresh logic, error reporting

### Total estimate

~12 working days for a focused build. Realistically **3 weeks
elapsed** assuming normal interruptions.

### Launch timing impact

- Original target: July 2026
- With this work: **late August / early September 2026**

Trade-off accepted because launching without this risks one-time-use
churn (the explicit reason for this work).

---

## What's Deliberately NOT in v1

- **Don't track non-customer cities.** Marketing temptation: "we
  have data on every Canadian city" sounds good. Reality: refresh
  cost explodes and most cities have no customers to monetize. Only
  refresh combos with at least 1 paying customer.

- **Don't refresh more often than monthly.** Daily / weekly refresh
  is 30x / 4x the cost respectively for marginal customer-visible
  benefit. AI engine outputs for stable verticals don't change that
  fast.

- **Don't surface every tracked question to the owner.** Top 10 by
  volume × intent. Information overload kills the "fresh insight"
  feel.

- **Don't build a public market reports page.** Even though the
  cache enables it, it's a distraction from in-app polish.
  Post-launch decision.

- **Don't auto-rebuild competitor lists from `top_mentioned_businesses`.**
  Show them as a separate leaderboard. The owner's curated list
  ([[project_competitor_curation]]) is preserved as the canonical
  comparison set. The leaderboard is informational.

- **Don't build province / country / global scope tiers.** Defer
  until a real customer needs it.

- **Don't expose the data extraction prompts to owners.** They're
  internal implementation. We can publish "how it works" in a help
  doc but don't surface the prompts themselves (they will be tuned
  often).

---

## Open Decisions

### Resolved by Phase 0

- ~~Discovery endpoint~~ — **`keywords_for_keywords` (Keywords Data,
  city-level via `location_code`)**, not `keyword_ideas` (Labs is
  country-only).
- ~~Branded search inclusion~~ — **dropped.** Replaced by
  category-volume tracking using existing question-layer data.
- ~~Q6 metric definition~~ — **count of keywords WITH non-null
  volume per city**, not raw breadth.
- ~~Whether all 18 verticals are supported~~ — **yes**, uniformly,
  via the per-business augmentation pattern using existing services
  + cuisine signal extraction.

### Still open

1. **Question count per combo: 50 vs 30 vs 100?**
   Recommendation unchanged: start at 30, expand to 50 after first
   month if coverage feels thin. Phase 0 returned 1,400-3,500
   keywords per combo, so we have plenty of pool to pick top-N from.

2. **`ai_share_of_traffic = 0.22` — keep or revisit?**
   Defer to month 3 post-launch. Now that branded search is dropped,
   the derivation path is: compare AI mention share changes to
   category-volume changes (does AI share track demand growth?).
   Needs 3+ months of category-volume history. Default 0.22 for
   now, document in ROI hero copy.

3. **Refresh cron platform: Railway cron, Supabase pg_cron, or
   APScheduler in-process?**
   Recommendation unchanged: Supabase pg_cron triggering a Railway
   HTTP endpoint. Keeps the worker stateless and easy to debug;
   avoids building cron infrastructure on Railway.

4. **Place_id normalization for AI-mentioned business names: who
   pays the SerpApi google_maps lookup cost?**
   ~$4.50/mo at 100 customers / 30 combos. Add to monthly cost
   model. Cache `name → place_id` mapping aggressively (it doesn't
   change). Acceptable.

5. **What happens when a business's name appears in an AI answer
   without a place_id resolve?**
   Recommendation: store the raw name, mark as unverified, exclude
   from `top_businesses` aggregation. Unverified mentions show in a
   "loosely matched" footer on the owner's dashboard so they can
   flag mis-spellings.

6. **Seed augmentation — what's the right max seed count per audit?**
   Phase 0 used 8-12 seeds for James Snow and got 1,642 keywords.
   `keywords_for_keywords` returns up to ~200 per seed. With 12
   seeds we're getting comprehensive coverage. Recommend cap at
   **15 seeds per audit** to keep response sizes manageable.
   Beyond 15, returns are duplicative.

7. **What if the services field is empty for a new business at
   first audit?**
   Skip augmentation for that audit; the next audit (after the
   service extractor has run on their website) will fill in. The
   owner can also manually add services in Settings to accelerate.
   No fallback needed beyond "skip and try next time."

---

## Honest Caveats and Risks

### Technical risks

- **AI engine output is noisy day-to-day.** A query that returned
  X1, X2, X3 yesterday might return X4, X1, X5 today. Monthly
  averaging is a partial mitigation but be skeptical of short-term
  movement in dashboards. Show monthly deltas, not daily.

- **Mid-city volume coverage is 50-77% of Toronto** (validated by
  Phase 0). Every test city had 500+ keywords with city-level
  volume, which is plenty for Formula A. The "Toronto has more
  data" finding is real but not catastrophic — we just need to be
  honest with customers that smaller cities have thinner data, and
  not over-promise precision.

- **PAA is not always rendered.** Phase 0 found that healthcare
  queries in mid-cities ("best family dentist burlington", "best
  physiotherapist milton") returned local_pack + organic +
  related_searches but **no PAA block**. The refresh worker must
  handle PAA-absent gracefully — fall back to `related_searches`
  for question expansion, or just skip the PAA step for that query.
  Don't fail the entire audit because PAA is missing.

- **Seed quality determines outcome quality.** Phase 0 found that
  James Snow Physiotherapy got 3 keywords with narrow clinical
  seeds vs 1,642 with multi-disciplinary seeds matching actual
  customer search behavior. **The `BASELINE_SEEDS` table must be
  curated by someone who understands how Canadians actually
  search**, not auto-derived from vertical names. Treat it as a
  living artifact — add to it whenever a new vertical underperforms.

- **Place_id resolution failures.** Some businesses mentioned in AI
  answers won't have a clean Google Maps match (new businesses,
  defunct businesses, businesses with very generic names). Plan
  for ~10% unresolved.

- **LLM extraction reliability for position / strength / sentiment.**
  These are subjective signals. Use a structured-output prompt and
  expect ~80% accuracy. Don't expose the raw scores to owners as
  precise numbers — bucket them ("strong" / "moderate" / "weak").

- **Google Ads `null` thresholds.** Volumes below ~10/mo come back
  as `null` from `search_volume`. We saw this not just on branded
  queries but on long-tail commercial queries like "best family
  dentist burlington" (0 in `search_volume` API but plenty of
  real-world intent). For ROI math, treat `null` as "below
  threshold" not "zero" — exclude from volume-weighting but include
  in question count.

### Product risks

- **The cached intelligence layer assumes owners care about
  question-level visibility.** If owners only care about "did I get
  more customers this month," visibility-share metrics are still
  one layer removed from what they want to know. Branded search +
  (eventually) GBP Insights bridges this gap. Watch retention
  metrics carefully in soft launch.

- **Cold-start in low-density areas.** First customer in (lawyer,
  Charlottetown) means `sample_size = 1` and benchmarks are
  meaningless. The "not enough data" UI guards against
  misinformation but means the customer's first month feels
  thinner than the dentist in Toronto's first month. Acceptable
  trade-off.

- **Customer claims "but I am mentioned, just under a different
  name."** AI engines sometimes refer to businesses by slightly
  varied names. Manual review tool in the admin panel would help;
  defer to post-launch if not blocking.

- **Owner over-indexes on the leaderboard and ignores their actual
  customers.** If a customer becomes obsessed with "why is X1
  always #1 in mentions?" they might miss bigger issues. The
  dashboard should always keep ROI / revenue at the top, with
  visibility as a diagnostic underneath.

### Business risks

- **DataForSEO pricing changes.** Locked-in pricing isn't
  guaranteed. Watch for changes; SerpApi PAA is the architectural
  fallback. Multi-source data is healthy here.

- **Google legal exposure if AI engine queries get aggressive.**
  ChatGPT and Perplexity have their own ToS for API use. Staying
  within their published rate limits and ToS is non-negotiable.

- **The defensive moat erodes over time.** Competitors can build
  the same cache. The real moat is **time + customer count + the
  vertical analysis layer on top**. Don't get complacent assuming
  the cache itself is the moat.

---

## Success Metrics

How we'll know this worked, measured at month 2 and month 3 post-launch:

- **Month-2 retention** of customers who saw the Monthly Insights
  card at least 3 times: target ≥ 75%.
- **Self-reported "this is useful"** in onboarding survey at end of
  trial: target ≥ 60% mention visibility / position vs competitors
  as a top-3 reason for converting to paid.
- **Branded search correlation**: across our customer base, customers
  whose AI mention share grew >20% in month 1 see branded search
  growth >10% in month 2. Validates the AI-to-name-recognition
  causal chain.
- **Cost stays under 3% of MRR.** If it exceeds 3%, we've
  over-engineered the refresh cadence or over-tracked questions.

---

## Migration Plan

1. Apply migration 023 (schema)
2. Run a backfill script for existing customers: create
   `market_intelligence` rows for each unique (vertical, city) with
   active customers. Don't auto-refresh (would spike cost); flag as
   `stale` so refresh worker picks them up.
3. Ship Phase 1-4 behind a feature flag (`MARKET_INTELLIGENCE_V1`).
4. Enable for internal testing on Burlington Family Dentists,
   Masrawy Egyptian Kitchen, James Snow Physiotherapy first.
5. Compare ROI v2 numbers to current ROI MVP for these accounts.
   Document material differences.
6. Roll out to all customers behind the flag.

---

## How this doc evolves

- After Phase 0 (DataForSEO test): update "Question Layer" with
  actual sources used.
- After Phase 4 (ROI v2): update "Formulas" with actual constants
  used after observation.
- After soft launch month 2: update "Success Metrics" with actuals
  and decide on wide-launch readiness.
- When GBP approval lands: move "GBP Insights — Deferred Slot" from
  deferred to active and update "Build Order."
