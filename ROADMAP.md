# LeapOne — Development Roadmap

## How to use this file
- **Start every session:** paste this into Claude — "Check ROADMAP.md and tell me what's next"
- **End every session:** ask Claude to update this file with what was completed
- This is the single source of truth for progress. The other docs describe *decisions*; this tracks *done vs. not done*

Last updated: 2026-04-17

---

## ✅ Completed

### Infrastructure & Setup
- [x] Monorepo structure (`apps/web`, `apps/api`, `supabase/`, `docs/`)
- [x] Next.js 15 with App Router, Tailwind CSS
- [x] Supabase project created and connected
- [x] `next-intl` EN/FR translations — shipped early (was planned Phase 3, done in Phase 1)
- [x] Landing page built (`apps/landing/index.html`) — hero, features, how-it-works, waitlist CTA
- [x] Landing page deployed to **Vercel** — GitHub repo connected, auto-deploys on every push to main
- [x] DNS configured: A record (`@` → `216.198.79.1`), CNAME (`www` → `cname.vercel-dns.com`)
- [x] leapone.ca verified as authorized domain in Google Cloud Console
- [x] leapone.ca added in Vercel dashboard — Valid Configuration, set as Production. Vercel subdomain redirects 307 → leapone.ca
- [ ] Deploy Next.js app (`apps/web`) to Vercel — currently only landing page is deployed

### Authentication
- [x] Email/password sign up (with email confirmation)
- [x] Email/password sign in
- [x] Google OAuth — configured in Supabase, tested and working
- [x] Auth callback route (`/[locale]/auth/callback`) — PKCE flow, cookie handling
- [x] `profiles` table + trigger (auto-creates row on sign up, handles both Google OAuth and email)
- [x] Verify email page
- [x] Auth error banner (handles `otp_expired` and other hash errors)
- [x] Form validations: terms, password strength, duplicate email detection

### Dashboard Shell
- [x] Dashboard layout with auth guard (redirects to login if no session)
- [x] Desktop: centered container card on grey background (matches login/signup style)
- [x] Left sidebar: white, logo + business card + nav items + indigo active states
- [x] Mobile bottom nav: 4 tabs (Chat / Reviews / Bookings / Guide)
- [x] User menu: avatar top-right, dropdown with sign out
- [x] EN/FR switcher: always visible in header top-right (not buried in menu)
- [x] Chat home page: AI greeting + action cards (Reviews, Bookings) + chat input
- [x] Right stats panel (desktop): avg rating, responded count, appointments, quick actions
- [x] All dashboard text translated in EN and FR

---

## 🔄 Current Focus — Auth Completion

### Forgot/Reset Password
- [ ] `/auth/reset-callback` route handler (exchanges code, redirects to reset-password page)
- [ ] Forgot password page (`/[locale]/(auth)/forgot-password`)
- [ ] `ForgotPasswordForm` component (email input → Supabase resetPasswordForEmail)
- [ ] Reset password page (`/[locale]/(auth)/reset-password`)
- [ ] `ResetPasswordForm` component (new password + confirm → supabase.auth.updateUser)
- [ ] Wire "Forgot password?" link in LoginForm to forgot-password page
- [ ] EN/FR translations for both pages

### Profile Page
- [ ] Profile page (`/[locale]/dashboard/profile`)
- [ ] Update full name
- [ ] Update avatar (Phase 1: initials only, no upload yet)
- [ ] Add profile link to UserMenu dropdown
- [ ] EN/FR translations

---

## 📋 Next Up — Onboarding (REQUIRED before real users)

> ⚠️ Critical gap: new users sign up and land on a dashboard with fake hardcoded data.
> They have no entry in the `businesses` table. Onboarding must run before the dashboard.

- [ ] Create `businesses` table migration in Supabase (schema already designed in `docs/database-schema.md`)
- [ ] Post-signup redirect logic: if no business → onboarding, if business exists → dashboard
- [ ] Onboarding Step 1: Business info (name, city, type chips, employee range)
- [ ] Onboarding Step 2: Connect Google Business Profile (OAuth button + permissions list)
- [ ] Onboarding Step 3: Syncing spinner + progress
- [ ] Onboarding Step 4: Success → go to dashboard
- [ ] Desktop layout: left stepper panel (indigo) + right content (see `docs/ui-decisions.md`)

---

## 📋 Phase 1 Remaining — AI Review Responder

### Google Business Profile API
- [x] **Applied for OAuth app verification** — submitted, waiting for Google approval (1–4 weeks)
- [x] OAuth consent screen configured in Google Cloud Console
- [ ] Approval received from Google ← waiting
- [ ] Approval received from Google for OAuth consent screen ← waiting
- [ ] **`mybusinessreviews` API** — restricted API, intentionally not in public Library. Only appears after Google grants project access. Application submitted — waiting for approval.
- [ ] `mybusinessaccountmanagement` API enabled but quota value = 0 — needs quota allocated
- [ ] Add Business Profile API scopes once access confirmed
- [ ] Sync reviews from Google API → `reviews` table
- [ ] Store tokens in Supabase Vault (`review_connections` table)

### FastAPI Backend
- [ ] Set up `apps/api/` FastAPI project
- [ ] AI abstraction layer (`ai_engine.generate(prompt, context)`)
- [ ] OpenAI GPT-4o-mini integration
- [ ] Review response generation endpoint
- [ ] Post approved response back to Google

### Reviews Feature (Frontend)
- [ ] Reviews tab page (list view with filter tabs)
- [ ] Review detail panel (AI draft + edit + approve/discard)
- [ ] Replace hardcoded review data with real Supabase queries

### Payments & Infrastructure
- [ ] Stripe integration (CAD, recurring billing, trial period)
- [ ] Deploy frontend to Vercel
- [ ] Deploy FastAPI to Railway
- [ ] Resend email setup (transactional emails)

---

## 🔮 Phase 2 — AI Booking Assistant (not started)
Weeks 7–12 in original plan. Requires WhatsApp Business API (apply by Week 3–4).

## 🔮 Phase 3 — Ontario Startup Guide (not started)
Weeks 13–18 in original plan.

---

## ⚠️ Blockers & Important Notes

| Item | Status | Action needed |
|---|---|---|
| Google Business Profile API | ⏳ Submitted, awaiting approval | No action needed — just wait |
| WhatsApp Business API | Not applied | Apply by Week 3–4 |
| `businesses` table | Not created in Supabase | Run migration before building onboarding |
| Supabase email rate limit | Free tier ~3–4 emails/hr | Use real email accounts, not throwaway accounts for testing |
| FastAPI backend | Not started | Needed for AI features |

---

## 🔑 External Services Status

| Service | Status | Notes |
|---|---|---|
| Supabase | ✅ Active | Free tier, leapone project |
| Google Cloud Console | ✅ Project created | leapone project |
| Google OAuth (login) | ✅ Working | User sign in only |
| Google Business Profile API | ⏳ Applied, waiting | Submitted — approval 1–4 weeks |
| Vercel (landing page) | ✅ Live at leapone.ca | DNS configured, domain verified |
| Stripe | ❌ Not started | Needed before first paying customer |
| Vercel | ❌ Not deployed | Frontend deployment pending |
| Railway | ❌ Not started | FastAPI backend not built yet |
| Resend | ❌ Not started | Transactional email pending |

---

## 📝 Decisions Made That Differ From Original Plan

| Decision | Original Plan | What We Did | Why |
|---|---|---|---|
| EN/FR translations | Phase 3 | Done in Phase 1 | Canadian market — French users need it from day one |
| Dashboard layout | Full-screen | Centered card (like login) | Consistent design, more professional feel |
| Sidebar style | Dark indigo gradient | White with indigo accents | Better for daily-use working environment |
| EN/FR in UI | Buried in menu | Always visible in header | Bilingual app — must be discoverable |
| History/Refresh buttons | In mockup | Removed | Non-functional UI is worse than no UI — add when feature is built |

---

## 🗄️ Database Migration Status

| Migration | File | Status |
|---|---|---|
| profiles table + trigger | (run manually in SQL editor) | ✅ Applied |
| businesses table | `supabase/migrations/001_shared_tables.sql` | ❌ Not yet applied |
| subscriptions, conversations, notifications | same file | ❌ Not yet applied |
| review_connections, reviews, review_responses | `supabase/migrations/002_phase1_reviews.sql` | ❌ Not yet applied |
