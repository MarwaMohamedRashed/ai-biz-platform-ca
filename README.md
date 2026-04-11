# AI Business Platform — Canadian Small Businesses

> AI-powered tools that help Canadian small businesses save time, look professional, and grow.

**3 products. 1 shared platform. 6-month roadmap.**

| Product | Description | Phase | Pricing |
|---------|-------------|-------|---------|
| Review Responder | AI drafts Google review responses. Owner approves with one tap. | Phase 1 | $29–49/mo |
| Booking Assistant | AI handles SMS/WhatsApp appointment booking | Phase 2 | $39–79/mo |
| Startup Guide | Conversational compliance guide for Ontario entrepreneurs | Phase 3 | $49 one-time |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + Tailwind CSS → Vercel |
| Backend API | Python FastAPI → Railway (then GCP Cloud Run) |
| Database + Auth | Supabase (PostgreSQL) |
| AI Model | OpenAI GPT-4o-mini (primary) / Gemini 1.5 Flash (Phase 2 alternative) |
| Payments | Stripe (CAD) |
| Email | Resend |
| SMS / WhatsApp | Twilio (Phase 2 only) |

---

## Repository Structure

```
ai-biz-platform-ca/
├── apps/
│   └── web/                    # Next.js 14 frontend (all products)
│       ├── app/
│       │   ├── (auth)/         # Login, signup, password reset
│       │   ├── dashboard/      # Shared dashboard layout
│       │   ├── reviews/        # Phase 1: Review management UI
│       │   ├── bookings/       # Phase 2: Booking management UI
│       │   └── startup/        # Phase 3: Startup guide UI
│       └── components/
│           ├── shared/         # Buttons, cards, nav, chat widget
│           ├── reviews/
│           ├── bookings/
│           └── startup/
│
├── api/                        # Python FastAPI backend
│   ├── core/                   # Shared: auth, DB, AI engine, notifications
│   │   ├── ai_engine.py        # ⭐ AI provider abstraction layer
│   │   ├── database.py         # Supabase client
│   │   ├── auth.py             # JWT middleware
│   │   └── notifications.py   # Resend + Twilio
│   ├── reviews/                # Phase 1 routes + logic
│   ├── bookings/               # Phase 2 routes + logic
│   ├── startup/                # Phase 3 routes + logic
│   ├── main.py                 # FastAPI app entry point
│   └── requirements.txt
│
├── supabase/
│   ├── migrations/             # SQL migration files (run in order)
│   └── seed.sql                # Sample data for development
│
└── .github/
    └── workflows/
        ├── deploy-frontend.yml # Auto-deploy to Vercel on push
        └── deploy-backend.yml  # Auto-deploy to Railway on push
```

---

## Getting Started (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Supabase project (free at supabase.com)
- An OpenAI API key

### 1. Clone the repo
```bash
git clone https://github.com/MarwaMohamedRashed/ai-biz-platform-ca.git
cd ai-biz-platform-ca
```

### 2. Set up the backend
```bash
cd api
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Fill in your keys
uvicorn main:app --reload
```

API runs at: http://localhost:8000
Auto-generated docs: http://localhost:8000/docs

### 3. Set up the frontend
```bash
cd apps/web
npm install
cp .env.local.example .env.local  # Fill in your keys
npm run dev
```

Frontend runs at: http://localhost:3000

### 4. Set up the database
```bash
# Run migrations in order in your Supabase SQL editor
# supabase/migrations/001_shared_tables.sql
# supabase/migrations/002_phase1_reviews.sql
```

---

## Environment Variables

### Backend (api/.env)
```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
RESEND_API_KEY=re_...
AI_PROVIDER=openai                # Switch to "gemini" for Gemini Flash
ENVIRONMENT=development
```

### Frontend (apps/web/.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Build Phases

- **Phase 1 (Weeks 1–6):** Review Responder — target $400–800/month MRR
- **Phase 2 (Weeks 7–12):** Booking Assistant — target $1,500–3,000/month MRR
- **Phase 3 (Weeks 13–18):** Startup Guide — target $2,500–5,000/month MRR

---

## Development Notes

- **AI abstraction layer:** Never call OpenAI or Gemini SDK directly. Always use `api/core/ai_engine.py`. This lets you swap providers with one config change.
- **Learning-first approach:** Each task has a companion learning doc before implementation begins.
- **SQL migrations:** Number them sequentially (001_, 002_). Never edit a migration that has already run in production.

---

*Built by MarwaMohamedRashed — AI engineering learning project*
