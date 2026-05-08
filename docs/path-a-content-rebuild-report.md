# Path A — Content Rebuild Report

**Date:** 2026-05-07
**Status:** All steps shipped pending your testing tomorrow.

## ⚠️ SQL you need to run in Supabase tomorrow morning

Only **one** migration is pending — everything else (013, 014, 015) you've already confirmed is applied.

**Migration 016** — paste into Supabase SQL Editor and run:

```sql
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS descriptions   JSONB;
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS faq_schema     TEXT;
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS language       TEXT DEFAULT 'en';
ALTER TABLE aeo_content ADD COLUMN IF NOT EXISTS paa_questions  JSONB;
```

**Verify after running:**
```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'aeo_content'
  AND column_name IN ('descriptions', 'faq_schema', 'language', 'paa_questions')
ORDER BY column_name;
```
You should see 4 rows.

**No other SQL is needed for the F11/F12 polish.** Citation gaps + the new comparison table both live inside the existing `aeo_audits.raw_results` JSONB column — no schema change needed.

After applying, **restart the FastAPI server** (Ctrl+C, then `uvicorn main:app --reload --host 0.0.0.0 --port 8000`) so the new endpoint code loads. Hard-refresh the browser too.

---

## What was finished tonight

| Step | Item | File(s) | Status |
|---|---|---|---|
| 4 | "Complete your profile" CTA | `apps/web/components/dashboard/ContentPage.tsx` | Already shipped earlier — verified working in your last screenshot |
| 5 | FAQ → `FAQPage` JSON-LD, 10 Q&As | `api/aeo/schema_builder.py`, `api/aeo/router.py`, `ContentPage.tsx` | Done |
| 6 | Pass `services` into description prompts | `api/aeo/router.py` (`_build_content_prompts`) | Done |
| 7 | People-Also-Ask grounding via SerpApi | `api/aeo/router.py` (`_fetch_people_also_ask`) | Done |
| 8 | Per-platform descriptions (website / GBP / Yelp / social) | `api/aeo/router.py`, `ContentPage.tsx` | Done |
| 9 | French variants | `api/aeo/router.py` (FR prompt set), `ContentPage.tsx` (EN/FR toggle) | Done |
| 10 | Server-side validation pass | `api/aeo/router.py` (`_validate_content`, `_truncate_at_word`) | Done (warnings, not blocking) |

---

## Files changed

### New
- [supabase/migrations/016_aeo_content_multi_platform.sql](supabase/migrations/016_aeo_content_multi_platform.sql) — adds `descriptions JSONB`, `faq_schema TEXT`, `language TEXT`, `paa_questions JSONB` to `aeo_content`.

### Modified
- [api/aeo/schema_builder.py](api/aeo/schema_builder.py) — added `build_faq_schema(faq_items)` that wraps a Q&A list in a Schema.org `FAQPage` object.
- [api/aeo/router.py](api/aeo/router.py):
  - New `GenerateContentRequest` model with optional `language: str = "en"`.
  - New helpers: `_fetch_people_also_ask`, `_build_content_prompts`, `_truncate_at_word`, `_validate_content`.
  - `generate_content` rewritten end-to-end:
    - 5 LLM calls in parallel (website desc, GBP desc, Yelp desc, social bio, FAQ).
    - `services` is now explicitly listed in each description prompt.
    - PAA seeds passed to the FAQ prompt as "real customer questions" inspiration.
    - 10 FAQ Q&As (was 5), 40–80 word target per answer.
    - Per-platform character caps: GBP ≤700, social bio ≤150, applied via `_truncate_at_word`.
    - Deterministic FAQ schema built from the resulting Q&A list.
    - Validation produces warnings (not errors) so users always get something to copy.
    - All seven new fields persisted to `aeo_content`.
- [apps/web/components/dashboard/ContentPage.tsx](apps/web/components/dashboard/ContentPage.tsx) — full rewrite:
  - EN/FR toggle in the header (defaults to user locale).
  - Three description tabs (Website / Google / Yelp) with platform-specific hints and character counter for GBP.
  - Social bio block with live `n/150 characters` counter.
  - FAQ list now shows "grounded in N real Google searches" subtitle when PAA seeds were used.
  - New `FAQ Schema (JSON-LD)` block with `<script>`-wrapped copy and Rich Results Test deep link.
  - LocalBusiness schema block unchanged in structure but kept the same UX.
  - "Language drift" banner: if you load EN content but flipped the toggle to FR, you see a hint to click Regenerate.
  - Validation warnings shown at bottom when present.
  - Backward-compat shim (`normaliseContent`) so old DB rows still render before regeneration.

---

## What it costs you per generation

| Call | Approximate cost |
|---|---|
| 4× LLM descriptions (website + GBP + Yelp + social bio) | ~$0.004 |
| 1× LLM FAQ (~2500 tokens out) | ~$0.005 |
| 1× SerpApi PAA fetch | ~$0.005 |
| **Total** | **~$0.014** per Regenerate click |

About 2× the cost of the previous version, but you get 10× more content and grounded FAQs.

---

## Pre-test setup (do this first thing)

1. **Apply migration 016** in Supabase SQL Editor. Paste the contents of [supabase/migrations/016_aeo_content_multi_platform.sql](supabase/migrations/016_aeo_content_multi_platform.sql) and run.
2. **Verify columns**:
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'aeo_content'
     AND column_name IN ('descriptions', 'faq_schema', 'language', 'paa_questions')
   ORDER BY column_name;
   ```
   You should see 4 rows.
3. **Restart the FastAPI server** so it picks up the new endpoint. If you launched it without `--reload`, kill the process and relaunch:
   ```bash
   cd api
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Hard-refresh** the dashboard (Ctrl+Shift+R) so the browser drops cached JS.

---

## Test cases for tomorrow

### A. Smoke test — "does it run at all?"
1. Open `/dashboard/content`. The page should render. If you have a previous content row, you'll see it shown (legacy shape — single description).
2. Click **Regenerate**. Wait ~20s. The page should populate with the new shape (3 description tabs, 10 FAQs, FAQ schema block, LocalBusiness schema block).
3. Open the API terminal — you should see no tracebacks.
4. Open Supabase → Table Editor → `aeo_content`. The newest row should have non-null values in `descriptions`, `faq_schema`, `language`, `paa_questions`.
   - **Expected:** all four columns populated.
   - **If `descriptions` is null** → migration 016 wasn't applied or the API didn't reload.

### B. Per-platform descriptions (Step 8)
1. Click each tab: **Website**, **Google**, **Yelp**.
2. **Website** should be ~300–400 words, third person, mentions services.
3. **Google** should be visibly shorter; you should see a `n/700 characters` counter under it. Confirm the counter reads ≤700.
4. **Yelp** should be ~200–250 words, more concise than Website.
5. Click **Copy** on each tab and paste into a text editor — confirm you get the right variant.

### C. Services in description prompt (Step 6)
1. In Settings, ensure your `services` field has at least 3 comma-separated service names (e.g., "physiotherapy, massage therapy, sports rehab").
2. Regenerate.
3. Read the **Website** description — every listed service should appear.
   - **If a service is missing** → flag the business type/services back to me; the prompt may need tightening for that vertical.

### D. FAQ → 10 Q&As + FAQPage JSON-LD (Step 5)
1. Count the FAQ items rendered — should be **exactly 10** (or 9–10 if the LLM dropped one).
2. Click **Copy** on the **FAQ Schema (JSON-LD)** block.
3. Open [Google's Rich Results Test](https://search.google.com/test/rich-results) → **Code** tab → paste.
4. **Expected:** "Valid items detected" with `FAQPage` listed.
5. If you re-test the **LocalBusiness schema** block (the one we already validated yesterday), it should still pass.

### E. People-Also-Ask grounding (Step 7)
1. Below the FAQ section, look for the small subtitle: "grounded in N real Google searches".
2. **Expected:** N ≥ 3 (SerpApi normally returns 3–6 PAA questions for a populated topic).
3. Compare a few of your generated FAQ questions against the questions a real Google search shows for `"<your business type> in <your city>"` — you should see clear similarity in 2–3 of them.
4. **If N = 0** the subtitle won't appear — that's still OK, FAQ generation falls back to LLM-only seeds. Just confirms PAA fetch happened (best-effort).

### F. French variants (Step 9)
1. Click the **FR** chip in the header.
2. Click **Regenerate**.
3. **Expected:** all four descriptions, all 10 FAQ questions/answers, and the social bio render in French. The schema markup `description` field should also be in French.
4. Switch back to **EN**, click Regenerate, confirm content swaps back to English.
5. Mid-session test: load the page (which shows last-saved content), flip toggle to the OTHER language without regenerating. **Expected:** the amber "You're viewing content in X" banner appears, prompting you to regenerate.

### G. Server-side caps + validation (Step 10)
1. After Regenerate, scroll to the bottom of the content list. If any LLM call missed targets, you'll see a small amber `Note:` row listing warnings (e.g., `gbp description too long`, `faq too few items`).
2. Most generations should produce **zero warnings**.
3. Edge case: kill your `OPENAI_API_KEY` in `.env`, restart the API, click Regenerate. **Expected:** the request fails cleanly (you'll see "Generation failed. Please try again." in the UI) — not a hung browser tab. Restore the key after.

### H. "Complete your profile" CTA (Step 4 — verify it still works)
1. In Settings, blank out `image_url` (Logo or photo URL field). Save.
2. Regenerate.
3. **Expected:** an amber CTA appears in the LocalBusiness schema block listing "Logo or photo URL" as missing, with an "Update profile →" link that lands on `/en/dashboard/settings` (or `/fr/...` if you're in FR).
4. Re-fill the image URL, save, regenerate → CTA disappears.

### I. Schema regression — verify yesterday's win still holds
1. Click **Copy** on the **Schema Markup (JSON-LD)** block.
2. [Rich Results Test](https://search.google.com/test/rich-results) → Code tab → paste.
3. **Expected:** still "valid items detected" with `MedicalClinic` (or another industry-specific subtype matching your business).
4. The `addressCountry` field should be `"Canada"` (not `"CA"`), and there should be no hallucinated fields like `servesCuisine` or invented `service` arrays.

---

## Known limitations / caveats

- **PAA fetch is best-effort.** If SerpApi is slow or returns nothing, the FAQ falls back to LLM-only generation. We don't retry. The `paa_questions` array in the DB will be empty in that case.
- **Validation produces warnings, not errors.** A bad LLM response still ships to the user — they get something to copy, plus a hint to regenerate. We can tighten this to "retry once" later if it becomes a real problem in customer testing.
- **The legacy `description` column is still written** (with the website variant) for backward compat with anything else in the codebase that might read it. We can drop that in a later migration once we're confident nothing depends on it.
- **The FR toggle defaults to your UI locale.** A QC user landing on `/fr/dashboard/content` will start with FR selected. They can flip to EN if they want both — but they'll need to click Regenerate after each language change (we don't run both in parallel — that would double cost per click).
- **No "test the schema by URL" flow yet.** If a customer pastes their schema into their site and we want to verify it lives there, that's a separate feature (probably a "Verify my schema" button that fetches their site and runs `extruct`). Out of scope for this rebuild.

---

## What's NOT in this rebuild (deferred)

These were on the wider Path A wishlist but kept out to ship within tonight's window:

- A "Verify on my live site" button that fetches the user's homepage and confirms the schema is actually there.
- Press-release / "About page long-form" / Google Posts content generators (mentioned in `honest-evaluation-content-feature.md` Part 1.5 as missing). Phase 1+ items.
- Per-FAQ regenerate ("don't like this question, give me another"). Phase 2 polish.
- Schema validation via `extruct` on the server (currently we trust the deterministic builder; it's by-construction valid).
- Retry-once on validation failure (current code returns warnings only).

---

## After you test

If everything passes the test plan above, **Path A is launch-ready**. The remaining pre-launch items are infrastructure/marketing, not Content tab quality:

- F9 sprint items: Railway Dockerfile, Resend domain, vercel.json cron, rate limiting, privacy/terms, Sentry.
- F10 marketing/trust: free public AEO grader at `leapone.ca/grade`, 3 case studies, sample audit PDF.

If a test case fails, paste the failure (screenshot or console output) and I'll triage.

---

## Competitor features — status after tonight's work

| Feature | Status | Where |
|---|---|---|
| **F11 — Competitor benchmarking** | Built (already shipping) + **polish added tonight** | Existing: `extract_competitors`, `score_competitor`, `match_competitor_ai_citations`. New: side-by-side `ComparisonTable` on the Competitors page. |
| **F11 polish — Citation gap analysis** | **New tonight** | Backend: `_detect_directory_presence` scans organic results from each Google query for known directory domains (Yelp, BBB, Yellow Pages, TripAdvisor, etc., 22 directories total). Frontend: `CitationGapSection` component — shows directories you're on, plus an actionable amber list of directories competitors appear on but you don't, each with a "Claim listing →" link to the right vendor signup page. |
| **F12 — Competitor weak-point mining** | Built (already shipping) | `_analyze_competitor_weaknesses` in `router.py:1283` + `CompetitorInsightsSection` UI. No changes needed. |
| **F13 — AI-crawler analytics** | **Not built** | Requires a different data source (server logs / JS tracking pixel / Cloudflare API). Real future work. |

### Backend changes for citation gap analysis

- [api/aeo/router.py](api/aeo/router.py):
  - New `DIRECTORY_DOMAINS` constant (22 known directories — Canadian + US + niche health/professional).
  - New `_domain_from_url`, `_name_short`, `_detect_directory_presence` helpers.
  - `_google_one` now returns trimmed `organic_results_raw` (top 10 per query) so the analyzer has data to scan. Negligible JSONB bloat.
  - `_run_audit_core` invokes the analyzer after competitor scoring (~$0 — pure text scan over data we already paid SerpApi for) and attaches `citation_gaps` to the result.
  - Both audit-write paths (`run_audit` + `cron-monthly`) persist `citation_gaps` and `competitor_insights` into `aeo_audits.raw_results`.

### Frontend changes

- [apps/web/components/dashboard/CompetitorsPage.tsx](apps/web/components/dashboard/CompetitorsPage.tsx):
  - New `ComparisonTable` component above the existing per-competitor cards. Renders YOU + top 3 competitors as columns, with rows for Total + 5 pillars. Color-coded per cell (green ≥75%, amber ≥40%, red below). Horizontally scrolls on small screens.
  - New `CitationGapSection` component below the existing weak-point insights. Two parts: a green "✓ You appear on" pill list, then an amber gap list with per-directory "Claim listing →" deep links. Empty/zero-data states handled gracefully.
  - New `DIRECTORY_CLAIM_URLS` map (21 directories) so each gap's claim link goes to the right vendor signup page.

---

## Test cases for F11/F12 polish

### J. Side-by-side comparison table (F11 polish)
1. Open `/dashboard/competitors`.
2. **Expected:** Above the per-competitor cards, you see a new "You vs. top N" table with YOU as the first column and competitors as the next 1–3 columns. Each row is a pillar (GBP / Reviews / Website / Local / AI). Total row at top.
3. Cell colors should reflect %-of-max — green at 75%+, amber at 40–74%, red below 40%.
4. Long competitor names should truncate with an ellipsis but show the full name on hover (title attr).

### K. Citation gap analysis (F11 polish)
1. Click "Re-run audit" on the dashboard so a fresh audit captures `organic_results_raw`.
2. Wait for it to finish (~15s).
3. Open `/dashboard/competitors`.
4. Scroll past the Weak-Points insights → you should see a new "🔗 Directory Presence" section.
5. **Expected (best case):**
   - "You appear on" — green pill list (e.g. ✓ Yelp, ✓ Yellow Pages).
   - "Gaps — competitors are listed here, you are not" — amber list with "Claim listing →" links.
6. **Expected (no gaps case):** "No directory gaps detected — you appear wherever your competitors do."
7. **Expected (no signal case):** Friendly fallback "We didn't detect any directory listings…" — this can happen if SerpApi's organic_results don't surface directory domains for that vertical.
8. Click a "Claim listing →" link — should open the right vendor signup (e.g. Yelp gap → biz.yelp.com/signup).

### L. Persistence check
1. After step K, open Supabase Table Editor → `aeo_audits` → newest row → `raw_results` JSONB.
2. **Expected:** A `citation_gaps` key with shape `{user: [...], competitors: {...}, gaps: [...]}`.
3. The `competitor_insights` key from F12 should also be there (regression check — make sure my changes didn't break it).

### M. Old audits without citation_gaps still render
1. If you have an audit row from before tonight, the new section should not crash — it'll either render an empty-state or be skipped. Verify by switching to the most recent pre-today audit (if you have one) and confirming the page still loads.

---

## Honest caveats on the citation-gap heuristic

- **The match is fuzzy.** A business is detected on a directory if its first three name words appear in the organic-result title or snippet of a result on that directory's domain. This works well for businesses with distinctive names ("James Snow Physiotherapy") and worse for very generic ones ("Smith Dental").
- **It depends on what Google ranked.** SerpApi returns the top ~10 organic results — if a directory is on page 2, we won't see it. So "no gaps detected" can mean either you're really on everything, or Google just didn't surface those pages for that query.
- **22 directories covered.** Mostly Canadian + US + a handful of niche health/professional sites. If you find a directory that matters in a vertical we don't cover, send me the domain → I'll add it.
- **No Cron-monthly UI for citation gaps.** Each fresh audit refreshes the data — historical audits keep whatever data they were written with. That's fine but worth knowing.

---

## What's still genuinely deferred

| Feature | Why |
|---|---|
| F13 — AI-crawler analytics | Needs server logs or a tracking pixel — no shortcut. Multi-week feature. |
| "Verify on my live site" | Fetch the user's homepage and confirm schema is actually deployed. Phase 1+ polish. |
| Per-FAQ regenerate, more content surfaces (Google Posts, press release) | Phase 2 polish. |
| Side-by-side audit history (your score over time vs competitors) | Smart trend feature. Easy data, needs a chart. |

Sleep well — should be a clean morning of testing.
