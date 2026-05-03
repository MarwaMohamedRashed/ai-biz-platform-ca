# AEO — Review Count & Rating Query: Technical Reference

**Last updated:** 2026-05-01  
**Status:** Stable — all known bugs fixed, recency check implemented

---

## Overview

The AEO audit needs to know a business's **Google review count**, **star rating**, and **review recency** to score two pillars:

| Pillar | Signal | Points |
|---|---|---|
| Reviews & Reputation | 50+ reviews | 12 |
| Reviews & Reputation | 10–49 reviews | 6 |
| Reviews & Reputation | Rating ≥ 4.5 | 10 |
| Reviews & Reputation | Rating 4.0–4.4 | 5 |
| Google Business Profile | Has a star rating | 5 |
| Google Business Profile | KG type/category set | 5 |

**Scoring note (updated 2026-05-01):** The GBP category points (5pts) now only apply when Google has returned a Knowledge Panel with a `type` field. A business that only appears in the local map pack — but has no Knowledge Panel — does not earn these points. This reflects the reality that a thin GBP profile, while visible, is not fully optimized.

**Review recency** is evaluated separately (see Step 5 below) and surfaces as a recommendation — it does not directly affect the pillar score.

This data does **not** come from the Google Business Profile API (we don't have access). It comes entirely from **SerpApi** — a paid scraper that returns structured Google search result data.

---

## Where the code lives

```
api/
  aeo/
    router.py          ← ALL review query logic lives here

apps/web/
  components/dashboard/
    AeoAuditCard.tsx   ← Renders pillar bars including Reviews
    RecommendationsList.tsx  ← Renders the "Get to 10+ reviews (current: X)" item
  app/[locale]/dashboard/
    page.tsx           ← Server page — fetches latest audit from Supabase, passes to components
```

---

## How the review count is fetched — step by step

### Step 1 — 3 category queries via SerpApi (`run_google_multi`)

File: `api/aeo/router.py` → `run_google_multi()`

The audit runs 3 Google search queries using SerpApi, all category-style:

```
best physiotherapy clinic in Milton, ON
physiotherapy clinic near Milton
top physiotherapy clinic Milton ON
```

Each query calls `_google_one()` which makes one GET request to:
```
GET https://serpapi.com/search
  ?api_key=...
  &engine=google
  &q={query}
  &location={city}
  &gl=ca
  &hl=en
```

SerpApi returns a JSON object. **Two places inside it may contain review data:**

#### A) `local_results.places` (the Google Maps "3-pack")

```json
{
  "local_results": {
    "places": [
      {
        "title": "James Snow Physiotherapy",
        "rating": 4.7,
        "reviews": 256,
        "position": 1
      }
    ]
  }
}
```

Extracted by `check_local_pack(data, search_name)`.  
The function loops through `places` and looks for `search_name` (the business name with the city suffix stripped) inside each place's `title`.  
Returns: `{ present, position, rating, reviews }`.  
**Important:** `reviews` here is the integer field from the local pack. It is often present when the business appears in the map pack.

#### B) `knowledge_graph` (the Google sidebar card)

```json
{
  "knowledge_graph": {
    "title": "James Snow Physiotherapy & Rehabilitation Centre in Milton",
    "rating": 4.7,
    "review_count": 256,          ← integer — the actual count (use this)
    "reviews": "https://...",     ← URL string — NOT the count (skip it)
    "type": "Physiotherapist in Milton, Ontario",
    "website": "https://www.jamessnowphysio.ca/",
    "phone": "+1 905-..."
  }
}
```

Extracted by `check_knowledge_graph(data, search_name)`.  
**Field priority (confirmed 2026-05-01):**  
1. `review_count` — integer, most reliable (name-specific queries)  
2. `user_reviews` — string like `"256"` or `"1,200+"` (some query types)  
3. `reviews_count` — integer (older SerpApi format)  
4. ~~`reviews`~~ — **URL string, not a count — intentionally excluded**

### Step 2 — Aggregate the 3 results

After all 3 category queries complete, `run_google_multi()` aggregates:
- `local_data` = first result where `local_pack.present == True`, else fallback to first result
- `kg_data` = first result where `knowledge_graph.found == True`, else fallback to first result

For a business like James Snow Physiotherapy, which is not the top result in the Maps pack for category queries, **both `local_data.reviews` and `kg_data.reviews_count` may be `None`** after this step.

### Step 3 — 4th name-specific query (`_google_name_lookup`)

If `has_review_data` is False (i.e. no review count from any of the 3 category queries), the audit runs a 4th query using the business's **actual name**:

```
James Snow Physiotherapy & Rehabilitation Centre Milton
```

This is a name query, so Google is much more likely to return a `knowledge_graph` sidebar with review data.

The function `_google_name_lookup()`:
1. Strips the city from the business name using `extract_search_name()` to avoid doubling: `"...Centre in Milton"` → `"...Centre"` + ` Milton`
2. Calls `_google_one()` with this query
3. If the KG is found → updates `kg_data`
4. If the local pack entry has a `reviews` field → updates `local_data`

### Step 4 — 5th call: review recency (`_check_review_recency`)

If the Knowledge Graph returned a `place_id`, the audit makes one additional call using SerpApi's `google_maps_reviews` engine, sorted by newest first. Only the most recent review's date is used.

```
GET https://serpapi.com/search
  ?engine=google_maps_reviews
  &place_id={place_id}
  &sort_by=newestFirst
  &gl=ca&hl=en
```

SerpApi returns reviews with a relative `date` field (e.g. `"3 months ago"`, `"a week ago"`). The helper `_parse_relative_date()` converts this to approximate days. Reviews older than **90 days** are considered stale.

If no `place_id` was returned (business has no Knowledge Panel), this call is skipped entirely — the business already has higher-priority GBP recommendations generated.

**Result fields:**
```python
{
  "checked": True,         # False if call was skipped or failed
  "recent": False,         # True = reviewed in last 90 days
  "days_since_last": 127,  # approximate days, may be None
  "last_review_date": "4 months ago"
}
```

**Cost:** 1 extra SerpApi search credit per audit, only when place_id is available.

---

### Step 5 — `calculate_score()` reads the aggregated data

```python
effective_rating = kg.get("rating") or lp.get("rating") or 0
effective_reviews = kg.get("reviews_count") or lp.get("reviews") or 0
```

If both are still 0 after all 4 queries, the review count is treated as 0 in scoring and as "unknown" in recommendations.

---

## Why review count is currently showing "unknown"

Three possible failure modes being debugged (debug logs added 2026-05-01):

### Failure mode 1 — Title mismatch in `check_knowledge_graph`

`check_knowledge_graph` only returns `found: True` if `search_name` appears **inside** `kg["title"]`. If the KG title in SerpApi differs slightly from the stored business name, it won't match.

**Example:**  
- Stored name: `"James Snow Physiotherapy & Rehabilitation Centre in Milton"`
- `search_name` after stripping city: `"James Snow Physiotherapy & Rehabilitation Centre"`
- SerpApi KG title: `"James Snow Physio"` (abbreviated)  
→ mismatch → `found: False` → review count lost

**Debug log to look for:**
```
[AEO][KG] Title mismatch: search_name='James Snow Physiotherapy & Rehabilitation Centre' not in kg_title='...'
```

### Failure mode 2 — Local pack title mismatch in `check_local_pack`

Same substring matching problem. SerpApi may list the business under a slightly different name.

**Debug log to look for:**
```
[AEO][LP] place[0] title='James Snow Physio' rating=4.7 reviews=256
[AEO][LP] No match found for 'James Snow Physiotherapy & Rehabilitation Centre'
```

### Failure mode 3 — SerpApi field name varies

SerpApi uses `user_reviews` on some queries and `reviews` on others (or omits both). The current code tries all three (`user_reviews`, `reviews`, `reviews_count`) but if SerpApi returns something else entirely, it will be missed.

**Debug log to look for:**
```
[AEO][KG] Raw knowledge_graph keys: ['title', 'rating', 'review_count', ...]
```

---

## Debug logs added (2026-05-01)

The following `logger.debug` and `logger.info` calls are now in `router.py`:

| Location | What it prints |
|---|---|
| `_google_one()` | Query string, `search_name`, all top-level SerpApi response keys |
| `check_local_pack()` | All place titles + rating + reviews in the local pack, and which one matched |
| `check_knowledge_graph()` | All KG keys, raw field values for `user_reviews`/`reviews`/`reviews_count`, parsed result |
| `run_google_multi()` | Summary per query: ai/local/organic/kg results with review counts |
| `_google_name_lookup()` | Whether KG was found and its review count; whether local_pack had reviews |

Logging is set to `DEBUG` level in `main.py`. All logs appear in the **uvicorn terminal** when you run an audit.

---

## How review data flows to the UI

```
[SerpApi] 
    ↓
check_local_pack() → local_pack.reviews (int or None)
check_knowledge_graph() → knowledge_graph.reviews_count (int or None)
    ↓
run_google_multi() → aggregated google result dict
    ↓
_run_audit_core() → passes to calculate_score() and generate_recommendations()
    ↓
POST /api/v1/aeo/audit response:
  {
    score: 43,
    breakdown: { reviews: 10, ... },
    recommendations: [
      { pillar: "reviews", title: "Get to 10+ Google reviews (current: 256)", ... }
    ]
  }
    ↓ also saved to Supabase:
aeo_audits.raw_results.recommendations  ← recommendations array
aeo_audits.score_breakdown              ← pillar scores
    ↓
apps/web/app/[locale]/dashboard/page.tsx  (server component)
  → reads latestAudit from aeo_audits
  → passes initialRecommendations={latestAudit.raw_results.recommendations}
    ↓
apps/web/components/dashboard/AeoAuditCard.tsx
  → renders pillar bars using score_breakdown
  → passes recommendations to <RecommendationsList />
    ↓
apps/web/components/dashboard/RecommendationsList.tsx
  → renders each recommendation.title (contains the review count string)
```

**Important:** The review count string in the recommendation title (e.g. `"current: 256"`) is generated at **audit time** in `generate_recommendations()` in `router.py`. The frontend never queries review count independently — it just renders whatever string the backend stored. If the backend stored "unknown", re-running the audit is the only fix.

---

## How to diagnose further

1. Restart the API server with `uvicorn main:app --reload --port 8000`
2. Click **Re-run audit** in the dashboard
3. Watch the uvicorn terminal — look for `[AEO][LP]` and `[AEO][KG]` lines
4. Compare the `title` values SerpApi returns against the business name in your settings
5. If titles don't match → the fix is fuzzy name matching (see next steps below)

---

## Fixes applied (2026-05-01)

### 1. Fuzzy name matching (`_name_matches`)
Replaced exact substring matching in `check_local_pack`, `check_knowledge_graph`, and `check_organic` with token-based matching. Requires ≥2 significant tokens (length > 3) from `search_name` to appear in the candidate title.

Handles: `"James Snow Physio"` ↔ `"James Snow Physiotherapy & Rehabilitation Centre"`

### 2. Correct SerpApi field name for review count
SerpApi returns `review_count` (integer) and `reviews` (URL string). The old code read `reviews` first — a URL — which failed to parse as an integer, giving `None` → "unknown".

Fixed field priority: `review_count` → `user_reviews` → `reviews_count`. The `reviews` URL field is intentionally excluded.

### 3. `place_id` now captured from Knowledge Graph
`check_knowledge_graph` now returns `place_id` from the SerpApi KG response. Used to drive the recency check.

### 4. Scoring fix — GBP category points
`calculate_score` previously gave 5pts for having *any* GBP presence. Now only awards those 5pts when the KG has a `type` field — meaning Google has categorized the business in its Knowledge Panel.

### 5. New recommendation — Earn a Knowledge Panel
When a business appears in the local pack but has no Knowledge Panel (`lp.present=True, kg.found=False`), a new recommendation is surfaced:
> **"Enrich your GBP to earn a Google Knowledge Panel"** (impact: 8)

### 6. New recommendation — Review recency
When the recency check runs and confirms no reviews in 90+ days:
> **"You haven't received new reviews in 3+ months (last: X days ago)"** (impact: 7)

Not shown when: place_id is missing, the recency API call failed, or the business has recent reviews.
