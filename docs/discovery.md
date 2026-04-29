# LeapOne — Product Discovery Document
*Created: 2026-04-29 | Status: Active*

---

## Vision

**LeapOne is an AI agent platform for small businesses.**
It reduces the time owners spend on customer acquisition and online presence,
so they can focus on their actual work.

The platform is built in phases. Each phase is a standalone product that also
feeds the next. Customers acquired in Phase 1 are the natural buyers of Phase 2.

---

## Why We Are Delaying Reviews and Sales Agent

### Google Reviews Auto-Post — PAUSED until ~July 2026
- Google Business Profile API application was **denied on 2026-04-29**
- Rejection reason: *"A requestor's email should be an owner/manager of a listing
  that has been verified for 60+ days"*
- leapone.ca was added to Google Maps on April 12, 2026
- Earliest reapply: approximately late June / early July 2026
- All code is built and ready (OAuth flow, review draft queue, AI generation,
  approval UI). Will resume the day approval lands.

### Facebook/Instagram Reviews — WAITING (Meta App Review)
- Meta app created, permissions configured (pages_read_user_content,
  pages_manage_engagement, Instagram content management)
- Business verification started
- Waiting on Meta app review (estimated 3–7 business days)
- Will resume once approved — backend code is partially built

### AI Sales Agent — DELAYED to Phase 2
- The sales agent requires channel integrations (WhatsApp/Twilio, Gmail OAuth,
  Meta DMs) that add complexity and external dependencies
- Requires business owners to change how they receive leads — high adoption friction
- AI talking to real customers requires strong trust first
- Strategic decision: build customer base and trust with AEO (Phase 1) first,
  then upsell the sales agent to existing customers (Phase 2)
- Existing Conversation_Sales_AI_Agent repo
  (MarwaMohamedRashed/Conversation_Sales_AI_Agent) will be referenced heavily
  when Phase 2 begins

---

## Phase 1 — AEO (Answer Engine Optimization)

### What is AEO?
When someone asks ChatGPT, Perplexity, or Google AI Overview
*"best plumber in Toronto"* or *"top hair salons in Ottawa"* —
which businesses get mentioned? AEO is the practice of optimizing a business
to appear in those AI-generated answers.

Most small businesses have no idea whether they appear in AI search results
or how to improve their chances. Nobody is solving this for SMBs yet.

### The Problem We Solve
- Small business owners don't know if they appear in AI search (ChatGPT,
  Perplexity, Google AI Overview)
- They don't know what content AI search engines pull from
- Traditional SEO agencies don't cover AI search yet
- This is the new Google ranking — and SMBs are invisible in it

### What LeapOne AEO Does
1. **AI Presence Audit** — Queries ChatGPT, Perplexity, and Google AI Overview
   for the business's category + city. Shows the owner exactly where they
   appear and where they don't
2. **Score & Benchmarking** — Gives them an AI Visibility Score (0–100).
   Shows how they compare to local competitors
3. **Content Generator** — Generates optimized business descriptions, FAQ pages,
   and structured data (schema markup) that AI search engines favour
4. **Monthly Monitoring** — Tracks their score over time. Alerts when mentions
   change. Shows what improved and what dropped
5. **Actionable Recommendations** — Specific steps: *"Add your services list
   to your Google profile"*, *"Answer these 5 questions on your website"*

### Why This Works as Phase 1
| Factor | Detail |
|--------|--------|
| No API approvals needed | Zero external dependencies — ships immediately |
| Instant trial value | Business owner sees audit results in under 5 minutes |
| Low friction | Just enter business name, city, services — done |
| Recurring value | Monthly monitoring justifies subscription |
| Trust builder | Establishes LeapOne as the AI expert before selling the agent |

### Target Customer
Small businesses that rely on local discovery:
- Home services (contractors, HVAC, plumbers, electricians)
- Health & wellness (clinics, physiotherapists, massage therapists)
- Professional services (consultants, accountants, lawyers)
- Restaurants and cafes
- Salons and spas

Primarily Canadian at launch (Ottawa, Toronto, Vancouver, Calgary).
English and French support from day one.

### Revenue Model
- **Free trial:** Full audit once, score only on repeat visits
- **Starter $29/mo:** Monthly monitoring, basic recommendations, 1 location
- **Pro $59/mo:** Competitor tracking, content generator, 3 locations,
  priority alerts

### Success Metric for Phase 1 Trial
10 small businesses actively using monthly monitoring after 30 days.

---

## Phase 2 — AI Sales Agent

### What It Does
An AI agent that captures and qualifies leads from the channels where small
business leads actually arrive — WhatsApp, email, Facebook/Instagram DMs —
so the owner never loses a lead because they were too busy to respond.

### Core Loop
1. Lead contacts business via WhatsApp, email, or Facebook/Instagram DM
2. AI has a qualifying conversation — collects name, need, timeline, budget
3. Owner gets instant notification: *"New lead: Ahmed wants a kitchen reno
   quote, budget $20k, wants to start July"*
4. Owner sees full conversation in dashboard, AI has drafted a reply or quote
5. Owner approves and sends with one tap
6. AI follows up automatically if lead goes quiet after X days

### Why Phase 2 (Not Phase 1)
- Requires Twilio (WhatsApp), Gmail OAuth, Meta API — multiple dependencies
- Requires business owners to change how they receive leads (high friction)
- AI talking to real customers requires trust — earned through Phase 1
- Phase 1 AEO customers are the natural first buyers of Phase 2

### Channel Rollout
| Phase | Channel | Dependency |
|-------|---------|------------|
| 2a | WhatsApp via Twilio | Twilio handles Meta approval |
| 2b | Email (Gmail/Outlook OAuth) | Standard OAuth, no special approval |
| 2c | Facebook/Instagram DMs | Meta app review (already applied) |

### Existing Code to Reuse
- Conversation_Sales_AI_Agent repo: agent orchestration pattern, stage machine
  (Lead → Discovery → Quote), conversation/messages data model, JSON-based
  LLM action system
- LeapOne: auth, subscription model, Supabase, FastAPI structure, AI engine,
  business settings pattern

### Scaling Path
- **SMB ($49–99/mo):** Conversational, no setup, single user
- **Mid-market ($200–500/mo):** Team inbox, assign leads to staff, pipeline
  reporting, integrations (email, Slack, QuickBooks)

Mid-size businesses (10–50 employees) are underserved by Salesforce (too
expensive) and outgrowing HubSpot free. This is the expansion lane.

---

## Phase 3 — Reviews Auto-Post (Resume When Approved)

Once Google Business Profile API is approved (~July 2026) and Meta app review
clears, resume the review response product:
- Google Reviews: read → AI draft → owner approves → auto-post
- Facebook Reviews: same flow
- Instagram Comments: same flow
- Google Q&A: read questions → AI draft answer → owner approves → post

All backend code is already built. Resuming is a matter of wiring the
post endpoints and adding the Connect Google/Facebook buttons to settings.

---

## What We Already Have (Reusable Infrastructure)

| Asset | Status |
|-------|--------|
| leapone.ca domain + landing page | Live on Vercel ✅ |
| Next.js dashboard (auth, subscription, settings) | Built ✅ |
| FastAPI backend structure | Built ✅ |
| Supabase database + RLS | Built ✅ |
| AI engine (Claude, abstracted) | Built ✅ |
| Google Workspace (marwa.saleh@leapone.ca) | Active ✅ |
| Google Cloud Console (OAuth, APIs) | Configured ✅ |
| Meta developer app (LeapOne) | Created, pending review ✅ |
| Privacy policy + Terms of Service pages | Live ✅ |
| Subscription model (trial/pro) | Built ✅ |
| English + French i18n | Built ✅ |

---

## Open Questions (To Resolve Before Building Phase 1)

1. Which AI search engines to query in the audit? (ChatGPT API, Perplexity API,
   Google AI Overview — access and cost to confirm)
2. How to measure "AI search visibility" reliably and consistently?
3. Competitor comparison — how do we identify who their local competitors are?
4. Pricing validation — is $29/mo the right entry price for Canadian SMBs?
5. French-language AI search — how does visibility differ in French Quebec markets?