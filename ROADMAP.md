# LeapOne — Development Roadmap

## How to use this file
- **Start every session:** paste this into Claude — "Check ROADMAP.md and tell me what's next"
- **End every session:** ask Claude to update this file with what was completed
- This is the single source of truth for progress. The other docs describe *decisions*; this tracks *done vs. not done*

Last updated: 2026-04-19 (session 4)

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
- [x] User menu: avatar top-right, dropdown with sign out + profile link
- [x] EN/FR switcher: always visible in header top-right (not buried in menu)
- [x] Chat home page: AI greeting + action cards (Reviews, Bookings) + chat input
- [x] Right stats panel (desktop): avg rating, responded count, appointments, quick actions
- [x] All dashboard text translated in EN and FR

### Forgot/Reset Password
- [x] `/auth/reset-callback` — client-side page using `verifyOtp` (token_hash flow, works across browsers)
- [x] Forgot password page (`/[locale]/(auth)/forgot-password`)
- [x] `ForgotPasswordForm` component (email input → Supabase resetPasswordForEmail)
- [x] Reset password page (`/[locale]/(auth)/reset-password`)
- [x] `ResetPasswordForm` component (new password + confirm → supabase.auth.updateUser)
- [x] After password reset: signs out + redirects to login (security best practice)
- [x] Supabase email template updated to use `token_hash` flow (fixes cross-browser PKCE issue)
- [x] EN/FR translations for both pages

### Profile Page
- [x] Profile page (`/[locale]/dashboard/profile`)
- [x] Update full name (syncs to both `auth.users` metadata and `profiles` table)
- [x] Avatar: Google profile photo for OAuth users, initials fallback for email users
- [x] Email shown as read-only with hint
- [x] Profile link in UserMenu dropdown (translated EN/FR)
- [x] EN/FR translations

### Route Protection
- [x] `proxy.ts` — protects all `/[locale]/dashboard/**` routes (Next.js 16 uses proxy.ts not middleware.ts)
- [x] Unauthenticated requests redirected to `/[locale]/login` before page renders
- [x] Session tokens refreshed automatically on every dashboard request
- [x] next-intl locale routing combined in same proxy file

### Database
- [x] All shared tables applied: businesses, business_members, subscriptions, conversations, notifications
- [x] Multi-business support: unique index removed, RLS updated to use `business_members`, trigger auto-creates owner row on business insert
- [x] `country` column added to `businesses` (migration 004)
- [x] `onboarding_completed` boolean column added to `businesses` (migration 005, default false)

### Onboarding Flow
- [x] Post-signup redirect: if no business or `onboarding_completed = false` → onboarding; if complete → dashboard
- [x] Onboarding Step 1: Business info (name, city, type chips, country dropdown, province/state)
  - [x] "Other" type shows custom text input for business type
- [x] Onboarding Step 2: Connect Google Business Profile (permissions list, Skip option)
- [x] Onboarding Step 3: Syncing spinner (auto-advances after 2s)
- [x] Onboarding Step 4: Success → marks `onboarding_completed = true` → go to dashboard
- [x] Step resumption: if user stopped mid-onboarding (has business, `onboarding_completed = false`), resume at Step 2 on next login
- [x] Desktop layout: left indigo stepper panel + right content panel
- [x] EN/FR translations for all 4 steps

---

## 📋 Next Up — Phase 1 Core Features

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
- [ ] Deploy Next.js app to Vercel
- [ ] Deploy FastAPI to Railway
- [ ] Resend email setup with leapone.ca domain (replaces Supabase free tier email)
- [ ] Supabase pre-launch checklist:
  - [ ] Add `https://leapone.ca/**` to Redirect URLs (keep `http://localhost:3001/**` too)
  - [ ] Change Site URL from `http://localhost:3001` to `https://leapone.ca`
  - [ ] Switch Supabase email to custom SMTP via Resend

---

## 🔒 Must-Resolve Before Go-Live — Subscription & Access Control

> These items were flagged as critical. None are built yet. Must all be resolved before real users are onboarded.

### Session Security
- [ ] Session timeout / inactivity limit — users should not stay logged in indefinitely
  - Option A: Supabase Auth Settings → set JWT expiry (access token) + refresh token duration (e.g. 8h access token, 30 day refresh) — zero code change, just a Supabase config
  - Option B: App-level idle timeout — after X minutes of inactivity, auto sign-out via JS timer
  - Recommendation: Option A first (quick, covers most cases), Option B later if tighter security is needed (e.g. for business-sensitive data)

### Trial & Subscription Enforcement
- [x] Subscription table schema complete — tracks full lifecycle: trial, first payment, billing periods, cancellation, payment failure
- [x] Columns: `stripe_customer_id`, `stripe_price_id`, `subscription_starts`, `current_period_start/end`, `cancel_at_period_end`, `canceled_at`, `past_due_since`
- [ ] Onboarding completion creates trial subscription record (`product=reviews`, `status=trialing`, `trial_ends=now+14days`)
- [ ] When trial period ends (14 days): block access to paid features, show upgrade prompt
- [ ] Prevent a user from starting a new 14-day trial if they have already used one (check by email or Stripe customer ID, not just user ID — covers account deletion + re-signup)
- [ ] Subscription cancellation flow: user can cancel from settings, access continues until end of billing period

### Payment Flow
- [ ] Decision needed: when does the payment screen appear?
  - Option A: At end of 14-day trial (access gates trigger → user is prompted)
  - Option B: User can proactively upgrade during trial (e.g. "Upgrade" button in sidebar)
  - Recommendation: both — proactive upgrade + hard gate at trial end
- [ ] Stripe Checkout session: what plan/price to show, CAD currency, trial already used flag
- [ ] Post-payment webhook: update `subscription_status` to `active`, set `billing_cycle_end`
- [ ] Payment failure handling: notify user, grace period before access cut

### Route Protection (Auth + Subscription)
- [ ] Middleware: protect ALL `/dashboard/**` routes — redirect unauthenticated users to `/login` immediately, before any page renders
- [ ] Subscription gate middleware or layout check: if `subscription_status = expired` → redirect to `/upgrade` page instead of dashboard
- [ ] The `/upgrade` page itself needs to be built (Stripe Checkout trigger)

---

## ⚖️ Legal & Compliance — Required Before Real Users

### User Agreement
- [ ] Terms of Service page — EN and FR versions
- [ ] Privacy Policy page — EN and FR versions
- [ ] User must check "I agree to Terms of Service and Privacy Policy" checkbox during signup
- [ ] Agreement version + timestamp stored in `profiles` table (so you have a record of what version they agreed to)
- [ ] Dedicated session to review and finalize legal language before go-live

### User Consent & Communication Preferences
- [ ] Consent to contact (email, SMS) captured during onboarding or signup — required under CASL (Canada's Anti-Spam Legislation)
- [ ] `contact_consent` column on `profiles` or separate `consent_log` table — stores: consent given (bool), channel (email/sms), timestamp, IP address
- [ ] Unsubscribe tracking — if a user unsubscribes from any communication, mark them so they are never contacted again
- [ ] Unsubscribe link in all outgoing emails (required by CASL)
- [ ] Admin view: show consent status per user so you can prove compliance if challenged
  > ⚠️ CASL is strict — fines up to $10M CAD for violations. Do not send marketing emails without express consent.

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
| Supabase email rate limit | Free tier ~3–4 emails/hr. **Pre-launch decision needed:** upgrade to Supabase Pro ($25/mo) OR set up custom SMTP via Resend with leapone.ca domain (recommended — keeps cost low, branded emails). Do not ship to real users on free tier email limits. |
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
| Onboarding province field | Dropdown (CA only) | Free text labeled "Province / State" | App is open to non-Canadian businesses |
| Onboarding country field | Not planned | Added as dropdown (default: Canada) | Can't assume all users are Canadian |

---

## 🗄️ Database Migration Status

| Migration | File | Status |
|---|---|---|
| profiles table + trigger | (run manually in SQL editor) | ✅ Applied |
| businesses, business_members, subscriptions, conversations, notifications | `supabase/migrations/001_shared_tables.sql` | ✅ Applied |
| review_connections, reviews, review_responses, review_insights, market_benchmarks | `supabase/migrations/002_phase1_reviews.sql` | ✅ Applied |
| Multi-business support — removed unique index, updated RLS to use business_members, added on_business_created trigger | `supabase/migrations/003_multi_business_support.sql` | ✅ Applied |
| Add `country` column to businesses | `supabase/migrations/004_add_country_to_businesses.sql` | ✅ Applied |
| Add `onboarding_completed` boolean to businesses | run manually in SQL editor | ✅ Applied |
| Subscription billing columns — `stripe_customer_id`, `stripe_price_id`, `subscription_starts`, `current_period_start`, `current_period_end`, `cancel_at_period_end`, `canceled_at`, `past_due_since` | run manually in SQL editor | ✅ Applied |
