# LeapOne AEO — Competitive Gaps & What to Build Next

**Last updated:** 2026-05-01
**Audience:** Product strategy, founders, planning the next sprint
**Length:** ~10 minute read
**Premise:** We have a working Phase 1 product. To win small-business trust and beat the incumbents, what's missing?

---

## Part 1 — Production blockers (ship before we charge anyone)

These are not "nice to have." They are the gap between "working in dev" and "ready to invoice a customer." Pull them all forward into a Sprint F9 / pre-launch sprint.

| # | Item | Why it blocks launch | Effort |
|---|---|---|---|
| 1 | **Railway Dockerfile + deploy** | Backend runs on `localhost:8000` only. Vercel can't reach it. | 1 day |
| 2 | **Resend sender-domain verification** | Score-change alerts will silently fail in production. Trust killer if a customer's score swings and we don't email them. | 30 min in DNS + Resend dashboard |
| 3 | **`vercel.json` cron schedule** | Without it, monthly auto-audits don't fire — and "monthly auto-audits" is a core promise of the product. | 5 min |
| 4 | **Audit rate limiting** | Currently unlimited. A bored or malicious user can cost us $5+/hour by clicking re-run. | Half day (Redis or DB-counter) |
| 5 | **Verify Website 5xx behavior** | Known issue from Sprint F7 — partial credit awarded for unreachable sites. | 30 min |
| 6 | **French translations for new UI strings** | Pillar labels and recommendation text are English-only; we sell to Quebec SMBs too. | 2 hours |
| 7 | **Privacy policy + terms** | Required before taking payment. We crawl the user's website and call third-party APIs with their data — that has to be disclosed. | Half day |
| 8 | **Basic error tracking (Sentry)** | We're flying blind in production without it. | 2 hours |

**Estimated total:** ~3 working days for one engineer. None of these are interesting — they are table stakes.

---

## Part 2 — Trust signals (the SMB sales pitch)

Small business owners are skeptical. Most have been burned by SEO consultants who sold opaque dashboards. Three categories of features specifically build trust.

### 2.1 — "Show your work" features
Make the score auditable. If we say a clinic scored 65, the owner should be able to click and see *exactly which pillars hit, what queries we ran, and what each engine returned.*

| Feature | Why it matters |
|---|---|
| **Methodology page** (public) | Walk through the formula, the queries, the data sources. Owners forward this to their marketing person. |
| **"Why this score?" raw-data drawer** on the audit card | Show the actual Perplexity reply, the actual SerpApi local pack JSON, the actual scraped HTML schema. Make the score impossible to dispute. |
| **Cited-by-which-engine badges** | If they're cited by Perplexity but not by Google AI Overview, show "Perplexity ✓ / Google AI ✗" with the snippet. |
| **Score-change diff** | When the score moves, show "+5 from Reviews (10 → 12 reviews)" — not just the new total. |

### 2.2 — "We're working for you" features
Most of these already exist or are partially built — finish them.

| Feature | Status | Note |
|---|---|---|
| Monthly auto-audits | Built | Just needs `vercel.json` |
| Score-change alerts (±10 pts) | Built | Just needs Resend domain verified |
| Score-history chart | Built | Could be expanded to 12 months |
| Action tracking | **Missing** | When the user marks a recommendation "done", re-check that pillar within minutes. Cleanest "did your action work?" loop. |
| Email digest weekly | **Missing** | "Here's what changed this week, here's your top recommendation" — recurring touchpoint, low effort to implement |
| In-app activity feed | **Missing** | "Audit ran Apr 1, score went from 45 → 58, top action completed: GBP claimed" — historical record |

### 2.3 — "Proof we know what we're talking about"

| Feature | Why |
|---|---|
| **3 case studies** (real or beta-customer) | "Maple Leaf Dental went from 23 to 71 in 2 months." Critical for landing-page conversion. |
| **Free public AEO grader at `leapone.ca/grade?biz=...`** | HubSpot ships a free AI Search Grader for exactly this lead-gen reason. Lands in inbound funnel. |
| **Guarantees** | "If your score doesn't move in 60 days, you don't pay." Enormous trust unlock for $19/mo. |
| **Sample audit downloadable** | Owners want to see the deliverable before paying. PDF export. |

---

## Part 3 — The big competitive gap: COMPETITOR INTELLIGENCE

This is the single feature that, more than anything else, would let LeapOne win against Otterly, AthenaHQ, Profound, and HubSpot's free grader. The user explicitly called it out: *"give them something that helps them compete and maybe use information that helps them enhance things at weak points in competitors within the same area."*

The current product audits **one business at a time, in isolation.** A small business owner doesn't care about a score in absolute terms — they care about beating the place across the street.

### 3.1 — Competitor benchmarking (the headline feature)

For each business, run the same audit pipeline against the **top 3 competitors in the same category and city** (which we already get from SerpApi's `local_results`!). Then show:

```
You vs. your top 3 competitors in Milton:

                    YOU      TopRanked     Mid       Bottom
   AEO score        58       82            65        42
   GBP                23       25            22        15
   Reviews            8       22            14         4
   Website            14      18            16         8
   Local Search       5       15            8          5
   AI Citation        8       10            5          10
```

**Marginal cost:** 3× more audits per month per customer. At $0.07/audit and 4 audits/customer/month, that's $0.84/customer/month — still well within Starter-tier margin.

**Marginal value:** Massive. This is the table the owner shares with their team in a Monday meeting.

### 3.2 — Competitor weak-point mining (the killer feature)

Once we're auditing competitors, we already have their:
- Star rating
- Review count
- Most recent review date
- Whether they have a website with schema
- Whether they're in the AI Overview / Perplexity citation graph
- The actual review snippets (via SerpApi `google_maps_reviews`)

We can run sentiment analysis on competitor reviews (Claude haiku, cheap) and surface opportunities like:

> **"3 of your top competitors have rating ≤ 4.2. Customer complaint themes: long wait times (mentioned 14 times), parking (mentioned 9 times), pricing (mentioned 7 times).
> Recommendation: emphasize 'no wait, on-time guarantee' and 'free parking' in your business description and Google Posts."**

This is a **differentiator no current SMB tool has.** Otterly does AI mention monitoring; nobody is mining the competitor reviews to surface "what to attack." This is what marketing agencies charge $2k/month to do manually.

### 3.3 — Local citation gap analysis

We already check whether the user is in `local_results`, `organic_results`, knowledge graph. Same query against competitors tells us **which directories the competitor is on that we are not** — Yelp, Yellow Pages, BBB, industry directories. Each missing directory is a concrete to-do.

### 3.4 — Real-time competitive alerts

> "Your top competitor 'Smith & Co' just got 12 new reviews this week (up from 0 the previous week). Their score moved from 65 to 72."

Triggered by the monthly auto-audit job; same email infrastructure already wired for score-change alerts. Possibly upgraded to weekly cadence for Pro tier.

---

## Part 4 — Product moat features

These don't win on day one but compound over time.

### 4.1 — Multi-location support
Today the data model is one business per user. Many of the most desirable customers (dental groups, fitness chains, multi-location restaurants) need 2–10 audits/month. The schema supports it (`businesses` is its own table); the dashboard does not. Half-week of work.

### 4.2 — White-label / agency tier
Marketing agencies will pay $300+/mo for an agency dashboard managing 20+ client audits. Add a `agency_id` column to `businesses`, a "managed by" view, and a custom-branded report PDF. Massive ARPU multiplier.

### 4.3 — Reporting (PDF / shareable link)
Every audit becomes a shareable URL or downloadable PDF the owner sends to their boss/team/marketing agency. Distribution channel + soft-virality.

### 4.4 — Schema generator UI (with copy-paste buttons)
We already generate the JSON-LD schema. Today it's text in the Content tab. Add a one-click "copy as `<script>` tag" + a "test in Google Rich Results Test" button. Reduces friction on the single highest-impact recommendation we give.

### 4.5 — `extruct` library upgrade
Replace substring schema matching with real JSON-LD parsing. Modest accuracy improvement, eliminates an entire class of false positives, and lets us validate schema correctness (not just presence). Sprint F10 already.

---

## Part 5 — Adjacent products that share data

We've built the audit pipeline. The same data powers obvious adjacent products:

### 5.1 — VSO (Voice Search Optimization)
Voice queries ("Hey Google, find a clinic near me") use the **same** signals as AEO: GBP completeness, reviews, FAQ schema. Add a "Voice search readiness" badge to the score card — same data, second product, no extra API calls.

### 5.2 — GEO (Generative Engine Optimization) for ChatGPT, Bing Copilot
We currently check Perplexity + Google AI Overview. Add ChatGPT (via the OpenAI Search API once GA), Bing Copilot. Each new engine = one more data point + one more sales bullet.

### 5.3 — Conversion-readiness
After we get them ranked in AI search, the next question is: **does their website convert?** Page-load time, mobile-friendliness, contact-form presence. All checkable with `httpx` + a Lighthouse-style scorer. Natural upsell to Pro tier.

### 5.4 — Phase 3: Reviews auto-post (already on roadmap)
Resumes when Google API is approved (~July 2026). All scaffolding (`reviews` schema, AI response generation) already built. Drops in.

---

## Part 6 — Recommended ordering (proposed)

If we ship one thing every two weeks, this is the order I'd ship them:

| Sprint | Theme | Items |
|---|---|---|
| **F8** (current) | Reliability | ✅ Content nav, ✅ Score history chart, ✅ Monthly cron, ✅ Score-change alerts |
| **F9** (next) | Production launch | All of Part 1: Dockerfile, Resend domain, vercel.json, rate limit, privacy/terms, Sentry, FR translations |
| **F10** | Trust + Marketing | Methodology page, "why this score" drawer, public free grader, 3 case studies, sample PDF |
| **F11** | **Competitor benchmarking (3.1 + 3.3)** | The big one. Audits top 3 competitors per business. |
| **F12** | **Competitor weak-point mining (3.2)** | Sentiment + complaint themes. The killer feature. |
| **F13** | Action tracking + weekly digest | Closes the engagement loop. |
| **F14** | Multi-location + agency tier | Opens the high-ARPU customer segment. |

After F14 we have a moat: nobody else combines Phase 1 audit + competitor intel + multi-location + agency dashboard at the SMB price point.

---

## Part 7 — What we are deliberately not building (for now)

- **Full SEO suite** — Ahrefs / SEMrush territory. Don't compete; integrate later.
- **AI chatbot for end customers of the business** — adjacent but a different product.
- **Social media management** — done well by Buffer/Hootsuite.
- **Booking/scheduling** — Phase 2 has this on the roadmap; not now.
- **Reviews auto-respond** — Phase 3, blocked on Google API approval.

Discipline matters. Adding any of these in Phase 1 dilutes the trust pitch ("we do AEO and we do it well").

---

## Summary — three things to remember

1. **The Phase 1 product is real.** The audit pipeline, scoring, recommendations, content generation, monthly cron, and score alerts are all working. We are 3–5 days of plumbing away from being able to invoice a customer.

2. **Competitor benchmarking + competitor weak-point mining is the wedge.** Every other SMB-AEO tool audits one business in isolation. We can leapfrog by showing the owner "here is what your competitors are doing wrong, and here is exactly how to attack them" — using data we are already collecting.

3. **Trust is built by showing your work.** Methodology page, raw-data drawer on every score, score-change diffs, downloadable PDFs, score guarantee. SMB owners have been burned before. Be ostentatiously transparent.

If we ship Part 1 (production blockers), Part 2.1 (show your work), and Part 3 (competitor intel) — in that order — we have a defensible product against every current SMB-AEO tool in the market.