# ChatGPT Audit — Technical Documentation

## Overview

The ChatGPT audit adds OpenAI's GPT-4o-mini as a third AI citation source alongside Perplexity and Google AI Overview. It uses a dedicated OpenAI client (always OpenAI, regardless of the `AI_PROVIDER` env setting) to query local search prompts and detect business name mentions.

---

## Files Changed

| File | Change |
|---|---|
| `api/aeo/router.py` | New functions, updated scoring, recommendations, audit core, DB inserts |
| `supabase/migrations/014_chatgpt_audit_columns.sql` | Two new columns on `aeo_audits` |
| `apps/web/components/dashboard/AeoAuditCard.tsx` | ChatGPT signal in drawer + training data note |

---

## Backend — `api/aeo/router.py`

### New: Dedicated OpenAI client

```python
from openai import AsyncOpenAI
_audit_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

This client is always OpenAI regardless of `AI_PROVIDER`. The `ai_engine` singleton must not be used here because it routes to whatever provider is configured (Claude, Gemini, etc.), which would produce incorrect "ChatGPT" results.

---

### New: `_chatgpt_one(business_name, query, city) -> dict`

Calls OpenAI with a single local search query.

```python
async def _chatgpt_one(business_name: str, query: str, city: str) -> dict:
    response = await _audit_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a local business search assistant. ..."},
            {"role": "user", "content": query},
        ],
        max_tokens=500,
        temperature=0.0,
    )
    answer = response.choices[0].message.content.strip()
    mentioned = extract_search_name(business_name, city).lower() in answer.lower()
    snippet = answer[:500] if mentioned else None
    return {"mentioned": mentioned, "snippet": snippet, "answer": answer[:2000], "query": query}
```

Key design decisions:
- **`temperature=0.0`** — Deterministic output. Reduces false positive/negative variance across re-runs.
- **`gpt-4o-mini`** — Cheapest capable model. At ~$0.15/1M input tokens, cost per audit is negligible.
- **System prompt asks for specific business names** — Without this, the model gives generic advice rather than naming real businesses, producing false negatives.
- **`extract_search_name`** — Strips city suffixes before matching (e.g. "Joe's Pizza in Ottawa" → "Joe's Pizza").
- **Return shape matches `_perplexity_one`** — Same `{mentioned, snippet, answer, query}` keys for consistency.

---

### New: `run_chatgpt_multi(business_name, business_type_en, city, province) -> dict`

Runs `_chatgpt_one` for each query from `build_queries()` (3 queries). Returns aggregated result:

```python
{
  "mentioned": bool,       # True if mentioned in ANY query
  "snippet":   str|None,   # First snippet where mentioned
  "queries":   list[str],  # The 3 query strings
  "per_query": list[dict], # Individual results per query
}
```

Mirrors `run_perplexity_multi` exactly. Failures per-query are caught and recorded as `{"mentioned": False, "snippet": None, "answer": "", "query": query}` so one failing query doesn't abort the whole audit.

---

### Updated: `calculate_score` — `ai_citation` redistribution

Old scoring:
- Perplexity mentioned → +10 pts
- Google AI mentioned  → +8 pts
- **Total max: 18 pts**

New scoring:
- ChatGPT mentioned    → +6 pts
- Perplexity mentioned → +6 pts
- Google AI mentioned  → +6 pts
- **Total max: 18 pts (unchanged)**

Overall score maximum remains 100. The `chatgpt` dict is now a required parameter.

---

### Updated: `score_competitor`

Added `chatgpt_mentioned: bool | None = None` parameter. Same 6/6/6 redistribution. `has_full_data` now requires all four data points (website + 3 AI sources).

---

### Updated: `match_competitor_ai_citations`

Added `chatgpt_result` parameter. Scans per-query ChatGPT answers for competitor name matches using the existing `_name_matches()` function. Returns `chatgpt_mentioned` alongside `perplexity_mentioned` and `google_ai_mentioned` for each competitor.

Cost: $0 — pure text scanning over already-fetched data.

---

### Updated: `generate_recommendations`

Added `chatgpt: dict | None = None` parameter. If `chatgpt["mentioned"]` is False, appends a recommendation to `ai_citation` pillar:

- **Impact**: 6 pts
- **Difficulty**: hard
- **Key copy**: explains that ChatGPT uses training data (not live search) and that improvements appear in future model updates (6–12 months)
- **Actions**: Yelp/TripAdvisor/Yellow Pages profiles, Chamber of Commerce/BBB, local press mention, FAQ page

The Perplexity and Google AI recommendation impact values were also updated from 10/8 to 6/6 to match the new scoring.

---

### Updated: `_run_audit_core`

ChatGPT, Perplexity, and Google now run **in parallel** via `asyncio.gather`:

```python
perplexity_result, google_result, chatgpt_result = await asyncio.gather(
    run_perplexity_multi(...),
    run_google_multi(...),
    run_chatgpt_multi(...),
)
```

This means adding ChatGPT adds **zero wall-clock time** to the audit — it runs concurrently with the existing calls.

`chatgpt_result` flows through to:
- `calculate_score(..., chatgpt=chatgpt_result)`
- `generate_recommendations(..., chatgpt=chatgpt_result)`
- `match_competitor_ai_citations(..., chatgpt_result=chatgpt_result)`
- `score_competitor(..., chatgpt_mentioned=...)`
- Return dict under key `"chatgpt"`

---

### Updated: DB inserts (both `run_audit` and `cron-monthly`)

Two new columns written per audit:

```python
"chatgpt_mentioned": result["chatgpt"]["mentioned"],
"chatgpt_snippet":   result["chatgpt"]["snippet"],
```

And `raw_results` JSONB now includes `"chatgpt": result["chatgpt"]`.

---

## Database — Migration 014

```sql
ALTER TABLE aeo_audits ADD COLUMN IF NOT EXISTS chatgpt_mentioned boolean;
ALTER TABLE aeo_audits ADD COLUMN IF NOT EXISTS chatgpt_snippet   text;
```

Apply in Supabase SQL Editor before deploying the updated backend. Both columns are nullable — existing audit rows will have `NULL` for these fields, which the frontend handles gracefully (`chatgpt !== undefined` checks).

---

## Frontend — `AeoAuditCard.tsx`

### `RawResults` interface
Added `chatgpt?: { mentioned: boolean; snippet?: string | null }`.

### "Why This Score?" drawer — AI Citations section
ChatGPT is now the first signal listed (before Perplexity and Google AI):

1. **ChatGPT mentioned** — green/red signal dot
2. **Snippet** — shown if mentioned (first 200 chars)
3. **Training data note** — shown only when ChatGPT result is present but `mentioned=false`:
   > *"ChatGPT answers from training data — improvements appear in future model updates (6–12 months)."*
4. Perplexity signal (unchanged)
5. Google AI Overview signal (unchanged)

The training data note only renders when `chatgpt !== undefined` (i.e., the audit was run after this feature shipped). Old audits without a ChatGPT result show nothing for that row.

---

## Cost Per Audit

| API call | Approx. cost |
|---|---|
| 3× ChatGPT (gpt-4o-mini, ~500 tokens each) | ~$0.001 |
| 3× Perplexity (sonar) | ~$0.006 |
| 4× SerpApi | ~$0.020 |
| Website check | $0 |
| **Total per audit** | **~$0.027** |

Adding ChatGPT adds less than $0.001 per audit.

---

## Important: `AI_PROVIDER` Independence

The audit uses `_audit_openai` (a hardcoded `AsyncOpenAI` client), **not** `ai_engine`. This is intentional:

- `AI_PROVIDER` controls which LLM is used for content generation (GBP descriptions, FAQ, review responses)
- ChatGPT citations must always query OpenAI specifically — the point is to know if *ChatGPT* knows the business
- If the codebase switches `AI_PROVIDER=gemini` or `AI_PROVIDER=claude`, the ChatGPT audit still correctly queries OpenAI

`OPENAI_API_KEY` must be set even if `AI_PROVIDER` is not `openai`.

---

## Null Safety for Old Audits

Old audit rows (before this feature) have `chatgpt_mentioned=NULL` and no `chatgpt` key in `raw_results`. The frontend handles this:
- `rawResults?.chatgpt` is `undefined` for old audits
- The `chatgpt !== undefined` guard means the training data note doesn't render for old audits
- The Signal component receives `undefined` and renders a neutral state
