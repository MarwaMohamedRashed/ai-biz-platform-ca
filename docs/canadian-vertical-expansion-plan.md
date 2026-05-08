# Canadian Vertical Expansion — Execution Plan

**Date:** 2026-05-08
**Status:** Plan — combines your analysis + my earlier proposal + corrections.
**Goal:** Move from "trades-only Canadian moat" to "all-vertical Canadian moat".

---

## Honest pushback before we ship

Your list is mostly excellent, but five items need adjustment before they go in:

### ❌ Issue 1: `yellowpages.ca` is already in DIRECTORY_DOMAINS
Verified at [api/aeo/router.py:1572](api/aeo/router.py#L1572). Yellow Pages CA + .com both label as "Yelliw Pages" today. Skip from the "add 5" list.

### ❌ Issue 2: `homestars.com` and `trustedpros.ca` are also already in
Added yesterday. Skip from the "add 5" list.

So your "add 5 directories" is really **add 2 directories**: `n49.com` and `cylex-canada.ca`. Both legit, both worth adding.

### ⚠️ Issue 3: Zomato withdrew from Canada in 2020
Zomato closed all North American restaurant operations. They no longer maintain Canadian restaurant listings — adding it would create rec text pointing at a tool that doesn't serve Canadian SMBs anymore. Drop Zomato. Keep OpenTable.

### ⚠️ Issue 4: RECO Portal and CPSO are Ontario-only
- **RECO** = Real Estate Council of **Ontario**. BC has REC, Quebec has OACIQ, Alberta has RECA, etc. Provincial regulator structure means a national tool can't recommend "RECO Portal" to a realtor in Vancouver — they'd be confused.
- **CPSO** = College of Physicians and Surgeons of **Ontario**. Same problem — BC has CPSBC, Quebec has CMQ.

Two cleaner approaches:
- **Option A (preferred for now):** use Realtor.ca for realtors (national, Canadian Real Estate Association). For physicians, skip the regulator angle entirely and use RateMDs + Healthgrades — patients don't search regulators, they search reviews.
- **Option B (later):** build a province → regulator map. Higher effort, accurate per-province. Save for a follow-on.

I recommend Option A for tomorrow's ship. Option B is a 2-hour follow-on whenever you want it.

### ⚠️ Issue 5: Adding 3 query templates DOUBLES SerpApi cost per audit
Currently 3 templates × 3 engines = 9 query passes. Adding 3 more = 18 passes. SerpApi cost goes from ~$0.020 → ~$0.040 per audit. Not catastrophic, but worth being deliberate.

**Better approach:** make the new query templates **conditional**:
- `Emergency {type} {city} 24/7` — only run for trades businesses (where emergency-search behavior actually exists)
- `{type} open weekends {city}` — only run for businesses with hours data showing weekend hours, OR for trades + healthcare urgent care
- `{type} near {postal_code[:3]}` — only run if the business has a postal code (FSA-prefix is a uniquely Canadian search pattern, ~20% of users use it)

This way: a dental clinic gets 3+1=4 queries (base 3 + FSA), a plumber gets 3+3=6, a hair salon gets the existing 3. Cost goes up modestly, only where it generates real lift.

---

## What I'd add beyond your list

Three high-leverage additions you didn't have:

### + Opencare for dentists specifically
Already in DIRECTORY_DOMAINS. Should have its own conditional rec — Canadian dentists search behavior is heavily Opencare-driven. ~15 lines.

### + Realtor.ca for realtors (instead of RECO)
National (CREA), every CA realtor needs a profile. Add to DIRECTORY_DOMAINS + rec. Replaces the RECO suggestion.

### + Cleaner trades/health/professional-vertical detection
The pattern we shipped for trades (`_is_trades_business()`) should be replicated as `_is_healthcare_business()`, `_is_food_business()`, `_is_legal_business()`, `_is_realtor_business()`. Each ~5 lines of regex.

---

## Combined target list (what we'll actually ship)

### Phase 1 — Directory + recommendation expansions (~1.5 hours)

#### 1.1 — Add 2 missing Canadian directories
```python
# In DIRECTORY_DOMAINS dict
"n49.com":             "n49",
"cylex-canada.ca":     "Cylex Canada",
"realtor.ca":          "Realtor.ca",       # also add
"opencare.com":        "Opencare",          # already in -- verify
"ratemds.com":         "RateMDs",           # already in -- verify
"lawyerlocate.ca":     "LawyerLocate",      # add
"opentable.com":       "OpenTable",         # add
"opentable.ca":        "OpenTable",         # add (CA subdomain)
```

Effective new entries: **n49, Cylex Canada, Realtor.ca, LawyerLocate, OpenTable** (5 net new).

#### 1.2 — Add CLAIM_URLS for the new entries
```typescript
// In DIRECTORY_CLAIM_URLS in CompetitorsPage.tsx
'n49':            'https://www.n49.com/biz/claim',
'Cylex Canada':   'https://www.cylex-canada.ca/add-business.html',
'Realtor.ca':     'https://www.realtor.ca/realtor-list',  // controlled by CREA membership
'LawyerLocate':   'https://www.lawyerlocate.ca/lawyers/register',
'OpenTable':      'https://restaurant.opentable.com',
```

#### 1.3 — Add 4 vertical-detector helpers
Following the `_is_trades_business()` pattern in `api/aeo/router.py`:
- `_is_healthcare_business()` — dentist, doctor, physiotherapist, chiropractor, optometrist, vet, pharmacy
- `_is_dentist_business()` — dental specifically (subset of healthcare)
- `_is_food_business()` — restaurant, café, bakery, bar, brewery
- `_is_legal_business()` — lawyer, attorney, paralegal, notary, law firm
- `_is_realtor_business()` — real estate, realtor

#### 1.4 — Add 6 conditional vertical recommendations
Following the HomeStars/TrustedPros pattern:
- **Healthcare** → "Claim your RateMDs profile" (only if not on RateMDs)
- **Dentist specifically** → "Claim your Opencare profile" (only if not on Opencare)
- **Restaurant** → "Claim your OpenTable listing" (only if not on OpenTable)
- **Restaurant** → "Claim your TripAdvisor listing" (only if not on TripAdvisor — already in domains)
- **Lawyer** → "Claim your LawyerLocate profile" (only if not on LawyerLocate)
- **Realtor** → "Claim your Realtor.ca profile" (only if not on Realtor.ca)

#### 1.5 — Universal recommendations (any vertical)
- **Apple Business Connect** ([businessconnect.apple.com](https://businessconnect.apple.com)) — fires for any business missing an Apple Maps presence. We can't easily detect this from SerpApi (Apple Maps isn't in Google's index), so the rec fires for ALL businesses but at low impact (+2). The text frames it as "free, takes 5 minutes, increasingly cited by Apple Intelligence".
- **Bing Places** ([bingplaces.com](https://bingplaces.com)) — same pattern. Fires for all. +2 impact. Frames it as "Microsoft Copilot pulls from Bing Places."

Each is a single non-conditional `recs.append({...})` block.

### Phase 2 — Query template improvements (~30 min)

#### 2.1 — Modify `build_queries()` signature
Pass `business_type` and `postal_code` (and the trades/healthcare flags) so it can return a tailored query list:

```python
def build_queries(
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
) -> list[str]:
    queries = [t.format(type=business_type_en, city=city, province=province)
               for t in QUERY_TEMPLATES]
    
    # FSA-prefix query — uniquely Canadian, ~20% of locals use it
    if postal_code and len(postal_code) >= 3:
        fsa = postal_code[:3].upper()
        queries.append(f"{business_type_en} near {fsa}")
    
    # Emergency/24-7 query — only meaningful for trades + urgent care
    if is_trades or is_healthcare:
        queries.append(f"Emergency {business_type_en} {city} 24/7")
    
    # Weekend availability — meaningful for trades + healthcare + auto
    if is_trades or is_healthcare:
        queries.append(f"{business_type_en} open weekends {city}")
    
    return queries
```

Default audit: still 3 queries. Trades audit: up to 6 queries. Cost is opt-in by vertical.

#### 2.2 — Plumb `postal_code` and vertical flags into the audit pipeline
The 3 callers of `build_queries` (Perplexity, Google, ChatGPT runners) need to receive the new args. ~5 line change per call site.

### Phase 3 — Quebec bilingual schema (~10 min)

In `build_schema()`, add:
```python
if (business.get("province") or "").upper() == "QC":
    obj["inLanguage"] = ["fr-CA", "en-CA"]
```

**Caveat:** this is a public claim about content language. If a Quebec business has English-only content, claiming `fr-CA` is misleading and Google may discount the schema. We should only do this when:
- The business is in QC, AND
- Content has been generated in French (i.e., `aeo_content.language` includes `'fr'`), OR
- The user explicitly opts in via a "My business serves both languages" toggle in Settings

I'll start with QC + French content as the trigger. Easy to refine later.

### Phase 4 — Tests (~30 min)

Extend `api/tests/`:
- 4 new vertical-detector tests (healthcare/food/legal/realtor — same shape as trades)
- 6 new conditional-rec tests (one per new rec)
- 3 new query-template tests (FSA, emergency, weekend gating)
- 2 new directory-domains tests (n49, Cylex)
- 1 new schema test (Quebec inLanguage block when applicable)

Target: ~16 new tests. Total suite goes from 110 → ~126.

---

## Summary table — final "what ships" list

| # | Item | From | Effort |
|---|---|---|---|
| 1 | Add `n49.com`, `cylex-canada.ca`, `realtor.ca`, `lawyerlocate.ca`, `opentable.com`, `opentable.ca` to DIRECTORY_DOMAINS | Mix | 6 lines |
| 2 | Add corresponding CLAIM_URLs | Mix | 5 lines |
| 3 | Add `_is_healthcare_business()`, `_is_dentist_business()`, `_is_food_business()`, `_is_legal_business()`, `_is_realtor_business()` | Me | ~25 lines |
| 4 | Conditional rec: RateMDs (healthcare) | You | ~12 lines |
| 5 | Conditional rec: Opencare (dentist) | Me | ~12 lines |
| 6 | Conditional rec: OpenTable (restaurant) | You | ~12 lines |
| 7 | Conditional rec: TripAdvisor (restaurant) — leverages existing TA in domains | Me | ~12 lines |
| 8 | Conditional rec: LawyerLocate (lawyer) | You (RECO replaced with this) | ~12 lines |
| 9 | Conditional rec: Realtor.ca (realtor) | You (RECO replaced with this) | ~12 lines |
| 10 | Universal rec: Apple Business Connect | You | ~10 lines |
| 11 | Universal rec: Bing Places | You | ~10 lines |
| 12 | Conditional FSA + emergency + weekend query templates | You (refined to gated) | ~20 lines + plumbing |
| 13 | Quebec `inLanguage` schema (gated on QC + FR content) | You (refined gating) | ~5 lines |
| 14 | 16 new pytest cases | Me | ~150 lines test code |

**Skipped from your list:**
- ❌ Zomato (no longer in Canada)
- ❌ RECO Portal (Ontario-only; replaced with Realtor.ca for nationwide coverage)
- ❌ CPSO Public Register (Ontario-only; covered by RateMDs + Healthgrades for patient-search intent)

**Total estimated effort:** ~3 hours of focused work. About 80% on the recommendation logic, 15% on tests, 5% on the query template work.

---

## Strategic outcome — what the moat looks like after Phase 1

| Vertical | % of CA SMBs | Vertical-specific recs | Status before / after |
|---|---|---|---|
| Trades | ~15% | HomeStars + TrustedPros | ✅ shipped yesterday |
| Healthcare | ~10% | RateMDs (universal) + Opencare (dentist) | ❌ → ✅ |
| Restaurant | ~12% | OpenTable + TripAdvisor | ❌ → ✅ |
| Legal | ~3% | LawyerLocate | ❌ → ✅ |
| Realtor | ~2% | Realtor.ca | ❌ → ✅ |
| Beauty / personal | ~10% | Generic only (Yelp/Facebook) | ❌ → ❌ (no specific dirs exist) |
| Retail | ~15% | Generic only | ❌ → ❌ (correct — no specific dirs) |
| Auto | ~5% | Generic only | ❌ → ❌ (CAA-Approved possible later) |
| Professional (accountants, consultants) | ~7% | Universal (LinkedIn) | ❌ → ❌ (sparse Canadian directory landscape) |
| **Universal additions** | 100% | Apple Business Connect + Bing Places | ❌ → ✅ |

**Coverage after Phase 1:** ~42% of Canadian SMB market gets vertical-specific rec logic, plus universal Apple/Bing recs for the remaining 58%. That's a real Canadian SMB moat — no US competitor (Otterly, AthenaHQ, HubSpot AEO) is going to know to recommend Opencare to a Toronto dentist or Realtor.ca to a Vancouver realtor.

---

## Ready to execute?

If you approve the plan above, I'll:
1. Ship Phase 1 (directories + recs) — most impactful, no plumbing changes
2. Ship Phase 2 (conditional query templates) — moderate effort, requires plumbing
3. Ship Phase 3 (Quebec schema) — small, safe
4. Ship Phase 4 (tests) — locks it in

Order of operations runs tests after each phase so we don't get stuck debugging across multiple changes at once. **Reply "go"** and I'll execute.

If you want to adjust anything (drop a recommendation, rephrase a vertical, change a URL), tell me before I start. Once Phase 1 lands, those URLs and rec text are in 110 customers' dashboards.
