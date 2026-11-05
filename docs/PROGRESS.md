# Progress — AI Fitness Agent

Updated at the end of every step. Format: `[x]` done, `[~]` in progress, `[ ]` not started.

## Current status

**Phase:** 2 — Database and auth COMPLETE. Next: Phase 3 (onboarding + first deployment).
**Decisions logged:** D-003 to D-034. Brief updated to match.
**Last completed:** 2.10: LangGraph checkpointer works through the Session pooler (D-012), tables in a private `langgraph` schema, set up by `migrate.py`. Dependency-age policy (D-030): `exclude-newer` in `pyproject.toml`, LangGraph pinned. 1024 fast tests + 146 DB tests passing; 0 rows and 0 test checkpoints left behind.
**Last commit:** `d5b487e` (steps 2.1–2.8). Step 2.10 and the D-030 downgrades are not committed yet.
**Waiting on:** Venkat's answers to the Phase 2 check questions, then "go" for Phase 3 planning.
**Phase 1 check questions:** skipped for now; can revisit anytime.

## Phase 0 — Setup

- [x] 0.1 Create repo folder structure and git init
- [x] 0.2 Backend skeleton: FastAPI "hello" + `/health` endpoint + pytest
  - Known: pytest shows a `StarletteDeprecationWarning` suggesting `httpx2`. Harmless. Not switching until we verify that package on the official Starlette changelog/PyPI.
- [x] 0.3 `.env.example`, config module (pydantic-settings), `.gitignore`
  - `.env` lives in `backend/` (the frontend will get its own in 0.4). Gemini model IDs are blank until 0.5.
- [x] 0.4 Frontend skeleton: Vite + React + TS + Tailwind showing a page
  - Tests: Vitest + Testing Library (`npm test`). `frontend/.env.example` holds public `VITE_*` values only.
- [x] 0.5 Accounts: Google AI Studio, GitHub, Supabase done. LangSmith (Phase 7), Vercel and Render (Phase 3) later.
- [x] 0.6 Fill in the `Commands` section of CLAUDE.md

**Phase 0 complete (2026-11-05).** Backend: 5 tests. Frontend: 1 test. Gemini, Supabase, and GitHub all verified.

## Phase 1 — Calculation engine

- [x] 1.1 `safety_config.py` (all limits in one place)
- [x] 1.2 BMR (Mifflin-St Jeor) + tests
- [x] 1.3 TDEE (activity multipliers) + tests
- [x] 1.4 Calorie target by goal + tests (caps are applied in 1.5)
- [x] 1.5 Safety clamps (calorie floor, 25% deficit cap, 1%/week rate cap, screening flags) + tests
- [x] 1.6 Macros (protein per kg, fat floor, carbs remainder) + tests
- [x] 1.7 `calculate_targets()` that ties 1.2-1.6 together + tests (debug endpoint skipped; Phase 3 builds the real one)

**Phase 1 complete (2026-11-05).** `backend/app/calc/`: `bmr.py`, `tdee.py`, `targets.py`, `clamps.py`, `macros.py`, `engine.py`, `validation.py`. All limits in `safety/safety_config.py`. 997 backend tests (most are property tests over input grids).

## Phase 2 — Database and auth

- [x] 2.1 Migration tooling + `profiles` (RLS, `updated_at` trigger)
- [x] 2.2 `health_screening`, `goals`, `calculated_targets`
- [x] 2.3 Reference tables: `foods`, `food_synonyms`, `food_units`, `exercises` (read-only)
- [x] 2.4 Plans: meal/workout plan tables + `plan_proposals`
- [x] 2.5 Logs: meal logs, workout logs, `body_weight_entries`, `weekly_checkins` + Data API turned off (D-028)
- [x] 2.6 Chat and costs: `conversations`, `messages`, `conversation_summaries`, `agent_runs`, `usage_counters` + daily-cost view
- [x] 2.7 Backend DB layer (`app/db/`, queries under RLS per D-025) + `/ready` DB check
- [x] 2.8 Auth: verify Supabase JWT in FastAPI + `/me`
- [→] 2.9 RLS tests with two users **through the API**: moved to Phase 3 (only `/me` exists so far). Table-level cross-user RLS is already tested for every table group.
- [x] 2.10 LangGraph checkpointer connection test (D-012) + dependency-age policy (D-030)

**Phase 2 complete (2026-11-05).** 7 migrations: 27 tables + 1 view, RLS everywhere, user-written vs server-written split (D-027), Data API off (D-028). Backend: `app/db/` (pool, `user_transaction`, `admin_transaction`), `app/core/auth.py` (ES256 JWT), `GET /me`, `/ready`, `app/agents/checkpointer.py`. Scripts: `migrate.py`, `daily_cost.py`. 1024 fast + 146 DB tests.

## Phase 3 — Onboarding + first deployment

Decisions: D-031 (email confirmation off for now), D-032 (supabase-js for Auth only), D-033 (local Docker build), D-034 (only Venkat uses the deployed app).

- [ ] 3.1 Onboarding request models (Pydantic): 18+, ranges, allowed values
- [ ] 3.2 Endpoints: save profile, screening, goal, first weigh-in (under RLS)
- [ ] 3.3 `POST /onboarding/complete` (consent check → `calculate_targets()` → save targets) + API-level cross-user tests (moved from 2.9)
- [ ] 3.4 CORS, consistent error responses, structured logging
- [ ] 3.5 Frontend: sign up / sign in (Supabase Auth), protected pages
- [ ] 3.6 Frontend API helper (attaches token) + onboarding step 1: consent + basics
- [ ] 3.7 Onboarding steps 2–4: goal & activity, diet & preferences, equipment & schedule, screening
- [ ] 3.8 Results screen: targets, reasons, doctor note, habits view
- [ ] 3.9 Backend Dockerfile (built locally) + deploy to Render
- [ ] 3.10 Frontend deploy to Vercel + end-to-end check in production

## Phases 4-11

Not started. See `docs/PROJECT_BRIEF.md` section 14.

## Mock data / placeholders (`# MOCK:`)

None yet.

## Eval results

None yet (evals start in Phase 7).

## Reminders for later

- Before any friend enters real health data: enable Gemini billing (paid tier).
- **Before 2026-12-01:** `gemini-2.5-flash` gets routed to `gemini-3.5-flash-lite`. Decide whether to switch `.env` to the stable models (D-015).
- Verify the Tele-MANAS helpline number (14416) before shipping the crisis message.
- Check each nutrition dataset's license before importing (Phase 4).
