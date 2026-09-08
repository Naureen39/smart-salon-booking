# Salon/Spa Booking & No-Show Reduction Assistant — Master Development Plan

**Document purpose:** This is the single source of truth for a coding agent (or engineering team) to design, build, test, and ship this product end-to-end. Every phase below is meant to be executed sequentially, with each phase producing a working, testable increment. All technology named here is free / open-source / has a permanent free tier — no paid service is required to build or run the MVP.

---

## 1. Project Overview

**Product name (working title):** GlowDesk — AI Salon & Spa Booking Platform

**One-liner:** A production-grade SaaS web app for salons/spas that lets clients discover services, book appointments via a polished website, a text chatbot, or a natural-sounding voice agent — while an ML model quietly scores every booking for no-show risk and triggers personalized reminder timing, and an owner-facing analytics dashboard turns booking history into revenue-saving decisions.

**Core capabilities:**
1. Fortune-500-grade public marketing website (Home, Services/Menu, About, Gallery, Contact, Book Now).
2. Secure client authentication (signup/login) and profile management.
3. Conversational booking assistant — both **text chat** and **voice agent** — that can check availability, book/reschedule/cancel appointments, and answer FAQs, powered by a **hybrid LLM router** (Groq `openai/gpt-oss-20b` primary, Gemini Flash/Flash-Lite fallback) with aggressive token minimization.
4. Retrieval-Augmented FAQ answering using open-source embeddings + PostgreSQL `pgvector`, so most FAQ questions never need to hit an LLM at all.
5. No-show / churn risk prediction using scikit-learn, trained on a realistically simulated appointment dataset, driving smart, personalized reminder timing.
6. Reminder engine (email + optional WhatsApp/SMS webhook) scheduled by predicted risk, not a fixed offset.
7. Owner/staff analytics dashboard: bookings over time, no-show trends, revenue leakage estimate, at-risk client list, staff utilization, service popularity.
8. Full auth/authorization split between public clients and internal staff/admin roles, with production-grade security practices throughout.

---

## 2. Problem Statement

No-shows are one of the largest silent revenue leaks for appointment-based small businesses like salons and spas — industry estimates commonly put no-show rates at 10–20%+ of booked slots, each one representing lost chair-time that can never be resold. Existing tools (Calendly-style bookers, generic SMS reminder blasts) treat every client identically: same reminder cadence, same message, no memory of who actually shows up. They also don't reduce the *friction* of booking itself — clients still have to navigate rigid calendar UIs.

This project solves both problems together:
- **Friction:** A conversational (text + voice) assistant that understands natural requests ("Can I get a haircut and beard trim next Saturday afternoon?") and turns them into confirmed bookings in a few turns, using minimal LLM calls.
- **Leakage:** A predictive model that flags clients/slots most likely to no-show (first-time clients, Monday-morning slots, clients with a prior no-show, last-minute bookings, etc.) so the business can send earlier/more personal reminders, request deposits, or proactively overbook high-risk slots — decisions surfaced clearly on an analytics dashboard.

**Target users:**
- **Clients** — browse services, chat or talk to book/reschedule, get smart reminders.
- **Salon owner/staff (admin)** — manage services & staff calendars, view analytics, see risk-flagged upcoming appointments.

---

## 3. Success Metrics (what "done, production-grade" looks like)

- Booking flow (chat or voice) completes in ≤ 5 conversational turns for a straightforward request.
- Average LLM tokens consumed per completed booking flow < 1,500 tokens total (input+output), achieved via structured state machine + RAG + small-model routing (see §9.4).
- No-show prediction model AUC ≥ 0.75 on held-out simulated data.
- Dashboard loads key metrics (bookings, no-show rate, revenue at risk) in < 1s from a materialized/cached query.
- All secrets, passwords, and tokens handled per OWASP ASVS Level 2 baseline (see §8).
- Fully containerized (`docker-compose up` brings up the entire stack locally).
- CI pipeline (GitHub Actions, free for public/private repos within free minutes) runs lint + type-check + unit tests + build on every PR.

---

## 4. High-Level Architecture

```
                         ┌─────────────────────────────┐
                         │        React Frontend        │
                         │  Public site + Auth + Chat/  │
                         │  Voice widget + Admin SPA     │
                         └──────────────┬───────────────┘
                                        │ HTTPS / REST / WebSocket
                         ┌──────────────▼───────────────┐
                         │         FastAPI Backend       │
                         │  ┌─────────────────────────┐  │
                         │  │ Auth & RBAC (JWT)        │  │
                         │  │ Booking Engine (rules)   │  │
                         │  │ Conversation Orchestrator│  │
                         │  │  - Intent/slot state mgr │  │
                         │  │  - RAG retriever         │  │
                         │  │  - LLM Router (Groq/     │  │
                         │  │    Gemini failover)      │  │
                         │  │ STT service (faster-     │  │
                         │  │    whisper)               │  │
                         │  │ TTS service (voice clone) │  │
                         │  │ No-show ML scoring         │  │
                         │  │ Reminder scheduler (Celery)│ │
                         │  │ Analytics/reporting API   │  │
                         │  └─────────────────────────┘  │
                         └──────┬───────────┬────────────┘
                                │           │
              ┌─────────────────▼──┐   ┌────▼─────────────┐
              │ PostgreSQL 16 +     │   │ Redis (cache,     │
              │ pgvector extension  │   │ Celery broker,    │
              │ (bookings, clients, │   │ rate limiting,    │
              │  FAQ embeddings,    │   │ session store)    │
              │  audit log)         │   └───────────────────┘
              └─────────────────────┘
```

**Deployment target (free tiers only):**
- Frontend → static build hosted free on Vercel/Netlify/Cloudflare Pages free tier, or served by FastAPI as static files for fully self-hosted option.
- Backend → any free-tier VM/container host (Render free web service, Fly.io free allowance, or a self-hosted VPS/Oracle Cloud Always-Free instance) — plan is host-agnostic.
- Postgres → Supabase free tier (has `pgvector` built in) or self-hosted Postgres container.
- Redis → Upstash free tier or self-hosted Redis container.
- All ML/voice models run as open-source weights on the backend's own compute (CPU-friendly quantized models chosen deliberately — see §9).

---

## 5. Tech Stack (100% free / open-source)

| Layer | Technology | Why |
|---|---|---|
| Backend framework | **FastAPI** (Python 3.11+) | Async, typed, auto OpenAPI docs, ideal for streaming chat/voice |
| ORM / migrations | **SQLAlchemy 2.0** (async) + **Alembic** | Production-standard, typed models |
| Database | **PostgreSQL 16** + **pgvector** extension | Relational data + vector similarity search in one engine (no separate vector DB needed) |
| Cache / broker / sessions | **Redis** | Celery broker, response cache, RAG cache, rate-limit counters |
| Background jobs / scheduler | **Celery** + **Celery Beat** | Reminder scheduling, model retraining jobs, nightly analytics rollups |
| Auth | **OAuth2 Password + JWT (access + refresh)** via `python-jose` / `fastapi-users` or hand-rolled service, **passlib[bcrypt]** for hashing | Stateless, scalable, standard |
| Validation | **Pydantic v2** | Request/response schemas, settings management |
| ML (no-show prediction) | **scikit-learn**, **pandas**, **numpy** | Gradient boosting / logistic regression baseline, explainable |
| Synthetic dataset generation | **Faker** + custom generator script | Realistic appointment history with believable no-show patterns |
| Embeddings (FAQ RAG) | **`BAAI/bge-small-en-v1.5`** (384-dim, Apache 2.0/MIT-family license, via `sentence-transformers`) served locally via **Hugging Face `transformers`/`sentence-transformers`**, optionally behind **Text Embeddings Inference (TEI)** for throughput | Small, fast on CPU, excellent retrieval quality, fully open |
| Vector search | **pgvector** (`ivfflat` or `hnsw` index) inside the same Postgres instance | No extra infra; ACID-consistent with booking data |
| LLM #1 (primary, fast) | **Groq API — `openai/gpt-oss-20b`** (free tier: 30 RPM / 1,000 RPD / ~200K TPD) | Extremely low latency (≈1,000 tok/s), great for real-time voice/chat |
| LLM #2 (fallback) | **Google Gemini API — `gemini-2.5-flash` / `gemini-2.5-flash-lite`** free tier | Second free-tier budget to burst into once Groq's daily/rate cap is hit |
| LLM routing/orchestration | Custom **LLM Router** service (see §9.4) with circuit breaker + exponential backoff, provider-agnostic prompt templates | Keeps the app running across two independent free quotas |
| Speech-to-Text | **`faster-whisper`** (CTranslate2 port of OpenAI Whisper, `small`/`base` int8-quantized, MIT license) self-hosted on backend CPU | Free, open-source, no per-call cost, works well on CPU with int8 quantization |
| STT fallback (optional) | Groq-hosted **Whisper Large v3 Turbo** endpoint (free tier, very fast) | Optional low-latency path when server CPU is constrained; still free |
| Text-to-Speech (voice cloning) | **OpenVoice V2** (MIT license, zero-shot multi-lingual voice cloning + tone/emotion control) as primary; **Coqui XTTS-v2** as an optional higher-fidelity alternative for local/non-commercial evaluation | OpenVoice V2 is fully MIT-licensed (safe for a commercial SaaS), supports cloning a short reference clip of the salon's chosen "brand voice" |
| Frontend framework | **React 18 + TypeScript + Vite** | Modern, fast dev loop |
| Styling/UI | **Tailwind CSS** + **shadcn/ui** components | Rapid, consistent, professional design system |
| Charts (analytics dashboard) | **Recharts** | Clean, composable charts for admin dashboard |
| State/data fetching | **TanStack Query (React Query)** + **Zustand** (light client state) | Caching, retries, optimistic updates |
| Realtime chat/voice transport | **WebSocket** (native FastAPI `WebSocket`) | Streaming partial STT/LLM/TTS chunks to the browser |
| Audio capture/playback (browser) | **MediaRecorder API** + **Web Audio API** | No paid SDK needed |
| Containerization | **Docker + docker-compose** | Reproducible local + deployable stack |
| CI/CD | **GitHub Actions** (free minutes on public/private repos) | Lint, type-check, test, build, (optional) deploy |
| Testing | **pytest**, **httpx** (async test client), **pytest-asyncio**, **Vitest** + **React Testing Library** (frontend) | Full-stack automated testing |
| Observability | **structlog** (structured JSON logs) + **Prometheus client** + optional self-hosted **Grafana** | Free, self-hostable monitoring |
| Secrets/config | **pydantic-settings** + `.env` (never committed) | 12-factor config |

> **Note on paid-service alternatives:** A short list of paid services that could *upgrade* parts of this stack (better TTS quality, managed SMS, managed hosting, etc.) is provided separately in the chat response, **not** in this plan file — this plan intentionally uses only free/open-source components end-to-end.

---

## 6. Data Model (PostgreSQL + pgvector)

### 6.1 Core tables

```sql
-- Users (both clients and staff share this table, differentiated by role)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    hashed_password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('client','staff','admin')) DEFAULT 'client',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Salon locations (supports multi-branch from day one)
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    address TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC'
);

-- Staff profiles (linked to users with role='staff')
CREATE TABLE staff_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    location_id UUID REFERENCES locations(id),
    title TEXT,
    bio TEXT,
    working_hours JSONB  -- e.g. {"mon": ["09:00-17:00"], ...}
);

-- Services (the "menu")
CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,             -- Hair, Nails, Spa, Skincare, etc.
    duration_minutes INT NOT NULL,
    price_cents INT NOT NULL,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Appointments (the central booking record)
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES users(id),
    staff_id UUID REFERENCES staff_profiles(id),
    service_id UUID REFERENCES services(id),
    location_id UUID REFERENCES locations(id),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('booked','confirmed','completed','cancelled','no_show')) DEFAULT 'booked',
    booking_channel TEXT CHECK (booking_channel IN ('web','chat','voice','admin')),
    is_first_visit BOOLEAN DEFAULT FALSE,
    lead_time_hours NUMERIC,          -- hours between booking creation and appointment time
    no_show_risk_score NUMERIC,       -- 0.0–1.0, filled by ML pipeline
    reminder_sent_at TIMESTAMPTZ[],   -- audit trail of reminder sends
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Conversation sessions (chat + voice), minimal history kept for token efficiency
CREATE TABLE conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES users(id),
    channel TEXT CHECK (channel IN ('chat','voice')),
    state JSONB NOT NULL DEFAULT '{}',   -- slot-filling state machine snapshot
    summary TEXT,                        -- rolling LLM-free summary, not full transcript
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- FAQ knowledge base with vector embeddings for RAG
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE faq_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    embedding VECTOR(384),   -- matches BAAI/bge-small-en-v1.5 dimension
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX faq_embedding_idx ON faq_documents
    USING hnsw (embedding vector_cosine_ops);

-- Audit log (security requirement)
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id UUID,
    ip_address INET,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 6.2 Why pgvector instead of a separate vector DB
Keeping FAQ embeddings inside Postgres avoids running a second database, keeps retrieval consistent with transactional booking data, and is sufficient at salon-scale (hundreds to low-thousands of FAQ/policy chunks). Use an `hnsw` index for fast cosine similarity search.

---

## 7. Authentication & Authorization (production-grade)

1. **Password auth** for clients and staff: bcrypt (via `passlib`) with cost factor ≥ 12, never store or log plaintext.
2. **JWT access tokens** (short-lived, 15 min) + **refresh tokens** (7 days, rotated on use, stored hashed in DB or Redis with revocation support).
3. **Role-Based Access Control (RBAC):** `client`, `staff`, `admin` — enforced via a FastAPI dependency (`require_role(["staff","admin"])`) on every protected route; never trust role claims without re-checking against DB on sensitive actions.
4. **Email verification** on signup (token-based link) before a client can complete a booking (prevents fake-account spam bookings).
5. **Rate limiting** on auth endpoints and the chat/voice endpoints (Redis-backed sliding window, e.g. via `slowapi`) to block brute force and to protect the free LLM/STT quotas from abuse.
6. **CORS** locked to the deployed frontend origin(s) only.
7. **Input validation** everywhere via Pydantic schemas; SQL injection is structurally prevented by using the ORM/parameterized queries only.
8. **Secrets management:** all API keys (Groq, Gemini) and DB credentials in environment variables / a secrets manager — never committed, never sent to the frontend.
9. **Transport security:** HTTPS everywhere in production (TLS termination at the host/proxy); HSTS header enabled.
10. **PII handling:** phone numbers/emails encrypted at rest is optional-but-recommended (e.g. `pgcrypto`) for higher compliance bar; at minimum restrict PII columns from ever appearing in logs.
11. **Admin-only analytics endpoints** double-guarded: role check + audit-logged access.
12. **CSRF** not applicable to token-based JSON API, but ensure refresh tokens use `HttpOnly`, `Secure`, `SameSite=Strict` cookies if cookie-based refresh is chosen (recommended over storing refresh tokens in `localStorage`).
13. **Dependency & container scanning:** enable GitHub Dependabot (free) and `pip-audit` / `npm audit` in CI.

---

## 8. Data Security Checklist

- [ ] All traffic over HTTPS/WSS in production.
- [ ] Passwords hashed with bcrypt, never reversible.
- [ ] JWT secret key ≥ 256-bit random, rotated periodically.
- [ ] Refresh token rotation + revocation list in Redis.
- [ ] Least-privilege DB roles (the app's DB user should not be a Postgres superuser).
- [ ] Parameterized queries only (enforced by ORM).
- [ ] Rate limiting on auth, booking, and AI endpoints.
- [ ] Structured audit log for booking mutations and admin actions.
- [ ] `.env` in `.gitignore`; secrets injected at deploy time.
- [ ] Automated dependency vulnerability scanning in CI.
- [ ] Backups: nightly `pg_dump` (or provider-managed backups on Supabase free tier).
- [ ] GDPR-style "delete my data" endpoint for client self-service (data minimization).

---

## 9. Conversational AI Design (Chat + Voice) — Token-Minimized

This is the most architecturally important part of the system. The design goal is: **an LLM should only ever be called for the part of the conversation that genuinely requires natural-language understanding or generation** — everything else (slot filling, availability lookup, FAQ retrieval, confirmations) is deterministic code.

### 9.1 Conversation Orchestrator = Finite-State Slot-Filling Machine + LLM "edges"

Instead of sending the *entire chat history* to the LLM on every turn (the single biggest token waster in naive chatbot implementations), the orchestrator keeps a small structured **state object** per session (stored in `conversation_sessions.state` JSONB):

```json
{
  "intent": "book_appointment",
  "slots": {
    "service": "Haircut",
    "staff_preference": null,
    "date": "2026-09-13",
    "time_window": "afternoon",
    "location": "default"
  },
  "missing_slots": ["staff_preference", "exact_time"],
  "turn_count": 2
}
```

- On every user turn, the **first attempt is a fast, non-LLM path**: regex/rule-based date-time parsing (`dateparser` library), fuzzy service-name matching against the `services` table (`rapidfuzz`), and simple intent keyword classification. If the message unambiguously fills or clarifies slots, no LLM call happens at all.
- The LLM is invoked only for: (a) genuinely ambiguous/free-form user input the rule layer can't parse, (b) generating the final natural-language confirmation/response text, and (c) FAQ questions that RAG retrieval couldn't answer confidently.
- When the LLM *is* called, the prompt sent is **not the full transcript** — it is a compact, templated prompt containing only: the current `state.slots` JSON, the single latest user message, and a short system instruction. This keeps every LLM call small (typically 150–400 input tokens) and outputs are constrained to short JSON (function-calling style) or short spoken sentences (≤ 40 words) for voice.
- **Structured output / function calling:** every LLM call that needs to update state asks the model to return a strict JSON object (`{"slot_updates": {...}, "reply_text": "..."}"`), validated with Pydantic; invalid JSON triggers one retry with a stricter instruction, then falls back to a canned clarifying question (zero LLM cost).

### 9.2 Retrieval-Augmented FAQ Answering (avoids LLM calls entirely for known questions)

1. Salon policies/FAQs (hours, cancellation policy, parking, payment methods, service details) are pre-embedded with `BAAI/bge-small-en-v1.5` and stored in `faq_documents.embedding`.
2. On an incoming question, embed the query, run a `pgvector` cosine similarity search (`ORDER BY embedding <=> query_embedding LIMIT 3`).
3. If the **top match similarity ≥ threshold (e.g., 0.82)**, return the stored canonical answer directly — **zero LLM tokens used**.
4. If similarity is below threshold, pass the top-3 retrieved snippets + the user question to the LLM with a strict "answer only from context, else say you'll check with staff" instruction — this bounds hallucination and still keeps the prompt small (context snippets are short, curated answers, not whole documents).

### 9.3 Minimizing tokens for one end-to-end booking flow

| Step | LLM used? | Approx tokens |
|---|---|---|
| Greeting / menu presentation | No (static/templated) | 0 |
| "I want a haircut Saturday afternoon" → intent + slot extraction | Rule-based first; LLM only if ambiguous | 0–250 |
| Availability lookup | No (DB query against staff working hours + existing appointments) | 0 |
| "Here are 3 open slots" | No (templated from DB result) | 0 |
| User picks a slot / clarifies | Rule-based match; LLM fallback if free text | 0–250 |
| Confirmation message generation | LLM (short, ≤ 60 tokens out) | ~150 in / 60 out |
| FAQ aside ("do you take walk-ins?") | RAG hit → 0 LLM tokens (majority of cases) | 0 (RAG hit) or ~300 (RAG miss, LLM-grounded) |
| **Total typical flow** | | **~400–900 tokens**, well under the 1,500 budget in §3 |

### 9.4 Dual-LLM Router (Groq ⇄ Gemini) with automatic failover

Implement a small provider-agnostic interface:

```python
class LLMProvider(Protocol):
    async def complete(self, system: str, user: str, *, max_tokens: int, json_mode: bool) -> str: ...

class GroqProvider(LLMProvider): ...      # openai/gpt-oss-20b
class GeminiProvider(LLMProvider): ...    # gemini-2.5-flash / flash-lite
```

- **Primary:** Groq `openai/gpt-oss-20b` (fastest, generous free daily token budget) for both chat text generation and voice-turn generation (low latency matters most for voice).
- **On 429 / rate-limit / 5xx from Groq:** the router automatically retries once with backoff, then fails over to Gemini (`gemini-2.5-flash-lite` for simple JSON slot-extraction calls to conserve the pricier Gemini quota, `gemini-2.5-flash` for FAQ/RAG-grounded answers that need more reasoning).
- Track daily usage counters per provider in Redis so the router can **proactively** switch providers before hard-hitting a 429, based on the published free-tier ceilings (configurable in settings, since providers change limits — see `settings.py`).
- All prompts are provider-agnostic templates (stored in a `prompts/` directory), so switching providers never changes behavior, only which HTTP client is called.
- Every LLM call is logged (provider, tokens in/out, latency, purpose) to a `llm_usage` table for cost/quota observability, surfaced on the admin dashboard.

### 9.5 Voice Agent Pipeline

```
Browser mic (MediaRecorder) --WebSocket audio chunks-->
   FastAPI WS endpoint
      --> faster-whisper (STT, streaming/chunked transcription)
      --> Conversation Orchestrator (as above; same state machine as chat)
      --> LLM Router (only when needed, short replies for natural spoken cadence)
      --> OpenVoice V2 TTS (clones the salon's chosen brand voice from a short
          reference sample recorded once by the salon owner/staff)
      --> WebSocket audio stream back to browser --> playback
```

- **Latency budget:** faster-whisper `small` (int8) on CPU transcribes ~5s of audio in well under 1s; Groq's ~1,000 tok/s generation keeps LLM latency low; TTS synthesis is the main latency driver, so **stream TTS audio in chunks** as soon as the first sentence of the reply is ready rather than waiting for the full response.
- **Barge-in / interruption handling:** simple voice-activity detection (VAD, e.g. `webrtcvad` or Silero VAD, both open-source) on the client stream to detect when the user starts speaking again and stop playback.
- **Reference voice:** the salon records one ~10–15 second clean sample (e.g., the owner or a chosen professional voice actor with consent) once during onboarding; OpenVoice V2 clones tone/timbre; this becomes the consistent "brand voice" for every caller — do **not** clone a real user's voice without explicit consent (this is a data-security/ethics requirement, not just a technical one).
- **Same token-minimization rules from §9.1–9.4 apply identically to voice** — the orchestrator doesn't care which channel is talking to it.

---

## 10. No-Show Prediction Model

### 10.1 Synthetic dataset generation (Python + Faker)

Build `scripts/generate_synthetic_data.py` that creates a believable `appointments` history (recommend 15,000–50,000 rows) with **engineered patterns**, not pure randomness, so the model has real signal to learn:

- **Base no-show rate:** ~12%.
- **First-time client:** +15–20 percentage points relative risk.
- **Monday/early-morning slots (before 10am):** +8–10 points.
- **Short lead time (booked < 24h before appointment):** +10 points (paradoxically last-minute bookers are less committed) — *and* very long lead time (booked > 30 days out) also +5 points (people forget).
- **Prior no-show on file for that client:** +25 points (strong recurring predictor).
- **Booking channel = voice/chat (impulse booking) vs. web (deliberate):** slight effect, configurable.
- **High-value / long-duration services (e.g., 2hr spa package):** lower no-show (people plan around them) — negative effect.
- **Weather/seasonality flag (optional stretch):** small seasonal bump in winter/holiday weeks.
- Add realistic noise so the signal isn't trivially perfect (target realistic AUC ~0.75–0.85, not 0.99, since a 0.99 model on synthetic data usually means leakage).

### 10.2 Feature engineering

Features fed to the model (computed via a `features.py` module reusable both for training and live scoring):
- `is_first_visit`, `lead_time_hours`, `day_of_week`, `hour_of_day`, `is_monday_morning`
- `client_past_no_show_rate`, `client_total_visits`, `client_tenure_days`
- `service_duration_minutes`, `service_price_cents`, `service_category`
- `booking_channel` (one-hot: web/chat/voice/admin)
- `staff_no_show_rate_historical` (some staff/time-slots correlate with more no-shows)

### 10.3 Model

- Baseline: **Logistic Regression** (interpretable coefficients — good for explaining *why* a client is flagged, useful for the dashboard's "why is this client at risk" tooltip).
- Stronger option: **Gradient Boosting** (`sklearn.ensemble.HistGradientBoostingClassifier` — pure scikit-learn, no extra heavy dependency) as the production default; keep logistic regression as an interpretable "explain" companion model.
- Pipeline: `sklearn.pipeline.Pipeline` with `ColumnTransformer` (OneHotEncoder for categoricals, StandardScaler for numerics) → classifier. Persist with `joblib`.
- Evaluation: train/test split stratified by no-show label + time-based split (train on earlier months, test on later months) to simulate real deployment; report AUC, precision/recall at the operating threshold the business will actually use (e.g., top 20% riskiest flagged).
- **Retraining job:** a Celery Beat weekly task retrains on the latest real booking history once the app has accumulated real data, replacing the synthetic-data bootstrap model — write this retraining path from day one so it isn't a rewrite later.
- **Live scoring:** on every new booking creation, compute `no_show_risk_score` synchronously (model inference is fast, <10ms) and store it on the `appointments` row; this powers both the reminder scheduler and the dashboard.

### 10.4 Smart reminder scheduling driven by risk score

- Low risk (<0.3): single reminder 24h before.
- Medium risk (0.3–0.6): reminder at 48h and 4h before.
- High risk (>0.6): reminder at 72h, 24h, and 2h before, plus an explicit "reply YES to confirm or we'll release your slot" confirmation-required message, plus optionally flag for the front desk to make a personal courtesy call.
- Implemented as Celery tasks scheduled at appointment-creation time based on `no_show_risk_score`, executed by Celery Beat + Celery worker.
- Reminder channel: **email (SMTP, free with any provider like Gmail SMTP for low volume, or a free-tier transactional email service)** as the guaranteed-free default; architecture leaves a pluggable `NotificationChannel` interface so a paid SMS/WhatsApp provider can be dropped in later without touching business logic (see paid-alternatives note in the chat reply).

---

## 11. Frontend Plan (Fortune-500-grade public site + app)

### 11.1 Information architecture

- **`/`** — Home: hero section with high-quality salon imagery, value proposition, featured services, testimonials, CTA to "Book Now."
- **`/services`** — Full menu grouped by category (Hair, Nails, Skin, Spa Packages) with price, duration, and imagery per service (use royalty-free stock imagery pipeline or the salon's own photos — never scrape copyrighted images).
- **`/about`** — Brand story, team bios (staff cards), gallery.
- **`/contact`** — Location map embed, hours, contact form.
- **`/login`, `/signup`** — Auth pages, clean minimal forms, social-proof sidebar.
- **`/book`** — The booking experience: service picker → the AI assistant (chat bubble + voice mic button) takes over from here, or a manual calendar fallback for users who prefer clicking over chatting.
- **`/account`** — Client dashboard: upcoming appointments, history, reschedule/cancel.
- **`/admin`** (staff/admin only, RBAC-gated route) — Analytics dashboard (see §12).

### 11.2 Design system guidance (to look like a Fortune 500 site, not a template)

- Establish a distinctive brand palette (not default Tailwind indigo/blue) — pick 1 primary brand color rooted in a premium salon aesthetic (e.g., deep emerald, warm terracotta, or matte black + gold accent) plus a neutral scale.
- Use a refined type pairing: one elegant serif or high-end sans for headlines (e.g., a display font) + a clean, highly-legible sans for body text — avoid default system fonts for headings.
- Generous whitespace, large hero imagery, subtle scroll-triggered animation (e.g., `framer-motion`, MIT-licensed) — avoid generic "AI-generated SaaS template" look (no default shadcn hero, no stock gradient blobs).
- Real photography-style imagery (salon interiors, service close-ups, team portraits) rather than icon-heavy illustration-only pages — reinforces trust for a real-world service business.
- Sticky, minimal nav bar with the login/account entry point clearly visible; the "Book Now" CTA should be the highest-contrast button on every page.
- Fully responsive/mobile-first (majority of real salon clients book from phones).
- Accessibility: semantic HTML, proper contrast ratios, keyboard navigable forms, ARIA labels on the chat/voice widget.

### 11.3 Chat + Voice widget

- Persistent floating assistant launcher available on every page once logged in (and a lightweight "sign in to book" prompt if not).
- Two modes in one widget: **type** or **tap-to-talk** (mic button, waveform visualizer while listening, streaming partial transcript shown live).
- Shows quick-reply chips for common next steps (e.g., proposed time slots as tappable buttons) so users aren't forced to type/speak everything — this also reduces LLM calls, since a button tap is a deterministic slot fill.
- Displays a short "typing/thinking" and "speaking" indicator; for voice, plays back synthesized audio with a visible transcript for accessibility.

---

## 12. Analytics / Admin Dashboard

**Key views (React + Recharts, data from cached/materialized backend endpoints):**

1. **Overview cards:** total bookings (period), no-show rate %, estimated revenue at risk (Σ price of predicted-high-risk upcoming appointments), average lead time.
2. **Bookings over time** — line chart, filterable by service/staff/location.
3. **No-show rate trend** — line chart, with an overlay showing rate before/after the reminder system went live (demonstrates ROI).
4. **At-risk upcoming appointments table** — sortable by `no_show_risk_score`, with a one-click "send extra reminder now" / "call client" action for staff.
5. **Service popularity** — bar chart, bookings & revenue by service/category.
6. **Staff utilization** — booked hours vs. available hours per staff member.
7. **Channel breakdown** — bookings via web vs. chat vs. voice vs. admin (also useful to show the AI assistant's adoption/impact).
8. **LLM usage panel** (from `llm_usage` log) — tokens consumed per provider per day vs. free-tier ceiling, so the owner/dev can see quota headroom at a glance.

All dashboard queries should be backed by either indexed SQL aggregations or a nightly Celery job that materializes rollup tables (`daily_booking_stats`, etc.) so the dashboard is fast even as booking history grows.

---

## 13. Repository Structure

```
salon-saas/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings
│   │   │   ├── security.py        # JWT, password hashing
│   │   │   └── rate_limit.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/            # SQLAlchemy models per §6
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── services.py
│   │   │   │   ├── appointments.py
│   │   │   │   ├── conversation.py   # chat REST + WS endpoints
│   │   │   │   ├── voice.py          # WS voice endpoint
│   │   │   │   └── admin_analytics.py
│   │   ├── ai/
│   │   │   ├── orchestrator.py    # slot-filling state machine
│   │   │   ├── llm_router.py      # Groq/Gemini failover
│   │   │   ├── providers/
│   │   │   │   ├── groq_provider.py
│   │   │   │   └── gemini_provider.py
│   │   │   ├── rag.py             # embedding + pgvector retrieval
│   │   │   ├── stt.py             # faster-whisper wrapper
│   │   │   ├── tts.py             # OpenVoice V2 wrapper
│   │   │   └── prompts/           # templated prompt files
│   │   ├── ml/
│   │   │   ├── features.py
│   │   │   ├── train.py
│   │   │   ├── predict.py
│   │   │   └── models/            # persisted joblib artifacts
│   │   ├── tasks/                 # Celery tasks (reminders, retraining, rollups)
│   │   └── schemas/               # Pydantic request/response models
│   ├── scripts/
│   │   └── generate_synthetic_data.py
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   │   ├── assistant/         # chat + voice widget
│   │   │   └── admin/             # dashboard components
│   │   ├── hooks/
│   │   ├── lib/api-client.ts
│   │   └── store/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md
```

---

## 14. Step-by-Step Development Plan (Phased Milestones)

### Phase 0 — Project scaffolding (Day 0–1)
1. Initialize monorepo structure above; set up `docker-compose.yml` with services: `backend`, `frontend`, `postgres` (with `pgvector` image, e.g. `pgvector/pgvector:pg16`), `redis`, `celery_worker`, `celery_beat`.
2. Configure `pydantic-settings` for all env vars (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `GROQ_API_KEY`, `GEMINI_API_KEY`, model paths, thresholds).
3. Set up Alembic and create the initial migration from §6 schema.
4. Set up GitHub Actions CI skeleton (lint + test on push).

### Phase 1 — Auth & core data APIs (Day 2–4)
1. Implement `users` CRUD, signup/login/refresh/logout, email verification token flow.
2. Implement RBAC dependency and protect a sample admin route to prove it works.
3. Implement `services`, `locations`, `staff_profiles` CRUD (admin-only writes, public reads for the menu page).
4. Write unit + integration tests for auth flows (happy path + invalid credentials + expired token + role escalation attempt).

### Phase 2 — Booking engine (Day 5–7)
1. Implement availability computation: given a service + staff (or "any staff") + date range, compute open slots from `staff_profiles.working_hours` minus existing `appointments`.
2. Implement appointment CRUD: create/reschedule/cancel with double-booking prevention (DB-level exclusion constraint or transaction-level check).
3. Compute and store `lead_time_hours`, `is_first_visit`, `booking_channel` at creation time.
4. Tests: overlapping booking rejected, cancellation frees the slot, reschedule updates both time and audit log.

### Phase 3 — No-show ML pipeline (Day 8–10)
1. Write `generate_synthetic_data.py` implementing the patterns in §10.1; generate and load into a `training` schema/table.
2. Build `features.py`, `train.py`; train baseline logistic regression + gradient boosting; evaluate; persist best model with `joblib`.
3. Build `predict.py` and wire it into appointment creation (synchronous scoring) — store `no_show_risk_score`.
4. Build the Celery Beat weekly retraining task (works on synthetic data initially, designed to swap to real data seamlessly later).
5. Tests: feature pipeline determinism, model file loads, scoring endpoint returns a probability in [0,1].

### Phase 4 — Reminder engine (Day 11–12)
1. Implement `NotificationChannel` interface + an `EmailChannel` (SMTP) concrete implementation.
2. Implement Celery tasks that schedule reminders per §10.4 risk tiers at booking-creation time (`apply_async(eta=...)`).
3. Implement reminder cancellation when an appointment is cancelled/rescheduled.
4. Tests: correct number/timing of reminders scheduled per risk tier (mock Celery `apply_async`).

### Phase 5 — RAG FAQ system (Day 13–14)
1. Create `faq_documents` seed data (a realistic FAQ set: hours, cancellation policy, parking, payment, walk-ins, gift cards, etc.).
2. Build an embedding script using `BAAI/bge-small-en-v1.5` via `sentence-transformers`; populate `faq_documents.embedding`.
3. Build `rag.py`: embed incoming query, `pgvector` similarity search, threshold-based direct-answer vs. LLM-grounded-answer branching (§9.2).
4. Tests: known FAQ question returns the exact stored answer with zero LLM calls (mock/assert LLM provider not invoked).

### Phase 6 — LLM Router (Day 15–16)
1. Implement `GroqProvider` and `GeminiProvider` behind a common `LLMProvider` interface.
2. Implement the router with usage counters in Redis, automatic failover on 429/5xx, and structured JSON-mode calls with Pydantic validation + one retry.
3. Implement `llm_usage` logging table + write path.
4. Tests: simulate Groq 429 → confirm router falls over to Gemini; simulate malformed JSON → confirm retry-then-fallback-to-canned-response behavior.

### Phase 7 — Conversation Orchestrator (chat) (Day 17–20)
1. Implement the slot-filling state machine (§9.1) with rule-based extractors (`dateparser`, `rapidfuzz`) as the first-pass parser.
2. Wire in RAG (Phase 5) for FAQ-type intents and the LLM Router (Phase 6) as fallback/generation layer.
3. Implement the REST/WebSocket `conversation` endpoints; persist `conversation_sessions.state`.
4. Build the frontend chat widget (quick-reply chips, streaming text).
5. Tests: full scripted conversation → produces a valid `appointments` row; ambiguous input correctly triggers exactly one LLM call (assert call count).

### Phase 8 — Voice Agent (Day 21–25)
1. Integrate `faster-whisper` (`small`, int8) as the STT service; build a chunked/streaming WS transcription endpoint.
2. Integrate OpenVoice V2 for TTS with a configurable "brand voice" reference clip loaded from salon settings.
3. Add VAD-based barge-in handling.
4. Wire the same Conversation Orchestrator from Phase 7 into the voice WS endpoint (channel-agnostic core).
5. Build the frontend voice widget (mic button, waveform, live transcript, audio playback).
6. Load-test perceived latency end-to-end (mic → transcript → reply audio) and tune chunk sizes / model size (`base` vs `small`) for the acceptable latency/quality trade-off.

### Phase 9 — Admin Analytics Dashboard (Day 26–29)
1. Build nightly Celery rollup jobs producing `daily_booking_stats`, `client_risk_summary` materialized tables.
2. Build the analytics API endpoints (admin/staff-only, RBAC + audit logged).
3. Build the React admin dashboard views from §12 with Recharts.
4. Build the "at-risk appointments" actionable table with the manual "send extra reminder" trigger.

### Phase 10 — Public marketing site polish (Day 30–32)
1. Build Home/Services/About/Contact pages per §11.1–11.2 with the brand design system.
2. Source/curate imagery (salon's own photos ideally; otherwise properly licensed royalty-free imagery — never unlicensed scraped images).
3. SEO basics: meta tags, sitemap, semantic headings, image alt text.
4. Full responsive QA pass (mobile/tablet/desktop).

### Phase 11 — Security hardening & QA pass (Day 33–35)
1. Run through the §8 checklist item by item.
2. Add rate limiting to conversation/voice endpoints specifically (protect the free LLM/STT quotas from abuse).
3. Penetration-test the auth flows manually (role escalation attempts, token replay, expired token handling).
4. Load test booking creation for race conditions (double-booking under concurrency).

### Phase 12 — CI/CD & deployment (Day 36–38)
1. Finalize GitHub Actions: lint (`ruff`, `eslint`), type-check (`mypy`, `tsc`), tests (`pytest`, `vitest`), Docker build.
2. Write deployment docs for the chosen free-tier hosts (Supabase Postgres+pgvector, Upstash Redis, Render/Fly.io backend, Vercel frontend).
3. Configure production environment variables/secrets in the hosting provider's secret manager.
4. Smoke-test the fully deployed stack end-to-end (signup → book via chat → book via voice → admin dashboard shows the booking → reminder gets scheduled).

### Phase 13 — Documentation & handoff (Day 39–40)
1. `README.md` with local dev setup (`docker-compose up`), environment variable reference, and architecture diagram.
2. API docs auto-generated via FastAPI's OpenAPI/Swagger UI.
3. Runbook for retraining the no-show model on real data once collected.
4. Known-limitations / next-steps document (e.g., multi-language voice support, SMS channel upgrade path).

---

## 15. Testing Strategy Summary

| Layer | Tooling | Focus |
|---|---|---|
| Backend unit | `pytest` | Business logic, feature engineering, LLM router failover logic (mocked providers) |
| Backend integration | `pytest` + `httpx.AsyncClient` + test Postgres/Redis (via `docker-compose.test.yml` or `testcontainers`) | Full API flows including auth, booking, RAG |
| ML | `pytest` | Deterministic pipeline outputs, AUC threshold assertion on held-out synthetic set |
| Frontend unit | `Vitest` + `React Testing Library` | Components, hooks, state store logic |
| E2E (stretch goal) | `Playwright` (free/open-source) | Full signup → chat-book → dashboard-view happy path |
| Security | `pip-audit`, `npm audit`, manual RBAC test matrix | Dependency CVEs, access control matrix |

---

## 16. Environment Variables Reference (`.env.example`)

```
# App
ENVIRONMENT=development
SECRET_KEY=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/salon_db

# Redis
REDIS_URL=redis://redis:6379/0

# LLM providers (free tiers)
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_API_KEY=
GEMINI_MODEL_PRIMARY=gemini-2.5-flash
GEMINI_MODEL_LITE=gemini-2.5-flash-lite

# Voice
WHISPER_MODEL_SIZE=small
WHISPER_COMPUTE_TYPE=int8
TTS_ENGINE=openvoice_v2
TTS_REFERENCE_VOICE_PATH=/app/assets/brand_voice_sample.wav

# RAG
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RAG_SIMILARITY_THRESHOLD=0.82

# Email (reminders)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=

# Rate limiting
RATE_LIMIT_CHAT_PER_MINUTE=10
RATE_LIMIT_VOICE_PER_MINUTE=5
```

---

## 17. Explicit Non-Goals for MVP (keep scope disciplined)

- Payment processing / deposits (flag as a fast-follow; requires a payment gateway integration decision later).
- Multi-tenant SaaS billing (this plan builds one salon's platform first; multi-tenant architecture is a documented future extension, not in-scope now).
- Native mobile apps (responsive web covers mobile usage for MVP).
- SMS/WhatsApp reminders in the free-tier build (email is the guaranteed-free default; channel is pluggable for a future upgrade).

---

## 18. Definition of Done (MVP)

- A client can visit the marketing site, sign up, open the assistant, book an appointment entirely by **typing**, entirely by **voice**, or manually via the calendar UI.
- Every booking is scored for no-show risk at creation time and reminders are scheduled accordingly.
- FAQ questions are answered correctly from the knowledge base without unnecessary LLM calls.
- An admin can log in, see the analytics dashboard with real numbers from seeded/synthetic + live data, and identify at-risk upcoming appointments.
- The entire stack runs via `docker-compose up` with only free-tier external API keys (Groq, Gemini) required.
- CI is green on `main`; the security checklist in §8 is fully checked off.
