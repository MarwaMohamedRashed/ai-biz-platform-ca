# DataForSEO Test Runner

Automates the validation plan in [`docs/dataforseo-test-plan.md`](../../docs/dataforseo-test-plan.md).

Runs ~25 API calls (~$0.70 in credits), parses the responses, and emits
a `SUMMARY.md` with PASS/PARTIAL/FAIL verdicts mapped to the test plan's
six questions, plus a final architecture-level recommendation
(PROCEED / PROCEED_WITH_CAVEATS / PIVOT / RECONSIDER).

## One-time setup

1. Register at https://dataforseo.com and top up $20 (well above what
   the test needs — gives margin for follow-up exploration).
2. Copy your login + password from the dashboard ("API access").
3. Add them to `api/.env` (the existing Python env file):
   ```
   DATAFORSEO_LOGIN=your-login-here
   DATAFORSEO_PASSWORD=your-password-here
   ```
   The script also accepts them at the repo root `.env` or via plain
   shell env vars.
4. Copy the config template:
   ```
   cp scripts/dataforseo_test/config.example.json scripts/dataforseo_test/config.json
   ```
5. Edit `config.json` and fill in the two `TODO-...` businesses (salon
   and plumber). Suggested cities: any GTA mid-city (Oakville,
   Burlington, Milton, Brampton, Hamilton, etc.). Use real businesses,
   ideally ones you have some personal connection to.

## Running

```
python scripts/dataforseo_test/runner.py
```

Wall time: ~3 minutes. The script prints each call as it goes.

## Output

`scripts/dataforseo_test/results/{timestamp}/`:

- **`SUMMARY.md`** — read this first. Per-business verdicts, top
  keywords, PAA questions, volume coverage, branded search results,
  trend stability per keyword, mid-city-vs-Toronto ratios, and a final
  PROCEED / PIVOT / etc. decision.
- **`manifest.json`** — same verdicts as machine-readable JSON. Handy
  if you want to compare across runs later.
- **`raw/{business_slug}/*.json`** — every API response, untouched.
  Use this for deep-dive on any surprising metric.
- **`raw/toronto_comparison/{vertical}.json`** — Toronto comparator
  data for Q6, called once per unique vertical.

## What to do with the SUMMARY.md

1. Read the **Overall verdict** section first.
2. If mixed, scan the **Per-business detail** to see which business
   fails which question.
3. Cross-reference the decision matrix in
   [`docs/dataforseo-test-plan.md`](../../docs/dataforseo-test-plan.md#step-7--decision-criteria).
4. Update [`docs/market-intelligence-architecture.md`](../../docs/market-intelligence-architecture.md)
   per its **"After the test — what to update"** section before
   starting Phase 1.

## Why this exists vs running Postman manually

- **Reproducible.** Re-run with one command if results look off.
- **Verdicts are code, not subjective squinting.** The Q1-Q6
  thresholds in the test plan are encoded in `runner.py` —
  `q1_actionability`, `q2_paa_depth`, etc. Tune them in one place.
- **Archive-able.** Raw JSON results can be inspected later without
  re-calling the API.
- **Reusable.** Same script works for re-testing in 6 months or for a
  new country / vertical — just edit the config.

## Tuning thresholds

If a verdict feels too harsh / too lenient, edit the threshold
constants directly in `runner.py`. Each Q has its own function
(`q1_actionability`, `q2_paa_depth`, etc.) with the thresholds inline
near the top of the function. Re-run on the same raw JSON folder by…
actually, the script always re-fetches. If you want to re-evaluate
existing raw JSON without re-paying for the API, add an
`--offline <results_dir>` mode later (TODO if needed).
