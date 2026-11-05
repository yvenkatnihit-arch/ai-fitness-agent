# Progress — AI Fitness Agent

Updated at the end of every step. Format: `[x]` done, `[~]` in progress, `[ ]` not started.

## Current status

**Phase:** 3 — Onboarding + first deployment (steps 3.1–3.8 done: sign-up → onboarding → targets works locally)
**Decisions logged:** D-003 to D-036. Brief updated to match.
**In progress:** 3.10: frontend live at https://ai-fitness-agent-one.vercel.app (D-036). Checked: no secrets in public JS, backend URL baked in, SPA reloads, security headers, CORS from the Vercel origin, and a full onboarding through production (targets match a hand calculation). Waiting on Venkat's own browser/phone test.
**Earlier:** 3.9: backend live on Render at https://ai-fitness-agent-5dq9.onrender.com (Docker, Singapore, Free). Dockerfile + `.dockerignore`; image checked locally, then the same checks pass on Render (health, ready, CORS, real Supabase token on `/me`, onboarding status, 422). First deploy failed on the build context (fixed in Render settings, see D-033).
**Earlier:** 3.8: results screen (`targets/TargetsView.tsx`): daily calories (Indian digit grouping) and macros exactly as the backend sent them, "Why these numbers", doctor note, habits view with no numbers for eating-disorder history; home loads `/targets/current` once onboarding is done. 48 frontend tests, build, lint passing.
**Earlier:** 3.7: onboarding screens for goal, food preferences (disliked-food chips), training (equipment, days) and health check (explicit Yes/No for all 6, injury areas), plus a Finish screen that calls `POST /onboarding/complete`. Shared `useSaveStep` hook and `Choice` component; `onboarding/options.ts` with a test that reads the backend's Python files and checks every option list matches. 43 frontend tests, build, lint passing. Venkat confirmed sign-up → consent → basics works in the browser.
**Earlier:** 3.6: `lib/api.ts` (token on every call, our error format → `ApiError` with field errors + request ID, "can't reach the server" message), `/onboarding` page driven by `GET /onboarding/status`, consent step (draft privacy notice `2026-11-draft`) and basics step, home redirects unfinished users to onboarding. 28 frontend tests, build, lint passing.
**Earlier:** 3.5: frontend sign up / sign in with supabase-js (Auth only), `AuthProvider` + `RequireAuth` + `/sign-in` page with friendly errors, react-router; `frontend/.npmrc` dependency-age rule (D-030), 5 frontend packages pinned older and tree rebuilt; `frontend/.env` created from public values; "Confirm email" already off (D-031 needs no dashboard change). 17 frontend tests, build, lint passing.
**Earlier:** 3.4: CORS (exact origins, no cookies), one error format with request_id (422 lists fields without echoing values; 500 generic; PoolTimeout → 503), JSON request logs with X-Request-ID (`app/core/{middleware,errors,logging}.py`), `LOG_LEVEL` setting, settings split so the app imports without `.env` (D-035). 1114 fast + 160 DB tests passing.
**Earlier:** 3.3: `POST /onboarding/complete` (`app/workflows/complete_onboarding.py`: read as user → `calculate_targets()` → one admin transaction marks onboarded + inserts targets; double-submit safe) and `GET /targets/current`. Display rounding + plain-English reasons + doctor note (`app/schemas/targets.py`); eating-disorder history → no numbers returned. Cross-user API tests (moved from 2.9). 1099 fast + 160 DB tests passing; 0 rows left behind.
**Earlier:** 3.2: onboarding endpoints (`app/api/onboarding.py` → `app/db/onboarding.py`, all under RLS): `GET /onboarding/status`, `PUT /onboarding/{consent,basics,goal,preferences,training,screening}`. Consent first (409), goal needs basics (409), target-weight direction check (`app/calc/goals.py`, 422), locked after onboarding (409). Migration 8: `profiles.consent_version`. 1096 fast + 153 DB tests passing; 0 rows left behind.
**Earlier:** 3.1: onboarding request models (`app/schemas/onboarding.py`), `app/calc/age.py`, `app/core/vocabulary.py`, `app/core/time.py`.
**Last commit:** `9de2d29` (Dockerfile). Docs updates since then not committed yet.
**Waiting on:** Venkat to try sign-up → onboarding → targets on the live site (laptop and phone), then the Phase 3 wrap-up.
**Phase 2 check questions:** skipped for now; can revisit anytime.
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

- [x] 3.1 Onboarding request models (Pydantic): 18+, ranges, allowed values
- [x] 3.2 Endpoints: save profile, screening, goal, first weigh-in (under RLS)
- [x] 3.3 `POST /onboarding/complete` (consent check → `calculate_targets()` → save targets) + API-level cross-user tests (moved from 2.9)
- [x] 3.4 CORS, consistent error responses, structured logging
- [x] 3.5 Frontend: sign up / sign in (Supabase Auth), protected pages
- [x] 3.6 Frontend API helper (attaches token) + onboarding step 1: consent + basics
- [x] 3.7 Onboarding steps 2–4: goal & activity, diet & preferences, equipment & schedule, screening
- [x] 3.8 Results screen: targets, reasons, doctor note, habits view
- [x] 3.9 Backend Dockerfile (built locally) + deploy to Render: https://ai-fitness-agent-5dq9.onrender.com
- [~] 3.10 Frontend deploy to Vercel + end-to-end check in production: live and checked by script; Venkat's browser test pending

## Phases 4-11

Not started. See `docs/PROJECT_BRIEF.md` section 14.

## Mock data / placeholders (`# MOCK:`)

- `frontend/src/onboarding/privacyNotice.ts`: **DRAFT** privacy notice (`2026-11-draft`). Not a mock, but must be reviewed (and the version bumped) before any friend signs up (D-034).

## Eval results

None yet (evals start in Phase 7).

## Reminders for later

- Before any friend enters real health data: enable Gemini billing (paid tier).
- **Before 2026-12-01:** `gemini-2.5-flash` gets routed to `gemini-3.5-flash-lite`. Decide whether to switch `.env` to the stable models (D-015).
- Verify the Tele-MANAS helpline number (14416) before shipping the crisis message.
- Check each nutrition dataset's license before importing (Phase 4).
- **Before friends join (D-034):** review the draft privacy notice (`frontend/src/onboarding/privacyNotice.ts`) and bump its version; turn email confirmation on with a real email provider (D-031); build data export and account deletion, which the notice promises (Phase 10); move DB tests off the real project (D-026).
