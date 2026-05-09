# LeapOne — Launch Prep Playbook (Early-Mid July 2026 — Bold Path)

**Date:** 2026-05-08 (last revised 2026-05-09)
**Time horizon:** 8–10 weeks to launch
**Target launch window:** early-to-mid July 2026
**Path chosen:** **Bold** — UX cleanup + verify-and-edit flow + AI execution coach all ship in v1

---

## Why we're slipping launch by 2-3 weeks

The original mid-June target shipped with what we have today: solid AEO
audit, content generator, recommendations. Good product, generic-enough
positioning that it could be confused with another AEO tool.

The bold path adds three things that **change the product's market
positioning from "another AEO tool" to "the AI coach for non-technical
Canadian SMB owners":**

1. **Content page UX cleanup** — progressive disclosure so a 55-year-old
   plumber isn't drowning in JSON-LD blocks
2. **Verify-and-edit flow on generated content** — AI proposes, owner
   edits or regenerates with notes, then verifies. Pattern we already
   use successfully on the reviews module. Prevents the
   "wrong-FAQ-pasted-on-website" failure mode that erodes trust.
3. **AI execution coach** — a chat assistant attached to each
   recommendation that walks the owner through actually doing it.
   "Claim your HomeStars profile" becomes a guided 5-minute
   conversation instead of a 200-word instruction the owner
   abandons.

Net effect on positioning: instead of "we audit your AI search
visibility" (technical-buyer language), the pitch becomes "we coach
Canadian small business owners through AI search optimization, even
if they're not technical." That's a stronger story and a real moat
that no US-built AEO tool replicates today.

The AI coach also unlocks the **Pro-tier upgrade pitch**: Starter is
"DIY AEO," Pro is "guided AEO with the coach." Today the $19→$49
upgrade is a thin sell (more audits per month). With the coach,
it's a clear value step.

---

## What ships in v1 (bold path)

### Phase A — Pre-launch product work (~10 days)
This is new. Was deferred / not in scope previously.

| Item | Effort | Why it's in v1 |
|---|---|---|
| Content page UX cleanup (progressive disclosure) | 1 day | Prevents drowning non-technical owners on first contact |
| Verify-and-edit flow for generated content (description, FAQ) | 2 days | Prevents wrong-content-pasted-on-website failure mode |
| AI execution coach (Pro-only) | 5 days | The headline differentiation; built on top of verify flow |
| Tier gating + Pro upgrade prompts | 0.5 days | Without gating, Starter customers consume the most expensive feature for free |
| Tests + docs | 1.5 days | Lock in regressions before launch |

### Phase B — Marketing foundation (was original Phase 0-7)
Same as original playbook, but the timeline starts after Phase A.

---

## The "eat your own dog food" principle (non-negotiable)

LeapOne sells AEO services. If on launch day a prospect googles "LeapOne"
or asks ChatGPT/Perplexity "is LeapOne a good AEO tool for Canadian small
businesses?" and gets nothing — **we lose the deal before we open our
mouth.** The single biggest pre-launch task is making LeapOne visible to
the same AI engines we promise to put our customers on.

**Hard truth about timelines:**
- **Perplexity + Google AI Overview**: live web search → can pick us up in
  days/weeks if we do it right
- **ChatGPT**: training-data based → won't see us at launch unless we're
  picked up in a future training run (6–12 months out). We already
  explain this honestly in the product. The pre-launch goal isn't
  ChatGPT citations — it's having a story when prospects ask why we're
  not cited yet (we are honest: "ChatGPT updates from training data; we
  optimise for the engines that update faster — Perplexity and Google
  AI Overview cite us by week 4 of launch")
- **Reddit + LinkedIn**: build authentically over weeks; don't fake it
- **Backlinks + press**: 4–8 week lead times; start now

**Honest reality check:** 6–8 weeks is enough to be visible on
Perplexity, Google AI Overview, the major Canadian SMB directories, and
LinkedIn. It is NOT enough to be the top result for "best AEO tool" or
to have ChatGPT recommend us. **Don't promise that.** Promise honest
visibility on the engines that update fastest, and a credible story for
the rest.

---

## Phase 0 — Pre-launch sanity (this week, 1 day total)

Before any marketing, lock these down. They're the foundation for
everything that follows.

| # | Task | Why | Effort |
|---|---|---|---|
| 0.1 | Create a LeapOne **Google Business Profile** | Without GBP, we can't be in the local pack. Even if we're online-only, list our city. | 30 min |
| 0.2 | Run our **own audit** on leapone.ca | Find our gaps before anyone else does. | 5 min |
| 0.3 | Generate our own schema via the Content tab and **paste it on leapone.ca** | Self-deploy LocalBusiness + FAQPage JSON-LD. Eat our own dog food, also forces us to fix any bugs. | 1 hour |
| 0.4 | Add `<link rel="canonical">` + Open Graph + Twitter Card meta on every public page | Already partly done — verify | 1 hour |
| 0.5 | Verify analytics: GA4 fires, Search Console verified, Bing Webmaster verified | Without these we're flying blind | 1 hour |
| 0.6 | Write a `robots.txt` that explicitly **welcomes** GPTBot, PerplexityBot, ClaudeBot, Google-Extended | Some sites block them by default — confirm we don't | 15 min |
| 0.7 | Submit `sitemap.xml` to Google + Bing | Free, takes 5 min | 15 min |

**End of Phase 0:** LeapOne is technically ready to be cited.

---

## Phase 1 — AEO foundation (Week 1–2, ~10 hours)

The same recommendations our product gives customers, applied to us.

### 1.1 — Claim every directory in our own DIRECTORY_DOMAINS list

Walk the list. Most are free. Each is 5–15 min:

**Universal (priority):**
- [ ] Google Business Profile (already in 0.1)
- [ ] Apple Business Connect — businessconnect.apple.com
- [ ] Bing Places — bingplaces.com
- [ ] Facebook Page — facebook.com/business
- [ ] LinkedIn Company Page — linkedin.com/company/setup/new
- [ ] Yelp Business — biz.yelp.com/signup (low-impact for SaaS but fast)
- [ ] BBB — bbb.org/get-listed (Canadian SMBs trust this hard)
- [ ] Foursquare for Business

**Canadian general:**
- [ ] Yellow Pages Canada — yellowpages.ca
- [ ] n49 — n49.com/biz/claim
- [ ] Cylex Canada — cylex-canada.ca
- [ ] Canada411 — 411.ca

**Vertical-relevant for a SaaS company:**
- [ ] LinkedIn Company Page (covered above — most important)
- [ ] G2 — g2.com (B2B SaaS reviews; takes ~2 weeks for approval)
- [ ] Capterra — capterra.com
- [ ] Software Advice — softwareadvice.com
- [ ] Product Hunt — submit on launch day specifically
- [ ] GetApp

**Honest note:** half of these will give us almost zero traffic. They
matter because **AI engines crawl them.** Yelp and BBB look weird for
SaaS but they show up in AI citation footprints.

### 1.2 — Get the LeapOne website Perplexity-ready

Perplexity favours: clear factual content, FAQ schema, About pages,
explicit pricing. We mostly have these. Audit:
- [ ] About page exists with concrete factual sentences (when, who, what,
  where) — Perplexity loves these
- [ ] Pricing page lists prices in plain text (not images)
- [ ] Methodology page is up (already shipping)
- [ ] FAQ on landing page wrapped in `FAQPage` JSON-LD (use our own
  generator!)

### 1.3 — Track our own visibility weekly

Run our own audit on leapone.ca every Monday. Watch for:
- AI Citations pillar climbing from 0 → 6 → 12 → 18 over 8 weeks
- Citation gap list shrinking
- Score trend in dashboard

This becomes our public case study at launch: "We built LeapOne. Here's
how we used it on ourselves."

---

## Phase 2 — Social media setup (Week 1, then daily upkeep)

### Priority order — set up in this exact sequence

1. **LinkedIn Company Page** — highest priority
   - B2B audience, our target buyer (SMB owners + agencies)
   - AI engines cite LinkedIn pages heavily
   - Founders post on LinkedIn; SMB owners scroll LinkedIn
2. **LinkedIn Personal Profile (Marwa)** — equal priority
   - Founder presence beats brand presence on LinkedIn
   - One personal post outperforms 5 company posts
3. **Facebook Page**
   - Canadian SMBs (especially trades, restaurants, salons) live here
   - Lower-fidelity but huge reach
4. **X / Twitter**
   - Tech audience, AEO/SEO conversations happen here
   - Lower priority for SMB customer acquisition; useful for thought
     leadership
5. **YouTube channel**
   - Set up the channel now even if first video ships in week 3
   - Channel age matters for the algorithm
6. **Reddit account (Marwa, personal)**
   - Build karma before launch by helping people in r/Toronto, r/ottawa,
     r/smallbusiness, r/Entrepreneur
   - **Never astroturf.** Mention LeapOne only when directly relevant
     and disclose ownership
7. **Instagram** — skip for now unless we have visual content; not
   high-leverage for B2B SaaS to Canadian SMBs
8. **TikTok** — skip; wrong audience

### Recommended channel branding (consistent across all):
- Handle: `@leapone_ca` or `@leaponeai` (check availability)
- Logo: existing LeapOne mark
- Bio template: "AEO platform for Canadian small businesses. Get cited
  by ChatGPT, Perplexity, and Google AI Overview. Bilingual EN/FR.
  leapone.ca"

---

## Phase 3 — Content cadence (Week 2 onwards, daily 30 min)

### The 30-minute daily rhythm (Monday–Friday)

This is the core. **30 minutes a day. Sustainable. Compounds.** Pick
one task per day from the rotation:

| Day | Focus | What you actually do (30 min) |
|---|---|---|
| Mon | LinkedIn post (founder voice) | Write a 200-word post on a tactical AEO insight you learned that week. Real, specific. Post from your personal account. Cross-post to company page. |
| Tue | Reddit engagement | Spend 30 min answering questions in r/smallbusiness, r/Entrepreneur, r/Toronto, r/EntrepreneurRideAlong, r/SEO. **Help, don't sell.** Drop LeapOne only when directly relevant + disclose. |
| Wed | Blog post on leapone.ca | Write a 600-1000 word article. Topic ideas in section 4 below. Schedule to publish Friday. |
| Thu | Outreach (1 hour, not 30 min — high leverage day) | Email 10 Canadian SMBs you'd like as case studies + 5 podcast hosts + 3 journalists who cover Canadian SMB topics. Templates in section 6. |
| Fri | Publish + amplify | Post Wednesday's blog. Tweet a key insight. Post on LinkedIn. Submit to relevant subreddits if genuinely useful. |

### Weekend (optional, lower-energy):
- Sat: 30 min on YouTube — record one short tip video (or batch-record 4 on a Saturday once a month)
- Sun: review what worked. Track in a spreadsheet: which posts got engagement, which didn't.

### Total: ~2.5 hours/weekday × 5 = ~12.5 hours/week of marketing
Realistic for a one-person founder. Stretchable to 5 hours/week if
needed (cut Tuesday + Saturday).

---

## Phase 4 — Content topics (45 article ideas, 6 weeks of posts)

Pick from this list. Each is 600–1000 words. Optimised for AEO citation
(answer-first, factual, schema-friendly).

### "Eat our own dog food" series (6 posts)
1. **"How we used LeapOne to put LeapOne on the AI search map (week-by-week)"** — public case study, ~1500 words, top-of-funnel gold
2. "What ChatGPT, Perplexity, and Google AI Overview actually say about us today"
3. "The 27 directories that matter for Canadian SMBs in 2026"
4. "Why we built our own deterministic schema generator (and stopped trusting LLMs to write JSON-LD)"
5. "Reddit citations after the Google deal: what changed in 2026 for Canadian SMBs"
6. "The 5 Schema.org subtypes that beat 'LocalBusiness' for trades, healthcare, restaurants, lawyers, and realtors"

### Vertical guides (10 posts — one per vertical we cover)
7. "AEO for Canadian dentists in 2026"
8. "AEO for Toronto plumbers"
9. "AEO for Ottawa restaurants"
10. "How Canadian lawyers get cited by ChatGPT"
11. "Real estate AEO: getting on Realtor.ca and into AI answers"
12. "Physiotherapy clinics + AEO: the RateMDs angle"
13. "AEO for Vancouver salons (and why beauty has fewer Canadian directories)"
14. "Auto repair + AEO: the CAA-Approved gap"
15. "AEO for Canadian accountants and bookkeepers"
16. "Marketing agencies + AEO: should you rank yourself or your clients?"

### "Honest" / contrarian (high-shareable)
17. "Why HubSpot's $50/mo AEO tool isn't built for Canadian SMBs"
18. "What Otterly gets right and what it gets wrong"
19. "The unsexy truth: ChatGPT won't cite your business for 6–12 months. Here's what to do instead."
20. "Why we didn't build an agency tier yet"
21. "Stop paying SEO consultants $2k/month. Here's what a $19 tool can actually do for you."

### Tactical / how-to (workhorses)
22. "Schema.org subtype lookup: what should your business actually use?"
23. "10 People-Also-Ask questions every Canadian dentist should answer on their FAQ page"
24. "What goes in your LinkedIn Company Page if you're a Canadian B2B SMB"
25. "Apple Business Connect step-by-step (with screenshots) for Canadian businesses"
26. "Bing Places + Microsoft Copilot: the under-claimed AI search surface"
27. "How to write a Reddit comment that doesn't get you banned (and might earn an AI citation)"
28. "The 5-minute postal-code fix that helps you appear in 'near me K1P' searches"
29. "Quebec inLanguage schema: how to signal bilingual to Google's Knowledge Graph"
30. "Free AI search visibility audit: what to actually look at"

### Comparisons (rank for "X vs Y" queries)
31. "LeapOne vs HubSpot AEO: which one for Canadian SMBs?"
32. "LeapOne vs Otterly.ai: AI search visibility for under $50/mo"
33. "LeapOne vs BrightLocal: AEO vs traditional local SEO"
34. "Otterly vs HubSpot AEO vs LeapOne: priced for SMBs?"

### Trend pieces (timely, ranks fast)
35. "What changed in Google AI Overview in 2026"
36. "Reddit becomes a top-3 AI citation source: what SMBs need to do"
37. "Why Schema.org's industry-specific subtypes matter more after Google's Feb 2026 update"

### French content (1 per week minimum)
38. "Référencement IA pour les PME canadiennes : par où commencer"
39. "Comment apparaître dans ChatGPT et Perplexity pour les entreprises québécoises"
40. "Les 5 répertoires canadiens essentiels pour votre visibilité IA"
41. "Schéma JSON-LD bilingue : un atout pour le marché québécois"

### Founder-perspective (LinkedIn-first)
42. "I'm building an AEO tool for Canadian SMBs. Here's what I'm learning. (week 1)"
43. "What 30 customer interviews taught me about Canadian small businesses and AI search"
44. "Why I'm building in Canada, for Canada"
45. "The honest competitive moat for a one-person SaaS in 2026"

---

## Phase 5 — YouTube strategy (Week 2–8, 1 video/week)

### Why YouTube
- AI engines cite YouTube transcripts heavily
- Google ranks YouTube videos in regular search
- Customers watch 2-min explainers before they read 1000-word blog posts
- Channel matures the more videos there are — start now even if rough

### Format constraints (sustainable)
- Length: **3–5 minutes** (sweet spot for explainers)
- Equipment: phone camera + free editing tool (CapCut / DaVinci Resolve)
- Production value: B+ at most. Don't perfectionism this. Substance > polish.

### First 8 video topics
1. "What is AEO? (3-minute explainer for SMBs)"
2. "How to claim your Apple Business Connect listing (Canadian walkthrough)"
3. "Schema.org for plumbers / electricians / HVAC contractors"
4. "I tested 5 AEO tools so you don't have to" — be honest about LeapOne
5. "Why Reddit matters for AI search in 2026"
6. "How to write FAQs ChatGPT will actually cite"
7. "Live demo: running an AEO audit on a real Canadian business"
8. "Bilingual schema markup for Quebec businesses"

### Distribution
- Embed videos in matching blog posts on leapone.ca → boosts both
- Cross-post on LinkedIn (native upload, NOT YouTube link — LinkedIn
  algorithm penalises external links)
- Cross-post on X
- 90-second highlight clips for Instagram + TikTok (test only — defer
  if too much work)

---

## Phase 6 — Outreach + backlinks (Week 2–8, ~3 hours/week)

### Backlinks: who we want
1. **Canadian SMB content sites** — BetaKit, BNN Bloomberg SMB section,
   Canadian Business, Maclean's small biz section
2. **AEO/SEO blogs that cover tools** — Search Engine Land, Search
   Engine Roundtable, Stackmatix, Rankability (run reviews of AEO tools
   regularly — we want to be in their next roundup)
3. **Canadian podcast hosts** — Canadian Founder Podcast, Build, Ship,
   Repeat, Code Story (Canadian guests welcome)
4. **Industry-specific Canadian publications** — Canadian Lawyer
   magazine, Canadian Pharmacy Magazine, Canadian Dentist Magazine —
   for vertical case studies

### Email template (the 1-email outreach that works)

```
Subject: Quick question — covering AEO tools for Canadian SMBs?

Hi <name>,

I'm Marwa, founder of LeapOne — an AEO platform built specifically
for Canadian small businesses (HomeStars/TrustedPros for trades,
RateMDs/Opencare for healthcare, Realtor.ca for realtors, FR/EN
bilingual support, etc.).

I noticed your <article/podcast/post> on <topic>. Most US-built AEO
tools at our price tier don't account for Canadian directories or
verticals — I think your audience would care about that.

Would a 15-min chat for a future article be useful? Happy to share
data: we run audits across ChatGPT, Perplexity, and Google AI Overview
in parallel, plus citation gap analysis on 28 directories.

If not now, I'll just send you our launch announcement when we go
live mid-June.

— Marwa
leapone.ca
```

### Press / journalists
- Find Canadian tech journalists who cover SaaS or SMB tooling
- Tools: BetaKit Slack, Canadian Tech Twitter, Press Hunt
- Pitch: founder story + Canadian-first angle + specific data

---

## Phase 7 — Launch week itself (early July 2026)

### T-7 days
- [ ] Final pre-launch audit on leapone.ca — score should be 70+
- [ ] All directory listings claimed
- [ ] Dashboard "before/after" screenshots prepared
- [ ] Press kit live at leapone.ca/press
- [ ] Video for launch announcement recorded

### T-1 day
- [ ] Schedule LinkedIn post (founder + company)
- [ ] Schedule X / Twitter thread
- [ ] Schedule Product Hunt submission (post Tuesday or Wednesday for
  best traffic — never Monday or Friday)
- [ ] Email 50 Canadian SMB owner contacts personally

### Launch day (Tuesday or Wednesday)
- 8 AM ET: Product Hunt go-live
- 9 AM ET: LinkedIn announcement post
- 9:30 AM ET: founder personal LinkedIn + X post
- 11 AM ET: relevant subreddits if genuinely useful (NOT spam)
- 1 PM ET: press email goes out to journalists
- 3 PM ET: send to email list
- 5 PM ET: post on relevant Slacks (Canadian SMB Slack, indie hackers)

### Launch week
- Daily: thank everyone who shares, engage with every comment within
  2 hours
- Day 3: write "what happened" recap blog post
- Day 5: send detailed metrics email to early users

---

## Honest "what won't work in 6–8 weeks"

Set expectations realistically.

| Expectation | Reality | What to do instead |
|---|---|---|
| ChatGPT recommends LeapOne | Won't happen — training data is from prior years | Optimise for Perplexity + Google AI Overview, which update faster |
| Page 1 of Google for "AEO tool Canada" | Months 6–12, not weeks | Rank for long-tail: "AEO tool for Canadian dentists", "Realtor.ca AI citation" |
| 1000+ Product Hunt upvotes | Realistic only with deep PH relationships | Aim for top 5 of the day — that's still meaningful traffic |
| Going viral on Twitter/LinkedIn | Don't plan for it | Plan for compounding: 50 posts → 5 break out |
| Being mentioned in Otterly's blog | Competitors won't cite us | Mentioned in third-party comparison roundups (Stackmatix, Rankability) — yes, achievable |
| Hiring help | Realistic only after revenue stabilises | Solo until $5k MRR, then first hire |

---

## Budget options (in increasing cost)

### Free (everything above can be done $0)
- Setup all directory listings
- Daily 30-min content rhythm
- Reddit engagement
- Email outreach (15 min/day)
- LinkedIn organic
- YouTube uploads
- **Time investment: 12–15 hours/week**

### ~$200/mo
- Everything above + tools to make it sustainable:
  - **Buffer or Later** ($15/mo) — schedule social posts in advance
  - **Resend** ($20/mo, already have for product) — newsletter
  - **Loom** (free–$15/mo) — quick video explainers
  - **CapCut** (free) — video editing
  - **Notion** (free) — content calendar
  - **Press Hunt** ($50/mo) — journalist contacts
  - **Maven 2-week SMB sales course** (~$80 one-time) — actually useful

### ~$500–1000/mo (later, post-launch)
- Paid ads (Google, LinkedIn) — only after product-market fit signal
- Sponsored posts in Canadian SMB newsletters
- Podcast sponsorships
- One-off PR firm engagement

**Don't spend on paid ads pre-launch.** You'll burn money against
strangers who don't know you yet. Save it for week 4 of launch when
you can target lookalikes of your first 100 users.

---

## The 9-week schedule — Bold path (Week 0 = 2026-05-09)

| Week | Theme | Top-3 priorities |
|---|---|---|
| **0** (this week) | Phase A kick-off + AEO foundation | Blog scaffold built · content-page UX cleanup shipped · Phase 0 directory claims (Apple, Bing, GBP at minimum) |
| **1** | Phase A continuation | Verify-and-edit flow shipped · AI execution coach backend started · all directory listings claimed |
| **2** | Phase A finish + content engine | AI coach complete + tier-gated · 5 blog posts drafted · LinkedIn Company Page + personal live |
| **3** | Marketing foundation | LinkedIn posting daily · 1 YouTube video published · Reddit account + 5 helpful comments |
| **4** | Authority | First 5 outreach emails to journalists · 2 podcast pitches · second YouTube video |
| **5** | Compounding | First Canadian SMB case study · weekly LinkedIn essay rhythm steady · third YouTube video |
| **6** | Pre-launch buzz | Email signup form on leapone.ca · launch announcement drafted · ProductHunt page prepared · press kit live |
| **7** | Soft launch | Friends + family launch · gather 10 testimonials · fix bugs surfaced |
| **8** | Public launch | Tuesday/Wednesday public launch · all channels coordinate · press email goes out |
| **9** | Post-launch | Thank everyone · write recap post · gather data for "first 30 days" piece |

**Launch target:** week 8, around 2026-07-07 to 2026-07-14 (early-to-mid
July). 2-3 weeks later than the original target, in exchange for the
AI coach moat that makes us materially harder to compete with.

---

## What to revisit when we resume

1. Does any of this conflict with how much time you actually have/week?
   12–15 hours is a lot for a solo founder.
2. Want me to draft the first 5 blog posts so they're ready?
3. Want me to draft the LinkedIn Company Page bio + first 10 posts?
4. Want me to write the email-outreach templates with Canadian
   journalist + podcaster lists?
5. Do you want a separate "self-audit dashboard" — a private leapone.ca
   page tracking our own AEO score weekly? Public-facing case study at
   launch.
6. Should we add our self-audit story to the landing page methodology
   section ("we used the tool on ourselves; here are our weekly scores")?

---

## Truth in one paragraph

The product is real. The 6–8 week window is enough to be honestly
visible — not famous. Compound the small daily actions (30 min/weekday)
and we'll have: a LinkedIn presence, 5 Canadian SMB case studies, our
own AEO score climbing weekly, citations on Perplexity and Google AI
Overview, 8 YouTube videos, 8 blog posts, all directory listings
claimed, and a credible press kit. That's a real launch. Anything more
is gravy. Anything less is sloppy.
