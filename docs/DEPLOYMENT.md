# Deployment Guide (Free-Tier Stack)

This follows the plan's host-agnostic, 100%-free-tier architecture (docs plan §4). Every step below can be done on each provider's free plan.

## Architecture at a glance

| Component | Free-tier host | Notes |
|---|---|---|
| Postgres + pgvector | Supabase | pgvector ships built-in |
| Redis | Upstash | broker for Celery, cache, rate limiting |
| Backend (FastAPI) | Render or Fly.io | Dockerfile-based |
| Celery worker | Render or Fly.io | same image as backend, different start command |
| Celery beat | Render or Fly.io | same image, `celery beat` start command |
| Frontend (static build) | Vercel, Netlify, or Cloudflare Pages | `frontend/dist` after `npm run build` |

The backend image is larger than a typical FastAPI service because it bundles the ML stack (scikit-learn, sentence-transformers/transformers, faster-whisper); budget for a slower first deploy and check your host's image size limit if it's unusually restrictive.

## 1. Database: Supabase (Postgres + pgvector)

1. Create a project at [supabase.com](https://supabase.com) (free tier).
2. In the SQL editor, confirm the `vector` extension is available (Supabase ships it by default; `CREATE EXTENSION IF NOT EXISTS vector;` is also run automatically by migration `0001`).
3. Copy the connection string from **Project Settings → Database → Connection string** and rewrite it for asyncpg:
   ```
   postgresql+asyncpg://<user>:<password>@<host>:5432/postgres
   ```
4. Run migrations against it once, from your machine or a one-off CI job:
   ```bash
   cd backend
   DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
   ```
5. **Least-privilege role**: run `infra/scripts/create_restricted_db_role.sql` (adjust the password) and point the app's `DATABASE_URL` at that role instead of the Supabase owner role, per `docs/SECURITY_CHECKLIST.md`.
6. **Backups**: Supabase's free tier includes managed daily backups with a short retention window; `infra/scripts/backup_db.sh` is only needed if you self-host Postgres instead.

## 2. Redis: Upstash

1. Create a free Redis database at [upstash.com](https://upstash.com).
2. Copy the `rediss://` (TLS) connection string it gives you and use it directly as `REDIS_URL`.

## 3. Backend: Render or Fly.io

Both work from the existing `backend/Dockerfile` unchanged.

**Render:**
1. New → Web Service → connect the repo, root directory `backend`.
2. Render auto-detects the Dockerfile. Set the start command to the Dockerfile's default (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
3. Add two more services from the *same* repo/image for the background workers:
   - **Celery worker**: same Docker image, start command `celery -A app.tasks.celery_app worker --loglevel=info`.
   - **Celery beat**: same image, start command `celery -A app.tasks.celery_app beat --loglevel=info`.
4. Add all variables from `.env.example` under **Environment** for all three services (see §5 below).

**Fly.io** follows the same pattern: one `fly.toml` app for the web process, and `fly.toml` `[processes]` entries (or separate apps) for `worker` and `beat` using the same image with different `cmd`.

## 4. Frontend: Vercel / Netlify / Cloudflare Pages

1. Connect the repo, set the root directory to `frontend`.
2. Build command: `npm run build`. Output directory: `dist`.
3. Set `VITE_API_BASE_URL` to the deployed backend's URL (e.g. `https://glowdesk-api.onrender.com`).
4. Update the backend's `CORS_ORIGINS` to include the deployed frontend's origin.

## 5. Environment variables / secrets

Every variable is documented in `.env.example` at the repo root. In each host's secret manager (Render/Fly.io "Environment", Vercel "Environment Variables", etc.), set at minimum:

- `SECRET_KEY`: a fresh, random 256-bit value (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Never reuse the local dev value.
- `DATABASE_URL`, `REDIS_URL`: from steps 1-2.
- `GROQ_API_KEY`, `GEMINI_API_KEY`: free-tier keys from each provider's console.
- `CORS_ORIGINS`: the deployed frontend's exact origin.
- `ENVIRONMENT=production`: flips the refresh-token cookie's `Secure` flag on (see `app/api/v1/auth.py`).

Never commit real values for any of these; `.env` is gitignored specifically so this mistake isn't possible by accident.

## 6. Post-deploy smoke test

Once all pieces are live, walk through this by hand (matches the plan's Definition of Done, §18):

1. `GET /health` on the backend returns `{"status": "ok", "environment": "production"}`.
2. Sign up a test account on the deployed frontend; confirm the verification email is logged/sent.
3. Log in, open the chat widget, book an appointment by typing a request (e.g. "book a haircut next Tuesday morning").
4. Confirm the booking appears when querying `GET /api/v1/appointments/me` with that user's token.
5. Log in as an admin/staff account, open `/admin`, confirm the new booking shows up in the overview cards and bookings-over-time chart (may need `python -m scripts.backfill_analytics` run once against the production DB if this is a fresh environment).
6. Check the Celery worker's logs for a scheduled reminder task after booking creation.
7. Ask the chat widget an FAQ question (e.g. "what are your hours?") after running `python -m scripts.seed_faq` against the production DB, and confirm it answers without needing an LLM call (check `GET /api/v1/admin/llm-usage` shows no new row for that turn).

## 7. One-time production setup scripts

Run these once against the production database after the first deploy:

```bash
cd backend
DATABASE_URL="..." python -m scripts.seed_faq
DATABASE_URL="..." python -m scripts.generate_synthetic_data --rows 20000 --out data/synthetic_appointments.csv
DATABASE_URL="..." python -m app.ml.train --data-path data/synthetic_appointments.csv
DATABASE_URL="..." python -m scripts.backfill_analytics --days 90
```

The no-show model and analytics rollup are designed to swap to real accumulated data over time (see the docstrings in `app/ml/train.py` and `app/tasks/analytics.py`); these commands just bootstrap a non-empty starting state.
