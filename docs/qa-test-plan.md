# LeapOne — Full QA Test Plan

**Purpose:** End-to-end test plan for everything currently shipping. Use this before launch and after any major change.
**Format:** Each test has a numeric ID, preconditions, steps, and expected result. Mark each PASS / FAIL / N/A as you go.
**Estimated total time:** 90–120 minutes for a full pass.

---

## 0. Preflight (do this before any test)

Confirm the foundation works before testing features.

### 0.1 — Environment
- [ ] FastAPI server is running with `--reload` flag (so code changes auto-pick up)
- [ ] Next.js dev server is running on port 3000
- [ ] `.env` for API has `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `SERPAPI_KEY`, Supabase keys, `BILLING_ENABLED` (true/false as desired)
- [ ] Browser is in Incognito/Private (avoids stale auth cookies)
- [ ] You have access to: Supabase Dashboard (SQL Editor + Table Editor), Stripe test dashboard, the API terminal

### 0.2 — Migrations applied (run this query in Supabase SQL Editor)

```sql
SELECT table_name, column_name FROM information_schema.columns
WHERE (table_name = 'aeo_audits'    AND column_name IN ('chatgpt_mentioned','chatgpt_snippet'))
   OR (table_name = 'subscriptions' AND column_name IN ('stripe_customer_id','current_period_end','cancel_at_period_end','trial_end'))
   OR (table_name = 'businesses'    AND column_name IN ('street_address','postal_code','image_url','price_range'))
   OR (table_name = 'aeo_content'   AND column_name IN ('descriptions','faq_schema','language','paa_questions'))
ORDER BY table_name, column_name;
```

**Expected:** 14 rows. Anything fewer → re-apply the missing migration before testing.

### 0.3 — Test accounts you'll need
- One brand-new email (for fresh signup test) — e.g. `qa-new-{timestamp}@yourdomain.test`
- One existing account with at least one completed audit
- One account with subscription `active` (only needed if BILLING_ENABLED=true)
- One account with subscription `null` (only needed if BILLING_ENABLED=true)

---

## 1. Authentication

### 1.1 — Fresh signup + email verification
**Steps:**
1. Visit `/en/signup` in incognito.
2. Submit a brand-new email + valid password.
3. Check your inbox for a verification email from Supabase.
4. Click the verification link.
5. **Expected:** lands on the verified page or login screen, account is now active.

### 1.2 — Login with verified credentials
**Steps:**
1. Visit `/en/login`.
2. Enter the credentials from 1.1.
3. **Expected:** redirected to `/en/onboarding` (because no business exists yet) OR `/en/dashboard` (if business already onboarded).

### 1.3 — Login with wrong password
**Steps:**
1. `/en/login`, enter correct email + wrong password.
2. **Expected:** clear error message, no redirect.

### 1.4 — Forgot password flow
**Steps:**
1. `/en/forgot-password`, enter email.
2. Check inbox for reset link.
3. Click link, set new password, submit.
4. **Expected:** lands on confirmation, can now log in with the new password.

### 1.5 — Already-verified user clicking expired/old verify link
**Steps:**
1. Sign up, verify, then click the verification link a second time.
2. **Expected:** graceful handling — either "already verified" message or redirect to login. Should NOT throw a 500.

### 1.6 — Idle timeout
**Steps:**
1. Log in, leave the dashboard tab idle (whatever your `IdleTimeout` threshold is — check the component).
2. **Expected:** auto-logout / redirect to login after the timeout.

### 1.7 — Sign out
**Steps:**
1. Click user menu → Sign out.
2. **Expected:** session cleared, redirected to landing or login. Visiting `/en/dashboard` should redirect to login.

### 1.8 — French locale auth flow
**Steps:**
1. Visit `/fr/login`.
2. **Expected:** UI fully in French, form submission works, success/error messages localised.

---

## 2. Onboarding

### 2.1 — Required fields validation
**Preconditions:** New user in onboarding, no business created yet.
**Steps:**
1. Try to submit with name blank → button is disabled.
2. Fill name, leave type unchosen → still disabled.
3. Pick "Other" type, leave customType blank → still disabled.
4. Fill all required (name, type, city) → button enables.

### 2.2 — Happy path: Canada-based clinic
**Steps:**
1. Fill: name "Test Clinic", type "other" + customType "physiotherapy clinic", country Canada, city Ottawa, province ON.
2. Optional: website, services, street_address, postal_code, phone, image_url, price_range.
3. Submit.
4. **Expected:** business inserted into `businesses` table, `business_members` row created with role 'owner', redirects to dashboard or step 2.
5. Verify in Supabase: `SELECT * FROM businesses WHERE name = 'Test Clinic'` → row present, all fields including new schema-generator ones populated.

### 2.3 — Onboarding with US business
**Steps:**
1. New onboarding, country = United States, postal_code "94103".
2. Submit.
3. **Expected:** insert succeeds (Canadian-postal validator only fires for country=Canada).

### 2.4 — Onboarding without optional fields
**Steps:**
1. Fill only name, type, city. Leave everything else blank.
2. Submit.
3. **Expected:** insert succeeds, optional columns are NULL.

### 2.5 — Bad postal code rejection (via Settings later)
**Steps:**
1. Complete onboarding without postal code.
2. Open Settings → Business Profile.
3. Enter postal code "12345" while country=Canada → save.
4. **Expected:** HTTP 422 from PUT `/api/v1/aeo/business`, frontend shows error, row NOT updated.
5. Change postal code to "K1P 5N7" → save → succeeds.

### 2.6 — Bad image URL rejection
**Steps:**
1. Settings → image URL → enter "logo.png" (no scheme) → save.
2. **Expected:** HTTP 422, error shown.
3. Enter "https://example.com/logo.png" → save → succeeds.

### 2.7 — Price range CHECK constraint (DB-level)
**Steps:**
1. Settings → price range → select "$$$".
2. Save.
3. **Expected:** persists. Verify in Supabase Table Editor.
4. Optionally try via SQL: `UPDATE businesses SET price_range = 'medium' WHERE id = '<id>'` → expect Postgres CHECK constraint violation.

---

## 3. AEO Audit

### 3.1 — First audit on a fresh business
**Preconditions:** Business onboarded, no audits yet.
**Steps:**
1. Open `/en/dashboard`.
2. Click "Run audit" / "Generate audit" (button label depends on state).
3. Wait ~15s. Watch the API terminal — should log `[AEO]` lines for each parallel call.
4. **Expected:**
   - Score banner displays a number 0–100.
   - Pillar bars show GBP, Reviews, Website, Local, AI Citations.
   - One row inserted into `aeo_audits`.
5. Verify in Supabase: row has `chatgpt_mentioned` (boolean, can be false), `perplexity_mentioned`, `google_ai_mentioned`, `score_breakdown` JSON, `raw_results` JSONB.

### 3.2 — Audit core data sanity
**Steps:**
1. Open the audit row's `raw_results` JSONB in Supabase.
2. **Expected keys:**
   - `perplexity` with `mentioned`, `snippet`, `queries`, `per_query`
   - `google` with `ai_overview`, `local_pack`, `organic`, `knowledge_graph`, `competitors`, `per_query`
   - `chatgpt` with `mentioned`, `snippet`, `queries`, `per_query`
   - `website` with `reachable`, `has_local_business_schema`, `has_faq_schema`
   - `recommendations` (list)
   - `competitors` (list, scored)
   - `competitor_insights` (object)
   - `citation_gaps` (object) ← new, must be present
3. **Expected:** every per-query result has `organic_results_raw` (top ≤10) for citation-gap analysis to function.

### 3.3 — Score correctness sanity
**Steps:**
1. Score = sum of pillar scores.
2. GBP ≤ 25, Reviews ≤ 22, Website ≤ 20, Local Search ≤ 15, AI Citations ≤ 18.
3. Total ≤ 100.

### 3.4 — Re-run audit (no cooldown / rate limit yet)
**Steps:**
1. Run audit twice in a row.
2. **Expected:** both succeed, two new rows in `aeo_audits` with separate timestamps.
3. Score history chart now shows 2 data points.

### 3.5 — Audit when website is unreachable
**Preconditions:** Edit the business website to a definitely-broken URL like `https://this-host-does-not-exist-12345.test`.
**Steps:**
1. Run audit.
2. **Expected:** audit completes, `website_check.reachable` = false, Website pillar low. No 500 error.

### 3.6 — Audit when business has no Google presence
**Preconditions:** Use a business name + city combo that genuinely doesn't have a Google Business Profile (e.g., a freshly-named startup).
**Steps:**
1. Run audit.
2. **Expected:** audit completes. GBP and Local Search likely 0; Reviews 0; AI citations likely 0. No crash.

### 3.7 — Audit with billing enabled, no subscription
**Preconditions:** Set `BILLING_ENABLED=true` in API env, no `subscriptions` row for this business.
**Steps:**
1. Click "Run audit".
2. **Expected:** HTTP 402. Frontend should show an upgrade prompt with link to `/dashboard/plan`.
3. Reset `BILLING_ENABLED=false` afterward.

### 3.8 — Score-change email alert (Resend)
**Preconditions:** Resend domain verified, business has at least one prior audit.
**Steps:**
1. Manipulate prior audit's score to be ≥10 points away from what you expect from the next run (or just run on a business whose score will move).
2. Run audit.
3. **Expected:** owner email receives a Resend notification.
4. **If not configured:** verify in API logs that `send_score_change_alert` was called and gracefully no-op'd.

### 3.9 — Audit performance
**Steps:** Time the audit run.
**Expected:** ≤ 25s end-to-end. Anything over 30s suggests a parallelism regression — check `asyncio.gather` calls.

---

## 4. "Why this score?" drawer / dashboard score breakdown

### 4.1 — Drawer opens with all pillar details
**Steps:**
1. On dashboard audit card, click "Why this score?".
2. **Expected:** drawer / modal lists all 5 pillars with the points awarded and a brief reason for each.
3. AI Citations section shows three signal dots (ChatGPT / Perplexity / Google AI) with green/red.
4. ChatGPT section shows the training-data note when `chatgpt.mentioned=false`.
5. Each citation snippet visible if `mentioned=true`.

### 4.2 — Drawer with old audit (pre-ChatGPT migration)
**Steps:**
1. If you have any audit row from before migration 014 was applied (`chatgpt_mentioned IS NULL`), open it.
2. **Expected:** drawer renders gracefully — ChatGPT signal shows neutral state (not crashed, not "false"). Training-data note doesn't show.

### 4.3 — Methodology link
**Steps:**
1. From the drawer, click "How is the score calculated?" / methodology link.
2. **Expected:** opens `/en/methodology` page (or new tab) with full pillar formulas.

### 4.4 — Methodology page itself
**Steps:**
1. Visit `/en/methodology` directly (logged out also OK — public page).
2. **Expected:** all 5 pillars listed with sub-signals + point values + data source. Page renders without parser errors.
3. Visit `/fr/methodology` → same content in French.

---

## 5. Recommendations

### 5.1 — Recommendations appear after audit
**Steps:**
1. Run audit on a business with at least 1 weak pillar.
2. On dashboard, scroll to "Recommendations".
3. **Expected:** non-empty list. Each rec has `pillar`, `impact_pts`, `difficulty`, title, body, actions.

### 5.2 — Recommendations conditional on weakness
**Steps:**
1. For a business with `gbp = 25/25` (perfect), confirm there's NO GBP recommendation in the list.
2. For a business with `chatgpt.mentioned = false`, confirm there IS a ChatGPT-specific recommendation explaining the training-data timeline.

### 5.3 — Recommendations sorted/prioritized
**Steps:**
1. Inspect the order — should be sortable by `impact_pts` desc and `difficulty` asc, or grouped by pillar (depending on your design).
2. **Expected:** consistent and readable. High-impact items aren't buried at the bottom.

### 5.4 — Recommendation actions are concrete
**Steps:**
1. Click into one recommendation.
2. **Expected:** the `actions` array reads like a checklist — concrete steps the SMB owner can take, not vague advice.

### 5.5 — French recommendations
**Steps:**
1. Switch UI to FR (locale toggle).
2. **Expected:** recommendation titles/bodies render in French (if your codegen produces FR strings — currently they're English-only since recs are server-generated. **Note any English bleed-through as an i18n bug to fix later.**)

---

## 6. Content generation (Path A rebuild)

**Prerequisites:** migration 016 applied, API restarted, browser hard-refreshed.

### 6.1 — Smoke test
**Steps:**
1. Open `/en/dashboard/content`.
2. Click "Regenerate" (or "Generate Content" if no prior content exists).
3. Wait ~20s.
4. **Expected:**
   - 3 description tabs visible: Website / Google / Yelp
   - Social bio block with `n/150 characters` counter
   - 10 FAQ items
   - "FAQ Schema (JSON-LD)" copy block
   - "Schema Markup (JSON-LD)" copy block
5. API terminal shows no tracebacks.

### 6.2 — Database persistence
**Steps:**
1. After 6.1, query Supabase: `SELECT descriptions, faq_schema, language, paa_questions FROM aeo_content ORDER BY created_at DESC LIMIT 1`.
2. **Expected:** all 4 columns populated. `descriptions` is a JSON object with `website`, `gbp`, `yelp` keys.

### 6.3 — Per-platform descriptions
**Steps:**
1. Click each tab in turn.
2. **Website:** ~300–400 words, third person.
3. **Google:** ≤ 700 chars (counter visible at the bottom of the block).
4. **Yelp:** ~200–250 words, more concise.
5. Each tab's Copy button copies that variant only.

### 6.4 — Services in description prompt
**Preconditions:** Settings → services field has 3+ comma-separated services.
**Steps:**
1. Regenerate content.
2. Read the Website description.
3. **Expected:** every listed service appears verbatim or as a clear paraphrase.

### 6.5 — FAQ count
**Steps:**
1. Count FAQ items rendered.
2. **Expected:** 10 (occasionally 9 if the LLM dropped one — flag if ≤ 8).

### 6.6 — FAQPage JSON-LD validity
**Steps:**
1. Click Copy on the **FAQ Schema (JSON-LD)** block.
2. Open [Google Rich Results Test](https://search.google.com/test/rich-results) → **Code** tab → paste.
3. **Expected:** "Valid items detected", `FAQPage` listed.

### 6.7 — LocalBusiness schema regression
**Steps:**
1. Click Copy on the **Schema Markup (JSON-LD)** block.
2. Same Rich Results Test → Code tab → paste.
3. **Expected:** valid, with the right `@type` (e.g. `MedicalClinic`, `Restaurant`, `Plumber` based on the keyword pattern match — NOT generic `LocalBusiness` for known verticals).
4. **Expected:** `addressCountry` is "Canada" (not "CA"), no hallucinated fields like `servesCuisine` for non-restaurants.

### 6.8 — People-Also-Ask grounding
**Steps:**
1. Below the FAQ list, look for "grounded in N real Google searches".
2. **Expected:** N ≥ 3 for most populated business types. If 0, the subtitle won't appear (PAA fetch found nothing — best-effort fallback).
3. Spot-check 1–2 FAQ questions against what Google's "People also ask" actually shows for `<your business type> in <your city>`.

### 6.9 — French content variants
**Steps:**
1. Click the **FR** chip in the header.
2. Click Regenerate.
3. **Expected:** all 3 description tabs, all 10 FAQs, and the social bio render in French.
4. The schema markup's `description` field is also French.
5. Switch back to **EN** + Regenerate → content swaps back.

### 6.10 — Language drift banner
**Steps:**
1. While viewing EN content, flip the toggle to FR (don't regenerate).
2. **Expected:** amber banner reads "You're viewing content in EN. Click Regenerate to switch to FR."
3. Click Regenerate → banner disappears.

### 6.11 — "Complete your profile" CTA
**Steps:**
1. Settings → blank out `image_url` → save.
2. Content → Regenerate.
3. **Expected:** amber CTA appears in the LocalBusiness schema block listing "Logo or photo URL". Link "Update profile →" goes to `/en/dashboard/settings`.
4. Re-fill image URL, save, regenerate → CTA disappears.

### 6.12 — Validation warnings
**Steps:**
1. After Regenerate, look at the bottom of the content list.
2. **Expected (most cases):** no warnings shown.
3. Edge case: if any LLM call returned out-of-spec content, an amber Note row appears with the warning labels (e.g. `gbp description too long`, `faq too few items`).

### 6.13 — Copy includes `<script>` wrapper
**Steps:**
1. Click Copy on either schema block.
2. Paste into a text editor.
3. **Expected:** the pasted content begins with `<script type="application/ld+json">` and ends with `</script>`.

### 6.14 — "Test in Rich Results ↗" button
**Steps:**
1. Click on either schema block.
2. **Expected:** opens Google's Rich Results Test in a new tab.

### 6.15 — Old cached content (legacy shape)
**Preconditions:** An aeo_content row from before migration 016.
**Steps:**
1. Visit Content tab without clicking Regenerate.
2. **Expected:** page renders without crashing. Description shows in the Website tab (legacy single description, mapped via `normaliseContent`). FAQ schema and per-platform variants may be missing — that's expected until regenerate.

---

## 7. Competitors page

### 7.1 — Empty state — no business
**Steps:**
1. Log in as a user with no business yet.
2. Visit `/en/dashboard/competitors`.
3. **Expected:** "Complete your profile first" empty state with a Settings link.

### 7.2 — Empty state — no audit
**Steps:**
1. Log in as a user with business but no audit.
2. Visit `/en/dashboard/competitors`.
3. **Expected:** "Run an audit first" empty state.

### 7.3 — Empty state — no competitors found
**Steps:**
1. Audit a very-niche or rural business that genuinely has no Google local pack neighbors.
2. Visit Competitors page.
3. **Expected:** "We couldn't identify competitors" message with friendly framing — not a crash.

### 7.4 — Happy path with competitors
**Preconditions:** Audited business with ≥ 1 scored competitor.
**Steps:**
1. Visit Competitors page.
2. **Expected:**
   - Your score card (indigo border) at top with pillar bars
   - **NEW:** side-by-side `ComparisonTable` (You + top 3) below
   - Per-competitor cards with their pillar bars and "you +X" deltas
   - Optional: weak-points (themes) section if their reviews were analysed
   - **NEW:** "🔗 Directory Presence" section at the bottom

### 7.5 — Side-by-side comparison table (F11 polish)
**Steps:**
1. Examine the ComparisonTable.
2. **Expected:**
   - First column "You" (indigo accent), then up to 3 competitor columns
   - Rows: Total + 5 pillar rows
   - Cells color-coded by % of max (green ≥75%, amber 40–74%, red <40%)
   - Long competitor names truncated with `…` and full name on hover

### 7.6 — Citation gap analysis (F11 polish)
**Preconditions:** Audit run AFTER the F11/F12 polish migration (i.e. `citation_gaps` populated).
**Steps:**
1. Scroll to "🔗 Directory Presence" section.
2. **Expected (best case):**
   - "✓ You appear on" list of green pills
   - "Gaps — competitors are listed here, you are not" amber list
   - Each gap has a "Claim listing →" link to the right vendor URL
3. Click a Claim link → opens the vendor's signup page (e.g. Yelp → biz.yelp.com/signup).
4. **Expected (no signal case):** friendly fallback message, no crash.

### 7.7 — Competitor weak-points (F12 — already shipping)
**Preconditions:** Top-3 competitors have place_ids and Google reviews.
**Steps:**
1. Scroll to "💡 Competitor Weaknesses — Your Opportunity".
2. **Expected:**
   - Themes list with count badges (e.g. "Long wait times — 14× mentioned")
   - Optional example quote per theme
   - Strategic opportunity callout at bottom

### 7.8 — Cross-border flag
**Preconditions:** Audit a Canadian business in a city near US border (Niagara, Windsor, etc.) — Google may surface US competitors.
**Steps:**
1. Visit Competitors page.
2. **Expected:** any non-Canadian competitor is shown only after Canadian ones are exhausted, and bears a "🌍 Different country" badge.

### 7.9 — Persistence regression
**Steps:**
1. Open Supabase Table Editor → newest `aeo_audits` row → `raw_results` JSONB.
2. **Expected keys:** `competitors`, `competitor_insights`, `citation_gaps`. Old rows without `citation_gaps` should still render (the page treats it as optional).

---

## 8. Score history & monthly cron

### 8.1 — Score history chart
**Steps:**
1. After running ≥ 2 audits, visit dashboard.
2. **Expected:** line chart showing a point per audit, by date.

### 8.2 — Score-history extends across months
**Steps:** If you have audit data spanning multiple months, confirm the chart covers all of them (12 month max ideally).

### 8.3 — Monthly cron endpoint (manual trigger)
**Steps:**
1. With API running and `CRON_SECRET` set, hit:
   ```bash
   curl -X POST http://localhost:8000/api/v1/aeo/cron-monthly \
     -H "Authorization: Bearer <CRON_SECRET>"
   ```
2. **Expected:** returns `{audited: N, results: [...]}`. New audit row inserted per business.
3. **Without auth header:** 401/403.

### 8.4 — Cron persists `competitor_insights` and `citation_gaps`
**Steps:** After 8.3, check the newly-written rows include both keys in `raw_results` (recently fixed regression).

---

## 9. Settings

### 9.1 — Load existing profile
**Steps:**
1. Visit `/en/dashboard/settings`.
2. **Expected:** all fields pre-populated from the DB, including the new schema-generator fields if filled in onboarding.

### 9.2 — Save standard fields
**Steps:**
1. Change name/city/services. Save.
2. **Expected:** "Profile saved" toast, persisted to DB.

### 9.3 — Save schema-generator fields
**Steps:**
1. Fill in street_address, postal_code, phone, image_url, price_range, hours.
2. Save.
3. **Expected:** all fields saved. Refresh page → values persist.

### 9.4 — Hours editor
**Steps:**
1. Open hours editor.
2. **Expected:** 7 day rows with Closed checkbox + open/close time pickers.
3. Mark Sunday as Closed → time inputs disable.
4. Set Monday 09:00–17:00 → save.
5. Verify in DB: `SELECT hours FROM businesses` → `{"monday": "09:00-17:00", "sunday": "closed"}` shape.

### 9.5 — Reset hours to all-empty
**Steps:**
1. With existing hours, clear all days (untick Closed and leave times blank — or however your UI surfaces "no value").
2. Save.
3. **Expected:** `hours` becomes NULL in DB (empty object → NULL conversion in `_clean_hours`).

### 9.6 — Review-response settings (independent block)
**Steps:**
1. Change tone preference, response length, CTA text.
2. Save.
3. **Expected:** "Saved" toast, persisted in `business_settings`.

### 9.7 — Manage subscription button
**Preconditions:** User has a subscription with `stripe_customer_id`.
**Steps:**
1. Click "Manage subscription →".
2. **Expected:** redirects to Stripe Customer Portal.
3. **If no stripe_customer_id:** button is hidden.

### 9.8 — Locale-aware portal return
**Steps:**
1. While in `/fr/dashboard/settings`, click Manage subscription.
2. **Expected:** Stripe Portal return URL contains `/fr/`.

---

## 10. Multi-language (EN ↔ FR)

### 10.1 — UI language switch
**Steps:**
1. Visit `/en/dashboard`. Toggle locale to FR (header chip or URL change).
2. **Expected:** all UI strings switch — nav, page headers, buttons.

### 10.2 — French routes
**Steps:** All major routes accessible at `/fr/...`:
- `/fr/login`, `/fr/signup`, `/fr/onboarding`
- `/fr/dashboard`, `/fr/dashboard/insights`, `/fr/dashboard/competitors`, `/fr/dashboard/content`
- `/fr/dashboard/settings`, `/fr/dashboard/plan`
- `/fr/methodology`

### 10.3 — Translation completeness
**Steps:**
1. Browse each page in FR.
2. **Expected:** no English bleed-through in nav/labels/buttons. Some content (recommendations, audit snippets) may still be English — flag separately.

### 10.4 — Email language
**Steps:** If you can trigger a score-change alert email for a `fr` user, confirm the email is in French (or English with a note for a future translation).

---

## 11. Billing & subscriptions

**Preconditions:** `BILLING_ENABLED=true`. Stripe test API keys.

### 11.1 — Plan page renders all tiers
**Steps:**
1. Visit `/en/dashboard/plan`.
2. **Expected:** Starter ($19), Pro ($49), Agency (contact-us). Manage button only shows if user has subscription.

### 11.2 — Checkout — Starter
**Steps:**
1. Click "Choose Starter".
2. Stripe Checkout opens with the Starter price.
3. Pay with test card `4242 4242 4242 4242`, any future expiry, any CVC.
4. **Expected:** redirected to `/en/dashboard/plan/success`.
5. Webhook fires → `subscriptions` row updated with `status=trialing` or `active`, `plan_tier=starter`, `stripe_customer_id` set, `current_period_end` set.

### 11.3 — Checkout — failed card
**Steps:**
1. Click Checkout for Pro.
2. Pay with `4000 0000 0000 9995` (declined).
3. **Expected:** Stripe shows error, user can retry. No subscription row created. No 500 in our webhook.

### 11.4 — Checkout cancel
**Steps:**
1. Click Checkout, then click "Back to LeapOne" / X out.
2. **Expected:** lands on `/en/dashboard/plan/cancel` page.

### 11.5 — Customer Portal
**Steps:**
1. Settings → Manage subscription.
2. **Expected:** Stripe Portal opens. You can cancel, update card, view invoices.
3. Cancel subscription in portal → return to LeapOne.
4. **Expected:** webhook updates `subscriptions.cancel_at_period_end=true` (or `status=canceled` immediately depending on Stripe config).

### 11.6 — Audit gate when subscription canceled
**Preconditions:** Subscription status `canceled` (after grace period).
**Steps:**
1. Try to run audit.
2. **Expected:** HTTP 402, frontend prompts to re-subscribe.

### 11.7 — `customer.subscription.updated` webhook
**Steps:**
1. In Stripe Dashboard → Customers → pick the test customer → Subscriptions → upgrade/downgrade.
2. **Expected:** Stripe fires `customer.subscription.updated` → our webhook updates `plan_tier`, `current_period_end`.

### 11.8 — Locale-aware Checkout return URLs
**Steps:**
1. From `/fr/dashboard/plan`, click Checkout.
2. After paying, the success URL contains `/fr/`.

---

## 12. Cross-cutting

### 12.1 — Row-Level Security (data isolation)
**Steps:**
1. Log in as User A with Business A.
2. Note Business A's id.
3. Log in as User B (different account, different business).
4. Try `GET /api/v1/aeo/recommendations/<Business A id>` — should be 403/404.
5. Try to query Business A's audits via the Supabase client (browser-side) → should return 0 rows because of RLS.

### 12.2 — Audit endpoint security
**Steps:**
1. While logged in as User A, send `POST /api/v1/aeo/audit` with `business_id` belonging to User B.
2. **Expected:** HTTP 403 "Access denied".

### 12.3 — Generate-content endpoint security
**Steps:** Same as 12.2 but for `/generate-content`. Expect 403.

### 12.4 — Generate-content language injection
**Steps:**
1. Send `POST /api/v1/aeo/generate-content` with `language: "javascript"` (junk).
2. **Expected:** treats as `en` (default), no crash, no error.

### 12.5 — XSS resistance
**Steps:**
1. Set business name to `<script>alert('xss')</script>` in Settings.
2. Run audit, view content tab, view dashboard.
3. **Expected:** script does NOT execute. The string renders as text in all UI surfaces.

### 12.6 — Long input handling
**Steps:**
1. Set services field to 5000 characters of text. Save.
2. Run audit, generate content.
3. **Expected:** no crash. LLM prompts may truncate but the system stays up.

### 12.7 — Network failure mid-audit
**Steps:**
1. Block `serpapi.com` in your hosts file or with a network tool.
2. Run audit.
3. **Expected:** audit still completes — Google pillar may score 0, no 500. Logs show the failure clearly.
4. Unblock afterward.

### 12.8 — Concurrent audits same business
**Steps:**
1. From two browser tabs, click "Run audit" near-simultaneously.
2. **Expected:** both complete. Two new audit rows. No deadlock.

### 12.9 — Browser back button on multi-step flows
**Steps:**
1. During onboarding step 2, hit back. Expected: returns to step 1 with state preserved or a cleanly-empty form.
2. During Stripe Checkout, hit back. Expected: returns to /plan, no charge.

### 12.10 — Mobile / narrow viewport (smoke test only)
**Steps:**
1. Resize browser to ~375px width.
2. **Expected:** dashboard, content, competitors pages don't horizontally scroll on standard content. Tables (ComparisonTable) may scroll horizontally — that's expected.

### 12.11 — Audit endpoint response shape
**Steps:** With DevTools → Network, watch the `/audit` response.
**Expected keys:** `score`, `breakdown`, `recommendations`, `perplexity`, `google`, `chatgpt`, `website`, `competitors`, `competitor_insights`, `citation_gaps`, `raw_results`.

---

## 13. Public surfaces (logged-out)

### 13.1 — Landing page renders
**Steps:** Visit `/`. Expected: full landing page, screenshots, pricing CTAs, no console errors. Google Analytics tag fires (Network tab → `gtag` request).

### 13.2 — Landing page in French
**Steps:** Visit `/fr`. Expected: full FR translation, links go to `/fr/...`.

### 13.3 — Landing page schema markup
**Steps:** View source of `/`. Expected: `<script type="application/ld+json">` with LocalBusiness object + Open Graph meta tags.

### 13.4 — Methodology page logged-out access
**Steps:** Visit `/en/methodology` while logged out. Expected: page renders, no auth redirect.

---

## 14. Things to watch for during testing (pattern smells)

- **Slow audits** (>30s) — likely a parallelism regression
- **0/0 scores** with no error message — error is silently swallowed somewhere
- **`null` values rendered as the string "null"** — missing fallback
- **Untranslated English in FR** — i18n key missing
- **Browser console errors** — typically a hydration mismatch or missing key
- **API tracebacks in terminal** — anything Python-level is a real bug, even if the user-visible behavior looks OK
- **Stripe webhook 4xx in Stripe Dashboard → Webhooks → Recent events** — silent webhook failures break billing without breaking the UI

---

---

## 15. Reviews module

**Status:** Built but Google API approval is blocked until July 2026, so any "post response back to Google" path will fail. Everything else (read, AI-draft, edit, approve) works against the existing data.

### 15.1 — Reviews list page renders
**Steps:**
1. Visit `/en/dashboard/reviews`.
2. **Expected:** list of reviews from the latest audit (or empty-state with "no reviews yet" if none).
3. Each row shows rating, reviewer name, snippet, date.

### 15.2 — Generate AI response for a single review
**Preconditions:** At least one review present; `OPENAI_API_KEY` (or whatever `AI_PROVIDER` points to) set.
**Steps:**
1. Click into a review.
2. Click "Generate response" / "Draft reply".
3. Wait ~5–10s.
4. **Expected:** an AI-drafted response appears in the response field. Tone matches `business_settings.tone_preference`. Length matches `response_length`.

### 15.3 — Regenerate response
**Steps:**
1. With a draft visible, click "Regenerate".
2. **Expected:** a new draft replaces the old one. The previous draft is NOT preserved (this is the design — if it should be, flag it).

### 15.4 — Edit response before approving
**Steps:**
1. Generate a draft, then edit the text manually.
2. Click "Approve" / "Save".
3. **Expected:** the edited version is what's persisted, not the LLM original.

### 15.5 — Bulk auto-draft
**Preconditions:** Multiple un-responded reviews.
**Steps:**
1. Click "Auto-draft all" (or whatever the bulk button is labelled).
2. Wait — this may take a while depending on review count.
3. **Expected:** every review now has a draft. API logs show one LLM call per review.

### 15.6 — Approve response (Google API blocked)
**Steps:**
1. With a drafted response, click "Approve & post".
2. **Expected:** the response is saved as approved in our DB. **The actual Google posting step is gated on Google API approval — it should fail gracefully with a "pending Google API approval" message rather than throwing a 500.** Verify the gate exists.

### 15.7 — Tone preference respected
**Steps:**
1. Settings → review settings → set tone to "playful".
2. Generate a new draft.
3. **Expected:** noticeably different tone vs the same review drafted with "professional".

### 15.8 — Language matching
**Steps:**
1. Settings → response_language = `match_reviewer`.
2. Find a French-language review and a French-language reviewer.
3. Generate response.
4. **Expected:** response is in French.
5. Switch to `english` setting → regenerate same review → response in English.

---

## 16. Profile page (user account, NOT business)

### 16.1 — Profile page loads
**Steps:**
1. Visit `/en/dashboard/profile`.
2. **Expected:** form pre-filled with name + email from Supabase auth user metadata. Avatar URL field shown if present.

### 16.2 — Update display name
**Steps:**
1. Change name field.
2. Click Save.
3. **Expected:** name updated in `auth.users.user_metadata`. Refresh page → persists. Header user menu reflects new name.

### 16.3 — Email field is read-only
**Steps:**
1. Try to edit email.
2. **Expected:** field is disabled (changing email is a separate flow gated on re-verification).

### 16.4 — Logged-out access
**Steps:**
1. Sign out, then visit `/en/dashboard/profile`.
2. **Expected:** redirects to `/login` (not crashed, not 500).

---

## 17. Insights page

The Insights page is distinct from the dashboard home. It deep-links from "see details" or directly via `/dashboard/insights`.

### 17.1 — Insights renders with audit data
**Preconditions:** At least one completed audit.
**Steps:**
1. Visit `/en/dashboard/insights`.
2. **Expected:** detailed pillar breakdown, recommendations list, score-history chart. No console errors.

### 17.2 — Insights with no audit
**Preconditions:** Business onboarded but no audit yet.
**Steps:**
1. Visit `/en/dashboard/insights`.
2. **Expected:** empty-state with "run an audit" CTA, NOT a crash or "undefined" UI.

### 17.3 — Recommendations expand/collapse (if interactive)
**Steps:**
1. Click into a recommendation.
2. **Expected:** body + actions list visible. Smooth UX.

### 17.4 — French-locale insights
**Steps:**
1. Visit `/fr/dashboard/insights`.
2. **Expected:** UI strings in French. Audit data may still be in English (data is server-generated; flag as i18n debt if relevant).

---

## 18. OwnReputationCard (`/api/v1/aeo/own-reputation`)

Cached strengths + weaknesses extraction from the user's own Google reviews. Lives on the Competitors page.

### 18.1 — Card renders on Competitors page
**Preconditions:** Latest audit has a `place_id` in `raw_results.google.knowledge_graph` (i.e. business is indexed by Google).
**Steps:**
1. Visit `/en/dashboard/competitors`.
2. Scroll to the bottom — `OwnReputationCard` should be present.
3. **First load:** card may show a loading state, then populate with strengths + weaknesses + summary.

### 18.2 — Cache hit on second view
**Steps:**
1. Refresh the Competitors page within the same audit cycle.
2. **Expected:** card loads instantly (cached in `raw_results.own_reputation`). API logs show no new SerpApi call for reviews.
3. Verify in Supabase: `SELECT raw_results->'own_reputation' FROM aeo_audits ORDER BY created_at DESC LIMIT 1` → has `strengths`, `weaknesses`, `summary`, `review_count`, `avg_rating`.

### 18.3 — No place_id branch
**Preconditions:** Audit a business that's NOT indexed by Google → `knowledge_graph.place_id` is null.
**Steps:**
1. Visit Competitors page.
2. **Expected:** card renders gracefully with "we couldn't find your business on Google" or hides itself. NOT a crash.
3. API response shape: `{strengths:[], weaknesses:[], summary:"", error:"no_place_id"}`.

### 18.4 — Re-run audit refreshes cache
**Steps:**
1. With cached own_reputation visible, click "Re-run audit" on the dashboard.
2. After audit completes, return to Competitors page.
3. **Expected:** new audit has its own `own_reputation` cache (fresh). Old cache stays attached to its own audit row in DB.

---

## 19. Multi-business scenarios

The schema supports a user owning multiple businesses (`business_members` table). The UI today mostly assumes one. Worth a smoke test.

### 19.1 — Add a second business via direct DB insert
**Preconditions:** You already have one business as User A.
**Steps:**
1. In Supabase SQL Editor, insert a second business owned by the same user:
   ```sql
   INSERT INTO businesses (user_id, name, type, city, country, province)
   VALUES (auth.uid(), 'Second Test Biz', 'salon', 'Toronto', 'Canada', 'ON');
   -- then create membership:
   INSERT INTO business_members (business_id, user_id, role)
   VALUES ((SELECT id FROM businesses WHERE name = 'Second Test Biz'), auth.uid(), 'owner');
   ```
2. **Expected:** insert succeeds (no unique-on-user_id constraint).

### 19.2 — Dashboard with 2 businesses
**Steps:**
1. As that user, visit `/en/dashboard`.
2. **Expected:** dashboard shows ONE business (whichever the page-load query picks first). Document in your bugs log if this is wrong — multi-business UI selector isn't built yet, so single-business display is the current correct behavior.

### 19.3 — RLS still works
**Steps:**
1. As User B (different account), try to see the second business via Supabase client SELECT.
2. **Expected:** 0 rows. RLS policy "Members can view their businesses" must be working.

### 19.4 — Cleanup
**Steps:** Delete the test rows after the check:
```sql
DELETE FROM businesses WHERE name = 'Second Test Biz';
-- business_members row cascades automatically
```

---

## 20. Error paths beyond SerpApi

### 20.1 — OpenAI API key invalid
**Steps:**
1. Set `OPENAI_API_KEY=sk-bad` in `.env`. Restart API.
2. Click Re-run audit.
3. **Expected:** the ChatGPT pillar scores 0 (queries fail per-query, caught by the try/except in `_chatgpt_one`). Audit overall still completes. **NOT a 500.**
4. Click Generate Content.
5. **Expected:** descriptions / FAQ generation fails with a clean error. Frontend shows "Generation failed. Please try again." NOT a hung tab.
6. Restore the real key after.

### 20.2 — Perplexity API key invalid
**Steps:**
1. Set `PERPLEXITY_API_KEY=bad`. Restart API.
2. Re-run audit.
3. **Expected:** Perplexity pillar scores 0, audit overall still completes.
4. Restore.

### 20.3 — SerpApi key invalid
**Steps:**
1. Set `SERPAPI_KEY=bad`. Restart API.
2. Re-run audit.
3. **Expected:** GBP, Reviews, Local Search, Citation Gaps may all be 0/empty. Audit still returns a result. ChatGPT and website pillars still work.
4. Restore.

### 20.4 — Resend API key missing (score-change alerts)
**Steps:**
1. Set `RESEND_API_KEY=` (empty). Restart API.
2. Trigger a score change ≥10 points.
3. **Expected:** API logs warn that email couldn't be sent, audit still saves. NOT a 500.
4. Restore.

### 20.5 — Supabase connection drop mid-audit (hard to simulate cleanly)
**Optional / advanced:** Start an audit, kill Supabase access mid-flight (toggle network).
**Expected:** clean error, no half-written rows. Skip if hard to set up — covered by RLS testing above for the security side of it.

---

## 21. Additional cron + webhook edge cases

These extend section 8 (cron) and section 11 (billing).

### 21.1 — Cron with WRONG secret
**Steps:**
1. With `CRON_SECRET="real-secret"` set:
   ```bash
   curl -X POST http://localhost:8000/api/v1/aeo/cron-monthly \
     -H "Authorization: Bearer wrong-secret"
   ```
2. **Expected:** HTTP 401 or 403. NOT 200, NOT 500.

### 21.2 — Cron with no header (re-confirms 8.3)
Already covered in 8.3 — keep this row to mark the auth gate is intentional.

### 21.3 — Stripe `invoice.payment_failed` webhook
**Preconditions:** Active subscription. Stripe CLI listening.
**Steps:**
1. In Stripe Dashboard → Customers → pick the subscriber → manually mark a recent invoice as failed (or use `stripe trigger invoice.payment_failed` via CLI).
2. **Expected:** our webhook receives the event, updates `subscriptions.status` to `past_due` (per the handler logic).
3. The audit gate (12.X / 11.6) should now treat this user as having no active subscription.

### 21.4 — Stripe webhook with bad signature
**Steps:**
1. Send a POST to `/api/v1/billing/webhook` with a forged `Stripe-Signature` header.
2. **Expected:** HTTP 400 with "Invalid signature". NOT processed as if it were real.

### 21.5 — Stripe `customer.subscription.deleted` (immediate cancel)
**Steps:**
1. In Stripe Dashboard, cancel a subscription with "Cancel immediately" (not at period end).
2. **Expected:** webhook updates `subscriptions.status` to `canceled` right away. User loses access to gated audit immediately.

---

---

## 22. Reddit citation surface (added 2026-05-08)

Reddit is detected as an organic-result source for citations and surfaces a
universal "Build authentic Reddit presence" recommendation. UI uses a
"Browse mentions →" action label instead of "Claim listing →".

### 22.1 — Reddit detection from organic results
**Preconditions:** Audit a business that genuinely shows up in a Reddit thread (e.g. a popular Toronto restaurant or a clinic that's been mentioned on r/HomeImprovement).
**Steps:**
1. Run a fresh audit.
2. Open Supabase → newest `aeo_audits` row → `raw_results.citation_gaps.user`.
3. **Expected:** if a Reddit thread mentioning the business appeared in any of the 3 Google queries' top-10 organic results, `"Reddit"` appears in the `user` array.

### 22.2 — Reddit appears in the Directory Presence section
**Steps:**
1. After 22.1, visit `/en/dashboard/competitors`.
2. Scroll to "🔗 Directory Presence" section.
3. **Expected:** if you appear on Reddit, a green "✓ Reddit" pill is shown alongside other directories. If you don't, Reddit appears in the amber gap list (when at least one competitor is detected on it).

### 22.3 — Reddit gap shows "Browse mentions →" not "Claim listing →"
**Steps:**
1. With Reddit in the gap list, find its row.
2. **Expected:** the action label reads **"Browse mentions →"**, not "Claim listing →". Click → opens Reddit search.

### 22.4 — Reddit recommendation fires on a fresh audit
**Steps:**
1. Audit any business that doesn't appear on Reddit.
2. Open dashboard → Insights / recommendations.
3. **Expected:** a recommendation titled "Build authentic Reddit presence" appears.
4. **Expected difficulty:** "hard" (not "easy" — community engagement is genuinely long-term).
5. **Expected action text:** must include the word "astroturf" — we explicitly warn against self-promotion-disguised-as-engagement.

### 22.5 — Reddit rec links to city-specific subreddit when known
**Steps:**
1. Set business city to "Toronto", "Ottawa", or "Vancouver" in Settings.
2. Re-run audit.
3. View the Reddit recommendation.
4. **Expected:** the action URL points to `https://www.reddit.com/r/<city_subreddit>` (e.g. r/toronto, r/ottawa).

### 22.6 — Reddit rec falls back gracefully for unknown cities
**Steps:**
1. Set business city to an obscure value not in the `CITY_SUBREDDITS` map (e.g. "Smallville").
2. Re-run audit.
3. **Expected:** Reddit rec URL is `https://www.reddit.com/search/?q=Smallville` (search-fallback). NOT a 404 to a non-existent subreddit.

### 22.7 — Reddit rec does NOT fire when already detected
**Steps:**
1. Audit a business that's already on Reddit (e.g. a well-known business mentioned in r/<city> threads).
2. Confirm `Reddit` appears in `raw_results.citation_gaps.user`.
3. **Expected:** no Reddit recommendation in the list. The user already has the citation.

### 22.8 — Astroturfing warning is in the rec text (regression check)
**Why:** The original product spec required honest framing — telling customers to spam Reddit would actively harm them.
**Steps:**
1. Inspect the Reddit recommendation `action` field.
2. **Expected:** contains the word "astroturf" or equivalent warning. Pytest enforces this via `test_reddit_rec_warns_against_astroturfing`.

---

## 23. LinkedIn B2B vertical recommendation (added 2026-05-08)

For professional services / B2B verticals, a LinkedIn Company Page is a
real AI citation signal. New `_is_b2b_business()` detector covers lawyers,
accountants, consultants, agencies, financial advisors, recruiters,
realtors, architects, software/SaaS companies. Recommendation fires only
when the business is B2B AND not already detected on LinkedIn.

### 23.1 — Lawyer gets BOTH LinkedIn and LawyerLocate recs
**Preconditions:** Business with type "law firm" or "lawyer".
**Steps:**
1. Run audit, view recommendations.
2. **Expected:** both "Activate your LinkedIn Company Page" AND "Claim your LawyerLocate profile" appear (intentional overlap — they serve different surfaces).

### 23.2 — Accountant gets LinkedIn rec
**Preconditions:** Business type contains "accountant" / "CPA" / "bookkeeper" / "accounting firm".
**Steps:**
1. Run audit.
2. **Expected:** LinkedIn rec appears.

### 23.3 — Marketing agency / consultant / financial advisor get LinkedIn rec
**Steps:** Repeat 23.2 with these business types. **Expected:** LinkedIn rec appears for each.

### 23.4 — Realtor gets BOTH LinkedIn and Realtor.ca recs
**Steps:**
1. Business type "real estate agent" or "realtor".
2. **Expected:** both Realtor.ca AND LinkedIn recs appear.

### 23.5 — Consumer verticals do NOT get LinkedIn rec
**Steps:** For each of these business types — "dentist", "restaurant", "hair salon", "plumber", "bakery", "physiotherapy clinic" — confirm NO LinkedIn recommendation.
**Expected:** these are not B2B verticals. LinkedIn is irrelevant to their citation strategy. False positives here are bad UX.

### 23.6 — LinkedIn rec does NOT fire when already on LinkedIn
**Steps:**
1. Audit a B2B business whose LinkedIn page appears in their organic results.
2. **Expected:** no LinkedIn recommendation. Rec is gated on "not already detected".

### 23.7 — LinkedIn rec difficulty is "medium"
**Why:** LinkedIn presence is an ongoing weekly-posting commitment, not a one-time profile claim. Framing this as "easy" sets wrong expectations.
**Steps:** Inspect the LinkedIn recommendation `difficulty` field.
**Expected:** `"medium"`. Pytest enforces this.

---

## Sign-off

When all sections are PASS, Path A is launch-ready and the F11/F12 polish is shipped.

| Area | PASS / FAIL / N/A | Notes |
|---|---|---|
| 0. Preflight |   |   |
| 1. Authentication |   |   |
| 2. Onboarding |   |   |
| 3. AEO Audit |   |   |
| 4. "Why this score?" |   |   |
| 5. Recommendations |   |   |
| 6. Content generation |   |   |
| 7. Competitors |   |   |
| 8. Score history & cron |   |   |
| 9. Settings |   |   |
| 10. Multi-language |   |   |
| 11. Billing |   |   |
| 12. Cross-cutting |   |   |
| 13. Public surfaces |   |   |
| 15. Reviews module |   |   |
| 16. Profile page |   |   |
| 17. Insights page |   |   |
| 18. OwnReputationCard |   |   |
| 19. Multi-business |   |   |
| 20. Error paths (non-SerpApi) |   |   |
| 21. Cron + webhook edges |   |   |
| 22. Reddit citation surface |   |   |
| 23. LinkedIn B2B rec |   |   |

---

## Bugs / observations log

Use this section to capture anything non-blocking you spot during testing — for triage later.

| ID | Area | Description | Severity | Status |
|---|---|---|---|---|
|   |   |   |   |   |
