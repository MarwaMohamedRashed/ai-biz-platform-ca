# AEO Roadmap — Remaining Work

**Last updated:** 2026-05-01
**Use:** Working backlog for AEO Phase 1. Tick items off as they ship.

---

## Known Gaps & Pre-launch Blockers

### Email (Resend)
- **Status:** Code complete. Not live in production.
- **What's needed (manual steps):**
  1. Create account at resend.com and generate an API key
  2. Verify the sender domain (e.g. `leapone.ca`) in the Resend dashboard — required before any email sends
  3. Set `RESEND_API_KEY` and `FROM_EMAIL=noreply@leapone.ca` in Railway env vars
- **What's wired:** Score-change alerts (`±10 pts`) in `api/aeo/router.py`. Auth emails still use Supabase defaults.
- **Risk if skipped:** Score alerts silently fail. Users won't know their score changed between monthly audits.

### Railway Deploy
- **Status:** Not started. No `Dockerfile` or `railway.toml` exists.
- **What's needed:**
  1. Create `api/Dockerfile` (Python 3.12, `uvicorn main:app --host 0.0.0.0 --port $PORT`)
  2. Create `api/railway.toml` pointing to the Dockerfile
  3. Set all env vars in Railway dashboard: `RESEND_API_KEY`, `FROM_EMAIL`, `SERPAPI_KEY`, `PERPLEXITY_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CRON_SECRET`
  4. Point the Vercel frontend's `NEXT_PUBLIC_API_URL` to the Railway URL
- **Risk if skipped:** The audit endpoint runs on localhost only. All users share a developer laptop.

### Audit Re-run Rate Limiting
- **Status:** Not implemented. Any user can click "Re-run audit" unlimited times.
- **Cost impact:** Each audit = 5 SerpApi calls + 3 Perplexity calls. Unlimited re-runs = unbounded API cost.
- **Decision (2026-05-01):** Defer to F9. Add a per-user daily cap (e.g. 3 manual audits/day) in the audit endpoint before Railway deploy.

### Review Recency — `google_maps_reviews` call
- **Status:** Implemented (2026-05-01). Not yet tested in production.
- **Cost:** 1 extra SerpApi credit per audit, only when `place_id` is available from the Knowledge Graph.
- **Watch for:** Businesses where `place_id` is returned but `google_maps_reviews` returns 0 results (private/restricted listings). The code handles this gracefully (skips recommendation).

---

## Sprint F8 — Reliability + Monitoring

> **Email note (2026-05-01):** Currently using Supabase default emails for auth (signup confirmation etc.).
> Resend is wired in `core/notifications.py` and used for score-change alerts, but the sender domain and
> API key need to be configured in production before transactional emails go live. Revisit before F9 deploy.

| # | Task | Pillar/Area | Priority | Done |
|---|---|---|---|---|
| 1 | Fix Reviews=0 bug — add 4th SerpApi query targeting business name to force `knowledge_graph` to return | Reviews / GBP | High | ☑ |
| 2 | Verify Website pillar gives 0 on 5xx errors (test with a known-down site) | Website | High | ☑ |
| 3 | Add Content nav link in dashboard sidebar (currently hidden — must type URL) | UX | High | ☑ |
| 4 | Create `score_history` view or query on `aeo_audits` for charting | Monitoring | Medium | ☑ |
| 5 | Build score-over-time line chart on dashboard (last 6 months) | Monitoring | Medium | ☑ |
| 6 | Add per-pillar trend deltas ("GBP +5, Reviews -2 vs last month") | Monitoring | Medium | ☑ |
| 7 | Set up Vercel cron / Supabase scheduled function for monthly auto-audits | Monitoring | Medium | ☑ |
| 8 | Email alert when score changes ≥ ±10 points | Monitoring | Low | ☑ |

---

## Sprint F9 — Onboarding + Production

| # | Task | Area | Priority | Done |
|---|---|---|---|---|
| 1 | Create `api/Dockerfile` + `api/railway.toml` for Railway deploy | Deploy | **Blocker** | ☐ |
| 2 | Set all Railway env vars + point Vercel `NEXT_PUBLIC_API_URL` to Railway | Deploy | **Blocker** | ☐ |
| 3 | Configure Resend domain + set `RESEND_API_KEY` / `FROM_EMAIL` in Railway | Email | **Blocker** | ☐ |
| 4 | Add per-user audit re-run rate limit (3/day) before Railway deploy | Cost control | High | ☐ |
| 5 | Validate per-audit cost in production, finalize pricing | Deploy | High | ☐ |
| 6 | Add "Have you claimed your GBP?" yes/no in onboarding | Onboarding | Medium | ☐ |
| 7 | Allow user to enter primary GBP category directly | Onboarding | Medium | ☐ |
| 8 | Validate website URL format more strictly | Onboarding | Low | ☐ |
| 9 | Update marketing/pricing pages with new pillar UI screenshots | Marketing | Medium | ☐ |
| 10 | French translations for new pillar labels + recommendations | i18n | Medium | ☐ |

---

## Sprint F10 — Competitive features (optional but high-value)

| # | Task | Why | Priority | Done |
|---|---|---|---|---|
| 1 | Competitor benchmarking — run audit on 1–2 competitors, show score gap | Killer feature in Otterly/AthenaHQ | High | ☐ |
| 2 | Sentiment analysis on AI mentions (positive/negative tone) | HubSpot weights this 40% | Medium | ☐ |
| 3 | Schema upgrade — replace substring matching with `extruct` library | Accuracy | Low | ☐ |
| 4 | Add organic ranking position tracking (SEO layer) | Cover GEO/SEO fully | Medium | ☐ |

---

## Post-launch / V2 — Marketing site polish

Items that aren't blocking the June 1 launch but should land soon after, while early-bird beta users are onboarded.

| # | Task | Area | Priority | Done |
|---|---|---|---|---|
| 1 | French landing page (`apps/landing/fr/index.html`) — full translation of the marketing site, not just app strings | i18n / Marketing | Medium | ☐ |
| 2 | Designed 1200×630 Open Graph banner image to replace `leapone-icon.png` fallback (current OG card shows the small square icon instead of a proper landscape preview) | Marketing | Medium | ☐ |
| 3 | Rewrite landing page with screenshots of the live audit, recommendations, and competitor analysis (current copy is pre-product, will be replaced post-launch) | Marketing | High | ☐ |
| 4 | Pricing page with finalized $19 Starter / $49 Pro tiers (currently placeholder) | Marketing | High | ☐ |

---

## Phase 2 — AI Sales Agent
Starts after AEO Phase 1 launches and stabilizes. Roadmap details in `project_sprint_roadmap.md`.

## Phase 3 — Reviews Auto-Post
Resumes ~July 2026 when Google API approval expected. All code already built.
