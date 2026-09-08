# GlowDesk — AI Salon & Spa Booking Platform

A production-grade SaaS for salons/spas: a polished public site, client auth,
a token-minimized text + voice booking assistant (Groq primary / Gemini
fallback LLM router with rule-based slot filling and pgvector-backed RAG for
FAQs), a scikit-learn no-show risk model driving smart reminder timing, and
an owner-facing analytics dashboard. Built entirely on free/open-source
components — see [`salon-booking-saas-dev-plan.md`](salon-booking-saas-dev-plan.md)
for the full architecture and phased build plan.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 + pgvector, Redis, Celery
- **Frontend:** React 18 + TypeScript + Vite, Tailwind CSS, TanStack Query, Zustand, Recharts
- **AI:** Groq (`openai/gpt-oss-20b`) primary LLM, Gemini Flash/Flash-Lite fallback, `BAAI/bge-small-en-v1.5` embeddings, `faster-whisper` (STT), OpenVoice V2 (TTS)
- **ML:** scikit-learn no-show risk scoring

## Local development

1. Copy the environment template and fill in your free-tier API keys:

   ```bash
   cp .env.example .env
   ```

2. Bring up the full stack:

   ```bash
   docker compose up --build
   ```

   This starts Postgres (with pgvector), Redis, the FastAPI backend, Celery
   worker + beat, and the Vite dev server for the frontend.

3. Apply database migrations (from the `backend` container or locally with
   `DATABASE_URL` pointed at the compose Postgres instance):

   ```bash
   cd backend
   alembic upgrade head
   ```

- Backend API: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

## Running tests

```bash
# Backend
cd backend && pip install -r requirements-dev.txt && pytest

# Frontend
cd frontend && npm install && npm run test
```

## Project status

Phase 0 (scaffolding) complete: monorepo layout, Docker Compose stack,
`pydantic-settings` config, initial Alembic migration for the core schema,
and CI (lint + type-check + test) on every push/PR. See the dev plan's
phased milestones (§14) for what's next.
