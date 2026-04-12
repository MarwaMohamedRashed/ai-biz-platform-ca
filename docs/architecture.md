# LeapOne — Architecture Decisions

## Stack Overview

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js 16.1 + Tailwind CSS | App Router, RSC, PWA support, Vercel free tier |
| Backend | Python FastAPI | Async, fast, type-safe, native AI library support |
| Database | Supabase (PostgreSQL + Auth + Vault + RLS) | Free tier, built-in auth, row-level security |
| AI (primary) | GPT-4o-mini | Low cost, fast, good enough for review responses |
| AI (Phase 2 SMS) | Gemini 1.5 Flash | Higher volume SMS needs even lower cost per token |
| Auth | Supabase Auth (Google OAuth + email/password) | Google = primary, email = fallback |
| Payments | Stripe (CAD) | Supports both recurring and one-time payments |
| Email | Resend | Free tier, developer-friendly API |
| SMS / WhatsApp | Twilio | Standard, CASL-ready, Phase 2 only |
| Monitoring | Sentry | Free tier, works with both Next.js and FastAPI |
| Hosting (frontend) | Vercel | Free tier, instant deploys from GitHub |
| Hosting (backend) | Railway | $5/mo, easy Python deployment |
| Domain | leapone.ca | Registered — confirms CA market positioning |

## Monorepo Structure

```
ai-biz-platform-ca/
├── apps/
│   ├── web/          ← Next.js frontend
│   └── api/          ← FastAPI backend
├── supabase/
│   └── migrations/   ← SQL run in order in Supabase SQL Editor
├── docs/
│   ├── design-previews/  ← HTML mockups for all screens
│   ├── requirements.md
│   ├── ui-decisions.md
│   ├── architecture.md   ← this file
│   └── database-schema.md
└── README.md
```

All three products (Review Responder, Booking Assistant, Startup Guide) live in the same repo and share the same database, auth, and infrastructure.

## Multi-Tenancy Model

**Chosen: Row-Level Security (RLS) — NOT schema-per-tenant.**

- Each table has a `business_id` column
- Supabase RLS policies automatically filter every query to the logged-in user's data
- No schema creation needed per customer; scales to thousands of tenants
- Previous Sales AI project used schema-per-tenant — that pattern is NOT appropriate here (higher admin overhead, harder to query across tenants, not native to Supabase)

## AI Abstraction Layer

All products call one function — never the AI SDK directly:

```python
# Every product calls this — never openai.ChatCompletion.create() directly
response = await ai_engine.generate(prompt, context, model="gpt-4o-mini")
```

This lets us swap AI providers (OpenAI → Anthropic → Gemini) without touching business logic. Cost and quality decisions happen in one place.

## OAuth Token Security

Google OAuth tokens are stored in **Supabase Vault**, not as plain database columns.

- `review_connections` table stores a UUID reference to the vault secret
- To read the token: query `vault.decrypted_secrets` with the UUID
- Tokens are encrypted at rest; even a DB dump does not expose them

## User and Business Model

- One Supabase Auth user = one `profiles` row (auto-created by trigger)
- One user can own one business in Phase 1 (enforced by unique index)
- `business_members` table exists for Phase 2 team expansion — no migration needed later
- Business title (Owner, Manager, etc.) lives in `business_members.title`, not in `profiles`

## Payment Model

Stripe is configured to support both:
- **Recurring** (Review Responder $29–49/mo, Booking Assistant $39–79/mo)
- **One-time** (Startup Guide $49 flat)

The `subscriptions` table uses `stripe_id` for either a Stripe Subscription ID or a Payment Intent ID.

## Key External APIs

| API | When | Blocker |
|---|---|---|
| Google Business Profile API | Phase 1 | Apply for OAuth verification NOW — approval takes 1–4 weeks |
| Google Places API | Phase 1 (benchmarks) | Standard key, no approval needed |
| WhatsApp Business API | Phase 2 | Apply by Week 3–4 — Facebook Business Manager verification |

## i18n and Theme Strategy

- Build with CSS variables from day one (dark mode: swap variable values)
- Build with i18n-ready string files from day one (French: Phase 3)
- Do NOT hardcode colors or strings in components

## Infrastructure Cost at Launch

| Service | Monthly Cost |
|---|---|
| Railway (FastAPI) | $5 |
| Supabase | $0 (free tier) |
| Vercel | $0 (free tier) |
| AI (GPT-4o-mini) | ~$5–15 |
| Resend | $0 (free tier) |
| **Total** | **~$10–20/mo** |

Scales to ~$40–65/mo at several hundred customers before needing paid tiers.

## Phase Roadmap

| Phase | Weeks | Product | Key Dependency |
|---|---|---|---|
| 1 | 1–6 | AI Review Responder | Google Business Profile API approval |
| 2 | 7–12 | AI Booking Assistant | WhatsApp Business API approval |
| 3 | 13–18 | Ontario Startup Guide | Family member C research complete |
