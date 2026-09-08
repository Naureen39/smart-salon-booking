# Security Checklist — docs plan §8

Status of each item as of Phase 11 (security hardening & QA pass).

- [x] **Passwords hashed with bcrypt, never reversible.** `passlib` + bcrypt, cost factor 12 (`app/core/security.py`).
- [x] **JWT access tokens (15 min) + refresh tokens (7 days, rotated on use, revocable).** `app/core/security.py`, `app/core/refresh_store.py` — refresh tokens are single-use; replaying a rotated-away token is rejected (`tests/test_auth.py::test_refresh_rotates_token_and_old_one_is_invalid`).
- [x] **RBAC enforced via a dependency, re-checked against the DB on every request.** `app/api/deps.py::require_role` re-verifies the current DB row's role, not the JWT's role claim (`tests/test_rbac.py::test_role_claim_in_stale_token_is_reverified_against_db`).
- [x] **Email verification on signup.** `app/api/v1/auth.py` — token-based, Redis-backed, 24h TTL.
- [x] **Rate limiting on auth, booking, and AI endpoints.** Redis-backed sliding window via `slowapi` (`app/core/rate_limit.py`) on signup (5/min), login (10/min), appointment creation (20/min), and chat messages (`RATE_LIMIT_CHAT_PER_MINUTE`); the voice WebSocket uses a manual Redis counter on new connections (`RATE_LIMIT_VOICE_PER_MINUTE`) since slowapi's decorator targets HTTP routes, not persistent WS connections.
- [x] **CORS locked to the deployed frontend origin(s).** `settings.cors_origins`, applied in `app/main.py`.
- [x] **Input validation via Pydantic everywhere; parameterized queries only (ORM).** No raw SQL string interpolation with user input anywhere in the codebase; migrations use static DDL only.
- [x] **Secrets in environment variables, never committed.** `.env` is gitignored; `.env.example` documents every variable with no real values.
- [x] **Structured audit log for booking mutations and admin actions.** `app/core/audit.py`, written on appointment create/cancel/reschedule, admin manual reminders, analytics access, and account self-deletion.
- [x] **Admin-only analytics endpoints double-guarded (role check + audit log).** `app/api/v1/admin_analytics.py::require_admin_analytics_access`.
- [x] **Dependency vulnerability scanning in CI.** `pip-audit` and `npm audit` steps in `.github/workflows/ci.yml` (informational — see note below); `.github/dependabot.yml` for automated update PRs.
- [x] **GDPR-style "delete my data" endpoint.** `DELETE /api/v1/auth/me` anonymizes PII and deactivates the account rather than hard-deleting, preserving referential integrity for appointments/audit history that have their own retention needs — see the docstring on `delete_my_data`.
- [x] **Least-privilege DB roles.** `infra/scripts/create_restricted_db_role.sql` — a ready-to-run script for a non-superuser application role. Not applied to the local dev docker-compose stack by default (that uses the simpler owner role for dev convenience); intended for production setup.
- [x] **Backups: nightly `pg_dump`.** `infra/scripts/backup_db.sh` — for self-hosted Postgres deployments; redundant if using Supabase's managed backups.
- [ ] **All traffic over HTTPS/WSS in production.** Deployment-time concern (TLS termination at the host/proxy) — not applicable to local dev; see `docs/DEPLOYMENT.md`.
- [ ] **JWT secret key rotation.** An operational practice (rotating `SECRET_KEY` periodically), not something enforced in code; documented as a deployment responsibility.

## Notes

**Dependency scanning is informational, not a merge gate.** `pip-audit`/`npm audit` run on every CI build but don't fail it (`|| true`) — many advisories are low-severity, transitive, and have no available fix, which would otherwise make CI flaky. Dependabot's automated PRs are the actual remediation mechanism; the CI step provides visibility.

## Additional hardening beyond the literal checklist

- **Double-booking is prevented at the database level** via a Postgres `EXCLUDE` constraint (migration `0002`), not an application-level pre-check — this closes the race-condition window a pre-check can't. Verified under real concurrency in `tests/test_security_hardening.py::test_concurrent_booking_requests_for_same_slot_only_one_succeeds` (5 simultaneous requests for the identical slot; exactly one succeeds).
- **JWT "none"-algorithm rejection** is explicitly tested (`test_none_algorithm_jwt_is_rejected`) — `decode_token()` pins `algorithms=["HS256"]`, so a token whose header claims `alg: none` is rejected outright.
- **SQL-injection-shaped input** is rejected at the Pydantic validation layer before it can reach a query (`test_login_rejects_sql_injection_shaped_email_at_validation`), on top of the ORM's parameterized queries.
