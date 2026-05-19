# DataForSEO Test Plan

> **Purpose:** Validate whether DataForSEO can power the cached market
> intelligence layer described in
> [market-intelligence-architecture.md](market-intelligence-architecture.md).
> Specifically: question discovery per `(vertical, city)`, search volume
> for ROI Formula A, PAA expansion, branded search tracking, and
> month-over-month stability.
>
> **Owner:** Mohamed Saleh
> **Created:** 2026-05-18 (refreshed for the architecture rewrite)
> **Executed:** 2026-05-19 — see Outcome section below.
> **Status:** Phase 0 of the market-intelligence build. **Complete —
> verdict: PROCEED_WITH_CAVEATS.**
> **Decision time:** ~1.5 hours of manual inspection. Test cost: ~$3.50
> of API credits (slightly higher than the original $1 estimate
> because of additional probe calls after the first run's
> location-format issue).

---

## Outcome (2026-05-19)

The test was executed via the automated runner at
`scripts/dataforseo_test/runner.py`. Final verdict:
**PROCEED_WITH_CAVEATS.** Architecture survives with three concrete
adjustments documented in
[market-intelligence-architecture.md](market-intelligence-architecture.md)
under "Phase 0 Validation — Outcome".

### Verdict matrix (after running twice — once with broken city-level
location_name on Labs, once corrected to Keywords Data with
location_code; and after the multi-disciplinary seed correction for
James Snow)

| Business | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|---|
| Burlington Family Dentists | PASS | PASS | PARTIAL | FAIL | PASS | PARTIAL (0.50) |
| Masrawy Egyptian Kitchen | PASS | PASS | PASS | PARTIAL | PASS | PARTIAL (0.61) |
| James Snow Physiotherapy (multi-disc seeds) | PASS | FAIL | PARTIAL | FAIL | PASS | PARTIAL (0.62) |
| Salon West | PASS | PASS | PARTIAL | PARTIAL | PASS | PARTIAL (0.73) |
| 4 Seasons Plumbing | PASS | PASS | PARTIAL | PARTIAL | PARTIAL | PARTIAL (0.77) |

### Key findings

1. **Discovery endpoint changed**: `dataforseo_labs/.../keyword_ideas`
   does not support city-level locations (Labs is country-only with
   only 94 locations worldwide). The Keywords Data API
   `keywords_for_keywords` DOES support city-level via integer
   `location_code` — switched to that.

2. **City-level data is real and rich**: 1,400-3,500 keywords per
   (vertical, city) with city-specific volumes. Mid-cities have
   50-77% of Toronto's data density — substantial signal for
   Formula A.

3. **Branded search (Q4) failed across the board.** Google Ads
   returns `null` for SMB branded queries below ~10/mo, and the
   non-null returns are often cross-brand contamination ("Masrawy
   Egyptian Kitchen" = 12,100/mo, implausibly high). **Phase 6
   dropped, replaced with category-volume tracking.**

4. **Healthcare verticals require service-based seed augmentation**
   (the James Snow lesson). With narrow seeds
   `[physiotherapy, physiotherapist, physio clinic]`: 3 keywords, 0
   with volume. With multi-disciplinary seeds reflecting actual
   services offered (massage, chiro, acupuncture, MVA rehab, etc.):
   **1,642 keywords, 903 with volume**. The architecture adopts a
   per-business sub-type augmentation pattern using existing
   services + cuisine/dietary signal extraction.

5. **PAA isn't universal.** Healthcare in mid-cities sometimes
   returns no PAA block. Refresh worker must handle this gracefully
   (fall back to `related_searches`).

### What this triggered in the architecture doc

- "Phase 0 Validation — Outcome" section added at top
- "Question Layer" rewritten with corrected endpoint and
  per-business augmentation pattern
- "Branded Search Tracking" REPLACED with "Category-Volume Tracking"
- "Schema" updated to drop `business_branded_search` table
- "Cost Model" updated with new per-audit augmentation cost ($0.075)
- "Build Order" marks Phase 0 complete; Phase 3 expanded to include
  per-business augmentation
- "Open Decisions" — 4 of 5 original questions resolved; 2 new ones
  added (seed cap, empty services handling)
- "Honest Caveats" — added Phase-0-discovered findings (PAA absence,
  seed quality dependency, null-volume thresholds)

### Re-running the test

The runner at `scripts/dataforseo_test/runner.py` is reusable. To
re-validate (e.g. before adding a new vertical, or quarterly):

```
python scripts/dataforseo_test/runner.py
```

Edit `scripts/dataforseo_test/config.json` to change test businesses.
City codes are hardcoded in `runner.py` (`CITY_LOCATION_CODES`). Add
new cities by querying
`/v3/keywords_data/google_ads/locations` and updating the table.

Raw test results from 2026-05-19 are at
`scripts/dataforseo_test/results/2026-05-19T04-49-57Z/` (gitignored
locally; archive a copy if you want long-term reference).

---

## Original plan — kept below for reference

The original test plan is preserved below because it documents the
methodology (Q1-Q6 thresholds, pass/fail criteria, decision matrix)
that the runner encodes. It's accurate except for two things noted
inline:
- Step 4A's endpoint is `keywords_for_keywords` (Keywords Data), not
  `keyword_ideas` (Labs). Documented in the Outcome section above.
- Step 4C (branded search) is now informational — we ran it to
  validate the architectural decision to drop Phase 6, not to use it
  for tracking.

---

## Why this test exists

The architecture commits the product to an observed-AI-visibility ROI
model. That model is only viable if a data source can reliably return:

1. **30+ usable questions** per `(vertical, city)` combo, even for
   mid-sized Canadian cities (Burlington, Milton, Mississauga — not
   just Toronto)
2. **Search volume per question** (Formula A's volume-weighting term
   depends on it)
3. **PAA / follow-on questions** to round out the question set
4. **Monthly branded-search volume** for business names ("Burlington
   Family Dentists" as a query)
5. **Stability over time** — volumes that don't swing wildly
   month-over-month, so quarterly question refresh is sufficient

DataForSEO is the leading candidate. If it fails one or more of these,
the architecture stays valid but the data source slot changes (SerpApi
PAA + curated seed templates as fallback — Formula A degrades to
Formula B with no volume weighting).

If DataForSEO fails on **all** of these, we pivot — drop the cached
intelligence layer entirely and reconsider the retention story.

---

## Step 1 — Account + credits (~5 minutes)

1. Sign up at https://dataforseo.com — email + password, no credit
   card required.
2. Verify email; dashboard gives you **$1 free credit** to start.
3. Top up with **$20** under "Billing" — overkill for the test, but
   leaves room for follow-up exploration if early results are
   promising.
4. Go to "API access" → **copy your login + password** (HTTP Basic
   Auth credentials for every request).

---

## Step 2 — No-code test environment (~10 minutes)

Pick whichever you're most comfortable with:

- **Postman** (recommended — saves request history so you can compare
  responses side-by-side): import their official Postman collection
  from https://dataforseo.com/help-center/postman-collection.
- **DataForSEO's web "API Sandbox"** built into the dashboard. Works
  but less convenient for comparing responses across endpoints.
- **`curl`** if you prefer command line.

Set **HTTP Basic Auth** using the login + password from Step 1.

---

## Step 3 — Pick 5 real test businesses

Same 5 as before — these mix verticals and city sizes. Mid-city
quality is the failure mode we're most worried about, so this matters.

| # | Business                         | Vertical            | City               | Branded query to test                    |
|---|----------------------------------|---------------------|--------------------|------------------------------------------|
| 1 | Burlington Family Dentists       | dentist             | Burlington, ON     | "Burlington Family Dentists"             |
| 2 | Masrawy Egyptian Kitchen         | restaurant          | Mississauga, ON    | "Masrawy Egyptian Kitchen"               |
| 3 | James Snow Physiotherapy         | physiotherapist     | Milton, ON         | "James Snow Physiotherapy"               |
| 4 | A salon test account             | salon               | (your test city)   | (the salon's real name)                  |
| 5 | A trades test account            | plumber             | (your test city)   | (the plumber's real name)                |

---

## Step 4 — The four endpoints to test

For each business, run these four POST requests.

### A. Keyword Ideas — top questions per `(vertical, city)`

This is the **primary question-discovery source** per the architecture
doc. We need 30+ keywords with volume per combo. Filter for
question / commercial intent at inspection time.

- **Endpoint:** `POST https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live`
- **Body (JSON):**

```json
[{
  "keywords": ["dentist", "dental clinic", "family dentist"],
  "location_name": "Burlington,Ontario,Canada",
  "language_name": "English",
  "limit": 100,
  "include_serp_info": false
}]
```

- **What to look for:**
  - At least 30 returned keywords have a non-zero `search_volume`
  - At least 10 of those look like questions or high-intent phrases
    ("best family dentist Burlington", "emergency dentist near me",
    "invisalign Burlington")
  - CPC + competition data is populated (these inform intent weighting
    later)
- **Cost:** ~$0.01 per call.

### B. SERP Organic + PAA expansion — follow-on questions

The architecture uses PAA expansion to broaden the question set from
~30 (Keyword Ideas only) to ~50. For each business, run this for the
top query identified in A.

- **Endpoint:** `POST https://api.dataforseo.com/v3/serp/google/organic/live/advanced`
- **Body:**

```json
[{
  "language_code": "en",
  "location_name": "Burlington,Ontario,Canada",
  "keyword": "best family dentist burlington",
  "device": "desktop"
}]
```

- **What to look for:**
  - `people_also_ask` block returns **4-8 questions** for the
    mid-city queries (not just Toronto)
  - Each PAA entry has a `title` (the question text) and ideally a
    `snippet` or `expanded_element`
  - Local pack + organic results are also populated (this is the
    same SERP data we'd use to verify scope-aware fallback for the
    `competitor_scope=local` path)
- **Cost:** ~$0.005 per call.

### C. Branded search volume — monthly volume for the business name

This validates branded-search tracking (Phase 6 of the architecture
build).

- **Endpoint:** `POST https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live`
- **Body:**

```json
[{
  "keywords": ["Burlington Family Dentists", "Burlington Family Dentists Burlington"],
  "location_name": "Canada",
  "language_name": "English",
  "include_serp_info": false
}]
```

- **What to look for:**
  - Both variants return a `search_volume` value (even if low — 10 or
    20 searches/month is fine and informative)
  - `monthly_searches` array is populated (gives us the historical
    baseline for Phase 6's day-one dashboard)
- **Cost:** ~$0.05 per call (returns up to 1000 keywords per call;
  cheap at this scale).

### D. Keywords for Site — what the customer's site already ranks for

Optional but informative for Phase 1 onboarding flow ("here's what
your site already ranks for, here's what AI doesn't know about you").
Run for businesses with a public website.

- **Endpoint:** `POST https://api.dataforseo.com/v3/dataforseo_labs/google/keywords_for_site/live`
- **Body:**

```json
[{
  "target": "burlingtonfamilydentists.ca",
  "location_name": "Canada",
  "language_name": "English",
  "limit": 50
}]
```

- **What to look for:**
  - At least 10 keywords returned for a real customer site
  - Volume populated so we can prioritize
- **Cost:** ~$0.01 per call.

---

## Step 5 — Trend stability across 3 months of history

The architecture commits to **monthly mention refresh + quarterly
question-list refresh**. That cadence only works if volumes are stable
enough that we're not missing major shifts during the 3-month gap
between question-list refreshes.

Pull 3 months of historical volume for each business's top 3 keywords
identified in Step 4A:

- **Endpoint:** `POST https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live`
- **Body:**

```json
[{
  "keywords": ["family dentist burlington", "invisalign burlington", "emergency dentist burlington"],
  "location_name": "Canada",
  "language_name": "English",
  "include_serp_info": false,
  "date_from": "2026-02-01",
  "date_to": "2026-05-01"
}]
```

- **What to look for:**
  - `monthly_searches` array contains 3+ months of data
  - Month-over-month volume swings are **mostly moderate** (i.e. fewer
    than ~30% of keywords swing by more than ~50% in any given month)
  - At least *some* keywords show meaningful change (proves the
    movement is real, not flat-line dummy data)
- **Cost:** ~$0.05 per call.

---

## Step 6 — Inspect the output: six questions

For each business, sit with the responses and answer these honestly.

### Q1 — Are the top 30 keywords actionable?

Look at A's response. Are at least 30 of the keywords things a dentist
would actually care about? Or generic noise ("dental insurance",
"dental anatomy") that wouldn't help an owner?

- **Pass:** ≥30 keywords feel like things owners would want visibility
  for; the top 10 by volume are obvious wins.
- **Fail:** Most of the list is generic / random / too broad.

### Q2 — Does PAA expansion add 4-8 questions per query in mid-sized cities?

Look at B's `people_also_ask` for Burlington, Milton, Mississauga
(not just Toronto). Are there real questions returned?

- **Pass:** 4-8 real PAA questions per query in mid-sized cities.
- **Fail:** PAA box is empty or has only 1-2 generic questions for
  most mid-city queries.

### Q3 — Is volume data populated for mid-city queries?

ROI Formula A weights questions by volume. If `search_volume` is null
or 0 for most mid-city keywords, Formula A degrades to Formula B (no
volume weighting). That's still acceptable but worth knowing.

- **Pass:** ≥70% of keywords for mid-city combos have a non-zero
  `search_volume`.
- **Partial:** Volume populated for the top 10 keywords but sparse
  further down. Acceptable — top 10 carry most of Formula A's signal.
- **Fail:** Most volumes are null or zero. Formula A is unusable;
  must drop to Formula B.

### Q4 — Does branded search work for actual business names?

Look at C's response. Did "Burlington Family Dentists" return any
volume data?

- **Pass:** Both name variants return non-null `search_volume`
  (even low values are fine — 10, 20, 50/mo).
- **Partial:** Only the longer form (with city) returns volume.
  Workable but means we always need the disambiguating form.
- **Fail:** Both return null. Branded-search tracking (Phase 6) is
  not viable via DataForSEO; fall back to a different signal or
  drop that feature.

### Q5 — Is the trend data stable enough for quarterly refresh?

Look at the 3-month history from Step 5. Quarterly question-list
refresh means we won't see new questions emerge until the next refresh
cycle (up to 3 months later). That's only OK if volumes don't swing
wildly.

- **Pass:** Most keywords (≥70%) show <50% month-over-month swing.
  The swings that do happen are mostly seasonal-looking, not
  whiplash. Quarterly question refresh is safe.
- **Partial:** Volumes swing more than expected, but the *ranking*
  of top 30 keywords is stable (top keywords stay on top). Quarterly
  refresh still works — we're just less confident about absolute
  ROI numbers month-to-month.
- **Fail:** Volumes whiplash + rankings reshuffle every month. We'd
  need monthly question-list refresh, which doubles question-layer
  cost. Decision point: pay the extra cost or drop volume weighting.

### Q6 — Is city-level data dense enough, or do we need province fallback?

Compare the keyword count and volume coverage between a Tier-1 city
(Toronto) and a mid-city (Burlington / Milton). If Burlington returns
substantially fewer keywords or sparser volume data, we need a
documented fallback to province-level data for ROI math.

- **Pass:** Mid-city combos return ≥80% as many keywords as the
  Tier-1 comparison, with comparable volume coverage. City-level
  data is the primary path for everyone.
- **Partial:** Mid-cities return 40-80% of Tier-1 count. We use
  city-level for the question text but fall back to province-level
  volume for ROI math. Architecture doc already calls this out as
  acceptable.
- **Fail:** Mid-cities return <40% of Tier-1 count. We'd need to
  serve all mid-city customers from province-level data, which
  reduces the local specificity of the product. Acceptable but a
  meaningful product downgrade.

---

## Step 7 — Decision criteria

Mark each pass/partial/fail for each question:

| Business                       | Q1 actionable? | Q2 PAA depth? | Q3 volume? | Q4 branded? | Q5 stability? | Q6 city vs province? |
|--------------------------------|----------------|----------------|------------|--------------|----------------|----------------------|
| Burlington Family Dentists     | ☐              | ☐              | ☐          | ☐            | ☐              | ☐                    |
| Masrawy Egyptian Kitchen       | ☐              | ☐              | ☐          | ☐            | ☐              | ☐                    |
| James Snow Physiotherapy       | ☐              | ☐              | ☐          | ☐            | ☐              | ☐                    |
| Salon test                     | ☐              | ☐              | ☐          | ☐            | ☐              | ☐                    |
| Trades test                    | ☐              | ☐              | ☐          | ☐            | ☐              | ☐                    |

### Decision matrix

- **≥4 of 5 businesses pass Q1 + Q2 + Q3 + Q4** → **PROCEED** with
  DataForSEO as the primary data source. Phase 1 schema work can
  start.
- **Q5 mostly partial, Q6 mostly partial or fail** → still proceed,
  but update the architecture's "Honest Caveats" with the actual
  failure mode and add the province-fallback path to Phase 2 work.
- **Q3 mostly fail** → proceed with Formula B (no volume weighting)
  instead of Formula A. Update architecture doc accordingly.
- **Q4 mostly fail** → drop Phase 6 (branded search tracking) and
  redesign the lagging-indicator story (probably skip it for v1).
- **≥4 of 5 businesses fail Q1 OR Q2** → **PIVOT.** Drop DataForSEO,
  use SerpApi PAA + curated seed templates for question discovery.
  Formula A is unavailable; product proceeds with Formula B.
- **All five businesses fail Q1 + Q2 + Q3** → reconsider the cached
  intelligence layer entirely. Possibly drop the moat-building
  ambition and ship with the current ROI MVP + Progress card alone.

---

## Step 8 — Expected total cost

- 5 businesses × 4 endpoints (A + B + C + D) at ~$0.02 avg → **~$0.40**
- Step 5 historical trend pulls: 5 × ~$0.05 → **~$0.25**
- Branded search variants in C: already counted above
- **Total: well under $1.**

The $20 top-up is overkill but gives you margin to do follow-up
exploration if early results raise questions (e.g. "what happens if I
seed with a different keyword list" / "what's the PAA depth for a
sub-specialty like cosmetic dentistry").

---

## Honest things to watch for

1. **City-level data sparsity is the most likely failure mode.**
   DataForSEO's keyword volume by city in Canada is reportedly thin
   for cities under ~100k population. If Burlington returns 5
   keywords but Toronto returns 500, Q6 fails and we need the
   province-level fallback.

2. **PAA staleness.** Google's "People Also Ask" doesn't change as
   often as you'd hope. If month 2's PAA is 80% identical to month
   1's, the "fresh monthly insight" pitch needs to lean on mention
   shifts (which DO change) rather than question shifts (which
   don't).

3. **Keyword-to-question gap.** Keywords ≠ natural-language questions.
   A keyword like `"dentist Burlington"` is not a question. The
   actual ChatGPT / Perplexity prompts customers type are more
   conversational (`"where can I find a good family dentist in
   Burlington"`). Our mention-extraction layer runs the keywords
   through AI engines as-is, then enriches with PAA for the
   question-shaped queries. Treat keyword counts as a discovery
   surface, not the final query set.

4. **CPC ≠ relevance.** A high CPC means advertisers compete for the
   term, not necessarily that customers ask the question. Don't
   over-index on CPC when judging "actionable" in Q1.

5. **Branded volume can be deceptively low.** A real dentist might get
   only 30 monthly searches for their name and still have a thriving
   practice. Low branded volume isn't a failure of the business —
   it just means branded-search is a weak signal for their tier.
   Note this in Q4's pass criteria — even 10/mo is acceptable.

6. **Trend "stability" cuts two ways.** Flat volumes mean quarterly
   refresh is safe, but also mean we can't surface "your category is
   trending up X%" insights to the owner. Find the middle ground:
   mostly stable for the bulk, with occasional real swings.

---

## After the test — what to update

If the test passes (or mostly passes), update these files before
starting Phase 1:

1. **[market-intelligence-architecture.md](market-intelligence-architecture.md)**:
   - Update "Question Layer" if any source-priority changes
   - Update "Honest Caveats and Risks" → "Technical risks" with
     observed failure modes
   - Update "Open Decisions" — strike Decision #2 (volume confidence)
     once you have actual numbers, and Decision #4 (place_id cost) if
     the test surfaces real estimates

2. **[feature-implementation-deep-dive.md](feature-implementation-deep-dive.md)**:
   - Update the "Research artifacts" pointer with the actual outcome

3. **Memory** (`~/.claude/projects/.../memory/`):
   - Either create `project_dataforseo_validation.md` capturing the
     test outcome and any architectural changes, or extend the
     existing `project_progress_card_phase2` memory

---

## Notes for the engineer after the test

If the test passes and we proceed to Phase 1:

- **HTTP Basic Auth** — store credentials as `DATAFORSEO_LOGIN` and
  `DATAFORSEO_PASSWORD` env vars on the FastAPI backend (Railway).
  **Never** in Next.js / frontend — this is a server-side-only API.
- **`/live` vs async** — the endpoints above are all `/live`
  (synchronous, immediate response). There's also a `/task_post` +
  `/tasks_ready` + `/task_get` async pattern that's cheaper at scale.
  Revisit when monthly refresh volume warrants — at launch scale
  (~30 combos × monthly), `/live` is fine and simpler.
- **Thin abstraction** — wrap calls in `api/integrations/dataforseo.py`
  exposing `get_keyword_ideas(seed, location)`,
  `get_paa(keyword, location)`,
  `get_branded_search_volume(queries, location)`,
  `get_historical_volume(keywords, location, date_from, date_to)`.
  Same pattern as the Supabase client wrapper (see
  `feedback_supabase_mutations`). Lets us swap to SerpApi PAA + curated
  templates without rewriting calling code if Q1/Q2 fail.
- **Cache responses aggressively.** Question-list responses cache for
  90 days (quarterly refresh). Branded-search responses cache for 30
  days. Historical volume can be cached indefinitely. Most cost
  savings come from caching, not from picking cheaper endpoints.
- **Rate limits:** 2000 req/min by default. Well above what we'd hit
  at launch. No throttling logic needed for v1.
- **Place_id normalization is a separate concern.** DataForSEO doesn't
  return place_ids; those come from SerpApi `google_maps`. The
  architecture doc handles this in mention extraction — no DataForSEO
  work needed here.

---

*End of plan. When done, paste the filled-in Step 7 table back into a
conversation with me and I'll align on which architecture-doc updates
are needed before we open Phase 1.*
