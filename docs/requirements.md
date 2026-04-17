# LeapOne — Requirements

## Platform Vision
AI-powered tools for Canadian small businesses — speed, customer retention, accuracy, cost efficiency.
All through conversational interfaces that replace complex forms and dashboards.

## Core Principles
- Chat-first UI — AI executes tasks, reduces navigation
- Mobile-first, works on desktop too
- Light mode default, dark mode toggle later
- French language support — shipped in Phase 1 (was planned Phase 3; Canadian market required it earlier)
- Cost-efficient — $40–65/month infrastructure at launch
- AI provider abstraction layer — swap models without rewriting business logic

## Three Products

| | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Product** | AI Review Responder | AI Booking Assistant | Ontario Startup Guide |
| **Target** | Any local business with Google reviews | Service businesses (salons, tutors, cleaners) | Aspiring entrepreneurs in Ontario |
| **Pricing** | $29–49/month | $39–79/month | $49 one-time or $19/month |
| **Revenue target** | $400–800 MRR by month 2 | $1,500–3,000 MRR by month 4 | $2,500–5,000 MRR by month 6 |
| **Build time** | Weeks 1–6 | Weeks 7–12 | Weeks 13–18 |

## Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| Frontend | Next.js 16.1 + Tailwind CSS | $0 (Vercel free) |
| Backend | Python FastAPI | $5/mo (Railway) |
| Database | Supabase (PostgreSQL + RLS) | $0 (free tier) |
| AI | GPT-4o-mini (primary), Gemini 1.5 Flash (Phase 2 SMS) | ~$5–15/mo |
| Auth | Supabase Auth (email + Google OAuth) | $0 |
| Payments | Stripe (CAD) | 2.9% + 30¢/txn |
| Email | Resend | $0 (free tier) |
| SMS/WhatsApp | Twilio | $0 until Phase 2 |
| Monitoring | Sentry | $0 (free tier) |
| Domain | leapone.ca | ~$16.40/yr |

## Key Architecture Decisions

- **Monorepo** — all products in one GitHub repo (ai-biz-platform-ca)
- **Multi-tenancy** — Row-Level Security (RLS), NOT schema-per-tenant
- **One user → many businesses** — owner can manage multiple business profiles
- **Team members** — deferred to Phase 2 (business_members table)
- **Google Sign-in** — primary auth method + email/password fallback
- **AI abstraction** — all products call `ai_engine.generate(prompt, context)` never SDK directly
- **Token storage** — Google OAuth tokens stored in Supabase Vault (not plain columns)
- **Payment types** — supports both recurring and one-time payments from day one

## Google Business Profile API
- Must apply for OAuth verification BEFORE Week 2
- Requires live Privacy Policy URL (deploy landing page first)
- Approval takes 1–4 weeks — start immediately

## WhatsApp Business API (Phase 2)
- Requires Facebook Business Manager verification
- Submit application by Week 3–4 (not Week 8 as original plan states)

## Legal & Compliance
- PIPEDA compliance required — Privacy Policy before launch
- CASL compliance for SMS/email opt-in (Phase 2)
- Terms of Service before first paying customer
- Market benchmarks use public Google Places data only (no customer data cross-comparison)

## Family Team Roles
| Role | Responsibilities |
|---|---|
| Marwa (founder/engineer) | FastAPI backend, AI integration, DB design, deployment |
| Family member A (frontend) | Next.js UI pages following established components |
| Family member B (sales) | Walk into local businesses, pitch free trials |
| Family member C (research) | Ontario regulations for Phase 3 requirements database |
