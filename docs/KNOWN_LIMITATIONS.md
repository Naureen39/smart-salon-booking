# Known Limitations & Next Steps

Every item here was a deliberate, disclosed scope decision made during development — not an oversight. Each includes why, and what upgrading it would take.

## Voice pipeline (Phase 8)

- **TTS defaults to `pyttsx3` (offline OS speech), not OpenVoice V2.** OpenVoice V2 has no clean pip wheel and needs a manually-downloaded checkpoint plus a reference voice clip — `app/ai/tts.py::OpenVoiceEngine` is a real integration point (it checks for the actual checkpoint/package and fails with setup instructions) but isn't wired to a real checkpoint in this environment. **To upgrade**: download the checkpoint from `huggingface.co/myshell-ai/OpenVoiceV2`, install the `openvoice` package per its own repo instructions, record a 10–15s brand-voice reference clip, set `TTS_ENGINE=openvoice_v2` and `TTS_CHECKPOINT_DIR`/`TTS_REFERENCE_VOICE_PATH`, then implement the actual inference call in `OpenVoiceEngine.synthesize` (the class already validates all its preconditions).
- **VAD is a simple energy-based (RMS) detector, not webrtcvad or Silero.** `webrtcvad`/`webrtcvad-wheels` need MSVC build tools not present in this dev environment; Silero VAD's streaming API (`VADIterator`) is event-based rather than a simple per-frame yes/no. **To upgrade**: swap `app/ai/vad.py::VoiceActivityDetector.is_speech()`'s implementation — the rest of the voice pipeline (`app/api/v1/voice.py`) only depends on that method's signature.
- **No token-by-token streaming for chat/voice replies.** The chat widget shows a "Thinking…" indicator and renders the full response at once; voice sends one complete reply-audio blob rather than incrementally. **To upgrade**: this needs the LLM router to support streaming completions and the frontend to render partial text/audio as it arrives — a real feature addition, not a config change.

## Conversation orchestrator (Phase 7)

- **No mid-flow intent switching.** Once a session's `intent` is set to `book_appointment`, every subsequent message is treated as continuing that flow. An FAQ question asked mid-booking will likely be misread as booking free-form text and routed to the LLM extraction fallback rather than answered directly. **To upgrade**: needs a context stack (or an FAQ-keyword check that runs even mid-flow) in `app/ai/orchestrator.py::process_turn`.
- **Only `book_appointment` and `faq` intents exist.** Reschedule/cancel-by-chat aren't wired into the orchestrator (they have their own REST endpoints from Phase 2, just not a conversational path to them).

## Frontend auth (all phases)

- **No login/signup pages or token storage exist yet.** `ChatWidget`, `AdminDashboard`, and the `/admin` route all accept `accessToken` as a prop and currently receive `null` from `App.tsx` — they show a "please sign in" state rather than being broken. **To upgrade**: build the actual `/login`/`/signup` pages and a token-storage mechanism (context/store), then wire the real token into these existing components — no changes needed to the components themselves.

## Marketing site (Phase 10)

- **Imagery is Lorem Picsum placeholders**, clearly marked in code comments, standing in for the salon's real photography.
- **Team bios on `/about` are static/curated**, not pulled from `staff_profiles` — that table has no name field (it's on the linked `User`), and joining them publicly would mean extending the Phase 1 `staff_profiles` endpoint, which felt out of scope for a marketing-page task.
- **The contact form submits via `mailto:`**, not a backend endpoint — no contact-form API exists in the plan's surface. This is an honest working fallback, not a form that silently does nothing.
- Per Phase 10's own task list (docs plan §14), only Home/Services/About/Contact were built — `/book`, `/login`, `/signup`, `/account` are named in the site's overall information architecture (§11.1) but weren't part of this phase's deliverables.

## ML / data (Phase 3, Phase 9)

- **No-show model trains on synthetic data.** See `docs/RUNBOOK_MODEL_RETRAINING.md` for the swap-to-real-data path — the feature schema was designed so this doesn't require touching live-scoring code.
- **`generate_synthetic_data.py`'s risk factors were tuned empirically** (log-odds combination, specific coefficients) to hit the plan's 0.75–0.85 AUC target — the plan's literal "additive percentage points" description was tested first and only reached 0.66 AUC before this change.
- **Faker isn't used**, despite being named in the plan's stack table — the synthetic dataset is pure numeric/categorical features with no PII to fake.
- **`daily_booking_stats` is the only rollup table** — the plan also mentions `client_risk_summary` as an example; it wasn't built because no dashboard view in §12 actually needs a per-client (as opposed to per-appointment) risk rollup.

## Infrastructure

- **The local dev docker-compose stack uses the Postgres owner role directly**, not the least-privilege role in `infra/scripts/create_restricted_db_role.sql` — that script is documented for production use; switching local dev to it by default would add friction for no real benefit in a single-developer environment.
- **RAG's similarity threshold (0.65) and the ML AUC target were both empirically calibrated** against the real embedding model / real synthetic data, not just taken from the plan's suggested defaults — see the inline comments in `app/core/config.py` and `scripts/generate_synthetic_data.py` for the measured numbers that justified each.
