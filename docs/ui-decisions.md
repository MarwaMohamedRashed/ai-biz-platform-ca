# LeapOne — UI Design Decisions

## Design Philosophy
- **Chat-first** — AI greets user on open, proactively shows what needs attention
- **Reduce navigation** — AI executes tasks via conversation, tabs for detail views
- **Mobile-first** — business owners check on phone while busy
- **Obvious next action** — when app opens, user immediately knows what to do

## Navigation Model
- **Mobile** — Bottom tab bar (Chat / Reviews / Bookings / Guide)
- **Desktop** — Left sidebar navigation
- **Chat tab is home** — AI gives daily briefing with action cards on open
- **Tabs provide detail** — user can navigate to full list views or ask AI to search

## Opening State (AI Briefing)
When user opens app, AI greets with:
> "Good morning [Name]! Here's what needs your attention: 3 reviews waiting, 2 appointments today"

Followed by action cards inline in chat. User can tap card OR type/speak a command.

## Color Palette — Option A (Indigo + Orange)
```
Primary:    #4f46e5  (Indigo)
Accent:     #f97316  (Orange)
Background: #f8fafc  (Light gray-white)
Text:       #1e293b  (Dark slate)
```

## Typography
- **Font**: Inter (Google Fonts)
- **Weights used**: 400, 500, 600, 700, 800

## Logo — Option D
- L monogram in indigo square (rounded corners, rx=12)
- Orange spark dot (circle) at top-right of the L
- Wordmark: "Leap" (indigo) + "One" (orange) in Inter 800
- App icon: indigo square with white L + orange dot
- Works at all sizes: 80px (home screen), 48px (tab), 32px (favicon), 16px (browser tab)

## Screen Inventory

### Auth Screens (Mobile + Desktop)
- **Sign In** — Google button (primary) + email/password (secondary)
- **Sign Up** — Google button + name/email/password + terms (PIPEDA mention)
- **Password Reset** — email input + success state
- **Desktop** — split layout: left indigo panel (branding + features) + right white form

### Chat Home (Mobile + Desktop)
- **Mobile** — header + chat area + input bar (mic + text + camera) + bottom nav
- **Desktop** — left sidebar + chat area + right stats panel
- **3 states**: morning briefing / after user interaction / all-clear day
- Input bar: mic button (indigo) + text field + camera button (orange) + send button

### Reviews Tab (Mobile + Desktop)
- **Mobile list** — stats bar + filter tabs (All/Pending/Responded/Negative) + review list
- **Mobile detail** — review text + AI draft + edit area + approve/discard action bar
- **Desktop** — 3-panel: sidebar + review list + review detail inline
- Status badges: pending (amber) / draft ready (indigo) / responded (green) / negative (red)

### Onboarding Flow (Mobile + Desktop)
- **Step 1** — Business info (name, city, type chips, employee range)
- **Step 2** — Connect Google Business Profile (permissions list + OAuth button)
- **Step 3** — Syncing with spinner + progress items
- **Step 4** — Success with import summary + go to dashboard CTA
- **Desktop** — left stepper panel (indigo) showing step progress + right content panel

## Component Patterns
- **Action cards** in chat — colored border, title, badge, body text, action buttons
- **Negative reviews** — red left border
- **AI draft box** — indigo background (#eef2ff) with quality indicators
- **Status dots** in nav — orange dot for pending items
- **Progress bar** — indigo fill on gray track
- **Buttons** — indigo (primary), outline indigo (secondary), orange (accent action)
- **Border radius** — 12px cards, 20px buttons/pills, 10px inputs

## Responsive Rules
| Element | Mobile | Desktop |
|---|---|---|
| Navigation | Bottom tab bar | Left sidebar |
| Cards | Full width, stacked | Side by side |
| Auth | Full screen | Split panel |
| Review detail | Separate screen | Right panel inline |
| Stats | Compact bar | Right panel |
| Onboarding | Full screen steps | Left stepper + right content |

## Future Decisions (Deferred)
- Dark mode toggle (build with CSS variables from day one)
- French language toggle (build with i18n from day one)
- Voice input (push-to-talk, like existing Sales AI)
- Camera/document scan
- PWA install prompt
- Phase 2 Bookings tab design
- Phase 3 Startup Guide tab design
