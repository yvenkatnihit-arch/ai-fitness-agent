# Progress — AI Fitness Agent

Updated at the end of every step. Format: `[x]` done, `[~]` in progress, `[ ]` not started.

## Current status

**Phase:** 1 — Calculation engine COMPLETE. Next: Phase 2 (database and auth).
**Decisions logged:** D-003 to D-023 (monorepo, uv, streaming Option A, background jobs, "other" sex, +10% surplus cap, cost view, profile-change proposals, etc.). Brief updated to match.
**Last completed:** 1.7: `app/calc/engine.py` (`calculate_targets()` = BMR → TDEE → goal → clamps → macros), 5 hand-worked example people + a "calc/ imports no DB/web/LLM code" test. 997 backend tests passing.
**Waiting on:** Venkat's answers to the Phase 1 check questions, then "go" for Phase 2 planning.

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

## Phases 2-11

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
