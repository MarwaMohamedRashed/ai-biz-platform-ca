# DataForSEO Test Plan

> **Purpose:** Validate whether DataForSEO is worth integrating into LeapOne to power the post-launch "Monthly Insights" retention feature (trending PAA questions, search volume movement, category intelligence). Test cost: under $1 of API credits. Decision time: ~1 hour of manual inspection.
>
> **Owner:** Mohamed Saleh
> **Created:** 2026-05-18
> **Status:** Pre-launch validation — to be completed before committing to Phase 4 (Category intelligence + onboarding preload).

---

## Context

[[project_roi_mvp]] and [[project_progress_card_phase2]] gave us the launch-month retention story: revenue framing + month-over-month drift. The longer-term retention engine still needs a "fresh-every-month insight" feature. The leading candidate is a Monthly Insights tab showing trending PAA questions in the owner's category + city, powered by DataForSEO.

Before committing 1-2 weeks of engineering work, we want to validate that DataForSEO actually returns useful data for mid-sized Canadian cities (Burlington, Milton, Mississauga — not just Toronto). The test plan below is **self-contained, no code required**, and produces a yes/no decision in about an hour.

If DataForSEO fails this test, we pivot — either to SerpApi free-tier PAA scraping or Reddit/Quora mining as the data source, or we drop the Monthly Insights feature in favor of expanding the Progress card and competitor-change alerts.

---

## Step 1 — Account + credits (~5 minutes)

1. Sign up at https://dataforseo.com — email + password, no credit card on file required.
2. Verify email; the dashboard gives you **$1 free credit** to start.
3. Top up with **$20** under "Billing" — enough for the entire test with margin.
4. Go to "API access" → **copy your login + password** (you'll use these as HTTP Basic Auth credentials for every request).

---

## Step 2 — No-code test environment (~10 minutes)

Pick whichever you're most comfortable with:

- **Postman** (recommended — saves request history so you can review later): import their official Postman collection from https://dataforseo.com/help-center/postman-collection.
- **DataForSEO's web "API Sandbox"** built into the dashboard. Works but less convenient for comparing responses.
- **`curl`** if you prefer command line.

For all of these, set **HTTP Basic Auth** using the login + password from Step 1.

---

## Step 3 — Pick 5 real test businesses

Use the ones we already have audit data for. Deliberately mix categories AND city sizes — we want to know if mid-sized cities have decent data, not just Toronto.

| # | Business                         | Category         | City               |
|---|----------------------------------|------------------|--------------------|
| 1 | Burlington Family Dentists       | dentist          | Burlington, ON     |
| 2 | Masrawy Egyptian Kitchen         | restaurant       | Mississauga, ON    |
| 3 | James Snow Physiotherapy         | physiotherapist  | Milton, ON         |
| 4 | A salon test account             | salon            | (your test city)   |
| 5 | A trades test account            | plumber          | (your test city)   |

---

## Step 4 — The three endpoints to test

For each business, run these three POST requests.

### A. Keyword Ideas — what are people actually searching in this category?

- **Endpoint:** `POST https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live`
- **Body (JSON):**

```json
[{
  "keywords": ["dentist", "dental clinic", "family dentist"],
  "location_name": "Burlington,Ontario,Canada",
  "language_name": "English",
  "limit": 100
}]
```

- **Returns:** ~100 related keywords with monthly search volume, CPC, and competition score.
- **Cost:** ~$0.01 per call.

### B. Keywords for Site — what your customer's site actually ranks for

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

- **Returns:** keywords this site already ranks for. Lets you see whether their existing content matches search intent.
- **Cost:** ~$0.01 per call.

### C. Google Organic SERP — pulls the actual PAA box for a query

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

- **Returns:** the full SERP including `people_also_ask` box, local pack, organic results.
- **Cost:** ~$0.005 per call.

---

## Step 5 — Trend movement across 3 months of history

For endpoint A specifically, also pull historical search volume to see month-over-month changes:

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

- **Returns:** monthly volume for each keyword across the date range.
- **Cost:** ~$0.05 per call.

---

## Step 6 — Inspect the output: three questions

For each business, sit with the responses and ask yourself **honestly**:

### Q1 — Are the keywords actionable?

Look at endpoint A's response. Are the top 20-30 keywords things a dentist would care about? Or generic noise like "dental insurance" / "dental anatomy" that doesn't help them at all?

- **Pass:** you can pick 5 keywords that feel like *"yes, owners would want to be visible for these."*
- **Fail:** most of the list feels random or too broad.

### Q2 — Do questions exist in mid-sized Canadian cities?

Look at endpoint C's `people_also_ask` for Burlington, Milton, Mississauga (not just Toronto). Are there real questions returned? Or does Google return "insufficient data" / empty arrays?

- **Pass:** 4-8 real PAA questions per query in mid-sized cities.
- **Fail:** PAA box is empty or has only 1-2 generic questions.

### Q3 — Does the trend data move month-to-month?

Look at endpoint A's historical volume. Do you see meaningful changes (a keyword going from 200/mo to 600/mo), or are all the numbers flat?

- **Pass:** at least 30% of keywords show >20% movement month-over-month.
- **Fail:** everything is flat — the "trending questions" feature would feel stale by month 2.

---

## Step 7 — Decision criteria

After inspecting all 5 businesses, mark each pass/fail for each question:

| Business                       | Q1 actionable? | Q2 PAA in mid-cities? | Q3 trend movement? |
|--------------------------------|----------------|------------------------|---------------------|
| Burlington Family Dentists     | ☐              | ☐                      | ☐                   |
| Masrawy Egyptian Kitchen       | ☐              | ☐                      | ☐                   |
| James Snow Physiotherapy       | ☐              | ☐                      | ☐                   |
| Salon test                     | ☐              | ☐                      | ☐                   |
| Trades test                    | ☐              | ☐                      | ☐                   |

- **≥4 of 5 businesses pass ≥2 of 3 questions** → DataForSEO is worth integrating. Proceed to Phase 4 (category intelligence + onboarding preload).
- **2-3 businesses pass** → data is mixed; specific verticals work better than others. Worth integrating but limit to those verticals at launch.
- **0-1 businesses pass** → kill DataForSEO. Pivot to a different data source (Reddit / Quora mining, your own aggregated audit data) or drop the Monthly Insights feature entirely.

---

## Step 8 — Expected total cost

- 5 businesses × 3 endpoints × ~$0.025 average ≈ **$0.40 across all categories**
- Plus historical volume calls (5 × $0.05) ≈ **$0.25**
- **Total: well under $1.** The $20 top-up is overkill but gives you room to test more queries if early results are promising.

---

## Honest things to watch for

1. **City-level data sparsity.** DataForSEO's keyword volume by city in Canada is sometimes thin. If "Burlington, Ontario" returns 5 keywords but "Toronto, Ontario" returns 500, you've found a limitation — Phase 4 would need a fallback to province or country level for smaller cities.

2. **PAA staleness.** Google's "People Also Ask" doesn't change as often as you'd hope. If month 2's PAA is 80% identical to month 1's, the "fresh monthly insight" pitch weakens.

3. **Keyword-to-question gap.** Keywords ≠ natural-language questions. A keyword like *"dentist Burlington"* is not a question. The actual ChatGPT / Perplexity prompts customers type are more conversational (*"where can I find a good family dentist in Burlington"*). DataForSEO doesn't give you those — for those, your own audit query patterns (what we already feed to ChatGPT / Perplexity) plus PAA scraping is closer.

4. **CPC ≠ relevance.** A high CPC means advertisers compete for the term, not necessarily that customers ask the question. Don't over-index on CPC when judging "actionable" in Q1.

---

## Notes for the engineer after the test

If the test passes and we proceed to Phase 4:

- DataForSEO uses **HTTP Basic Auth** — store the login+password as `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` env vars on the FastAPI backend, not the Next.js frontend (we don't expose category-intel calls to the browser).
- The endpoints called above are **`/live`** variants — synchronous, return data immediately. There's also a `/task_post` + `/tasks_ready` + `/task_get` async pattern that's cheaper at scale; revisit when usage warrants.
- Wrap with a thin abstraction (`api/integrations/dataforseo.py`) so we can swap providers later without rewriting calling code. See `feedback_supabase_mutations` for the same pattern applied to the Supabase client.
- Cache responses for at least 24 hours (probably 7 days for keyword volume, which only updates monthly anyway). Most cost savings come from caching, not from picking cheaper endpoints.
- Rate limits: 2000 req/min by default. Way above what we'd ever hit. No throttling logic needed at launch.

---

*End of plan. When done, summarize the pass/fail counts and we'll align on Phase 4 scope.*
