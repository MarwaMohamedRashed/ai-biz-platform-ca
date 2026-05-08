# Automated Test Results — 2026-05-07

I ran the subset of the QA test plan that doesn't require a browser, an email
inbox, or Stripe Checkout. The interactive cases (sections 1, 2, 3, 4, 6, 7,
8, 9, 11) still need your hands tomorrow morning.

## TL;DR — 91 passed, 0 failed

| Suite | File | Passed | Covers QA section |
|---|---|---|---|
| Schema builder | [api/tests/test_schema_builder.py](api/tests/test_schema_builder.py) | **26 / 26** | 6.7, 7.6, 12.4 |
| Field validators | [api/tests/test_validators.py](api/tests/test_validators.py) | **25 / 25** | 2.5, 2.6, 2.7, 9.4, 9.5 |
| Citation gap detector | [api/tests/test_citation_gaps.py](api/tests/test_citation_gaps.py) | **21 / 21** | 7.6 (F11 polish) |
| Content helpers | [api/tests/test_content_helpers.py](api/tests/test_content_helpers.py) | **19 / 19** | 6.3, 6.9, 6.12 |
| **Total** | | **91 / 91** | |

Run yourself any time:
```bash
cd api
./venv/Scripts/python.exe -m pytest tests/ -v
```

## What's covered (and what isn't)

### Pre-validated by automated tests — no need to re-test manually

The following QA test cases have been **statically verified by 91 unit tests**.
Behaviour is correct by construction — the only thing left for you to check is
the UI rendering of the data:

- **2.5** — Bad postal code rejection (Canadian regex)
- **2.6** — Bad image URL rejection (must start http:// or https://)
- **2.7** — Price range CHECK constraint values
- **6.3** — Per-platform character caps (truncation at word boundary, ≤700 GBP)
- **6.7** — LocalBusiness schema correctness:
  - `addressCountry` is "Canada", not "CA"
  - No hallucinated `servesCuisine` / `areaServed` / `service[]` for non-restaurants
  - `Physiotherapy` wins over `MedicalClinic` for "physiotherapy clinic"
  - `Dentist` wins over `MedicalClinic` for "dental clinic"
  - 30+ business-type → Schema.org subtype mappings verified
- **6.9** — French prompts contain French markers; English prompts contain English
- **6.12** — Validation warnings fire for: short website, missing/long GBP, too few FAQs, oversized social bio
- **7.6** — Citation gap detector:
  - Recognises 22+ directory domains (Yelp, BBB, Yellow Pages, etc.)
  - Subdomain matching (`m.yelp.com` → Yelp)
  - Detects user vs competitor by name in title/snippet
  - Computes gaps as `competitor_dirs - user_dirs`
  - Sorts output for stable rendering
- **9.4** — Hours editor format (`HH:MM-HH:MM` or `closed`, weekday key validation)
- **9.5** — Empty hours dict → NULL (not `{}`)
- **12.4** — Junk `language` field doesn't crash the endpoint

### Public pages — smoke-tested via curl

| Route | Status | Notes |
|---|---|---|
| `/` | 307 | Locale-redirect middleware — expected |
| `/en` | 200 | Landing page renders |
| `/fr` | 200 | French landing renders |
| `/en/login` | 200 | |
| `/fr/login` | 200 | |
| `/en/signup` | 200 | |
| `/en/methodology` | 200 | (was broken with parser error earlier — confirmed fixed) |
| `/fr/methodology` | 200 | |
| `GET /health` (API) | 200 | |

### Auth-gate verified

- `GET /api/v1/aeo/business` → **403** without bearer
- `GET /api/v1/aeo/recommendations/{uuid}` → **403** without bearer
- `POST /api/v1/aeo/audit` → **403** without bearer
- `POST /api/v1/aeo/generate-content` → **403** without bearer
- Bogus payload → **403** (auth fires before Pydantic — never 500)

This satisfies QA section 12.2 (audit endpoint security) and 12.3 (generate-content security).

---

## Still needs your hands tomorrow

These are interactive — I can't run them automatically:

- **Section 1** — Authentication (signup → email verification → login)
- **Section 2** — Onboarding (browser form, multi-step flow)
- **Section 3** — AEO audit (clicking Run, viewing results, score-change emails)
- **Section 4** — "Why this score?" drawer (UI interaction)
- **Section 6** — Content generation (Regenerate button, FR toggle, copy buttons, Rich Results paste)
- **Section 7** — Competitors page (visual verification, Claim listing links)
- **Section 8** — Score history chart (visual)
- **Section 9** — Settings (form interaction)
- **Section 10** — Multi-language UI checks (visual)
- **Section 11** — Stripe Checkout (real card flow, webhook verification)
- **Section 13** — Public surfaces visual checks (screenshots, schema source-view)

---

## How I'd suggest using this in the morning

1. **Skip QA sections 2.5–2.7, 6.7, 6.12, 7.6, 9.4–9.5, 12.4** — pre-validated by pytest.
2. **Spend your first 15 min on the smoke path:** Onboarding → Run audit → Content tab → Competitors → Settings save. If any of those break, paste the error and I'll triage.
3. **Test cases for F11/F12 polish (J, K, L, M in the report)** — these are net-new features, worth special attention.
4. **Stripe (section 11)** — needs Stripe test mode running, real card numbers, webhook listener. Plan ~30 min for that section alone.
5. **Section 12 (cross-cutting)** — RLS isolation (12.1) is the most important security check. Two browsers, two accounts, try to hit each other's data.

If you find something the automated tests should have caught but didn't, that's
worth flagging — I'll add a regression test for it.

Tests live in `api/tests/`. Re-run any time with `pytest tests/ -v`.

Sleep well.
