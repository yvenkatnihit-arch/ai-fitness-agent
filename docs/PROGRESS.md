# Progress — AI Fitness Agent

Updated at the end of every step. Format: `[x]` done, `[~]` in progress, `[ ]` not started.

## Current status

**Phase:** 0 — Setup (steps 0.1–0.4 done)
**Last completed:** 0.4: frontend (Vite 8, React 19, TypeScript, Tailwind 4, Vitest). 1 frontend test + 5 backend tests passing; build and lint clean.
**Decisions logged:** D-003 to D-014 (monorepo, uv, streaming Option A, background jobs, "other" sex, +10% surplus cap, cost view, profile-change proposals, etc.). Brief updated to match.
**In progress:** 0.5: Kruthi is creating accounts and filling in `backend/.env`. Model: `gemini-2.5-flash` for both tiers (D-015). Gemini key verified on 2026-11-03 (HTTP 200, model served `gemini-2.5-flash`). Supabase and GitHub still to do.
**Waiting on:** Kruthi to report "done" for 0.5, then I'll verify that `.env` loads (without printing secrets).

## Phase 0 — Setup

- [x] 0.1 Create repo folder structure and git init
- [x] 0.2 Backend skeleton: FastAPI "hello" + `/health` endpoint + pytest
  - Known: pytest shows a `StarletteDeprecationWarning` suggesting `httpx2`. Harmless. Not switching until we verify that package on the official Starlette changelog/PyPI.
- [x] 0.3 `.env.example`, config module (pydantic-settings), `.gitignore`
  - `.env` lives in `backend/` (the frontend will get its own in 0.4). Gemini model IDs are blank until 0.5.
- [x] 0.4 Frontend skeleton: Vite + React + TS + Tailwind showing a page
  - Tests: Vitest + Testing Library (`npm test`). `frontend/.env.example` holds public `VITE_*` values only.
- [~] 0.5 Accounts checklist (Kruthi): Google AI Studio, Supabase, GitHub now; LangSmith (Phase 7), Vercel and Render (Phase 3) later
- [ ] 0.6 Fill in the `Commands` section of CLAUDE.md

## Phase 1 — Calculation engine

- [ ] 1.1 `safety_config.py` (all limits in one place)
- [ ] 1.2 BMR (Mifflin-St Jeor) + tests
- [ ] 1.3 TDEE (activity multipliers) + tests
- [ ] 1.4 Calorie target by goal, with deficit/surplus caps + tests
- [ ] 1.5 Safety clamps (calorie floor, 25% deficit cap, 1%/week rate cap, screening flags) + tests
- [ ] 1.6 Macros (protein per kg, fat floor, carbs remainder) + tests
- [ ] 1.7 `calculate_targets()` that ties 1.2-1.6 together + a tiny debug endpoint (optional) + tests

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
