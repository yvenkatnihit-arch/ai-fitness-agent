# Decisions — AI Fitness Agent

Every architecture decision: context, options, choice, why. Newest at the bottom.
Status: **Accepted** (decided), **Proposed** (waiting for Kruthi's answer).

---

## D-001 — Core stack
**Status:** Accepted (fixed in CLAUDE.md)
React + Vite + TS + Tailwind; FastAPI + Pydantic; LangGraph; Gemini via `langchain-google-genai`; Supabase (Postgres, Auth, RLS); LangSmith + own `agent_runs`; Vercel + Render + Supabase.
**Why:** chosen by Kruthi before the project started. Change only after asking.

## D-002 — Two model tiers via env vars
**Status:** Accepted
Small model (Flash-Lite class) by default; mid-tier (Flash class) only for plan generation and adjustments. IDs live in `.env`, all LLM setup in one module (`app/core/llm.py`).
**Why:** cost and latency; provider can be swapped later.

## D-003 — Repo layout
**Status:** Accepted
Options: (a) single repo (monorepo) with the brief's layout; (b) separate frontend and backend repos.
Choice: (a). The project root is the `Ai Fitness Agent` folder (this one); `frontend/`, `backend/`, `docs/` etc. are created directly inside it.
Why: one PR for changes touching both sides, simpler for a solo project. Vercel and Render both deploy from a sub-folder.

## D-004 — Python tooling
**Status:** Accepted
Options: pip + venv, Poetry, uv.
Choice: `uv`.
Why: fast, one lockfile, simple commands.

## D-005 — Where the calculation engine gets its inputs
**Status:** Accepted
`calc/` is pure Python: plain function arguments in, plain results out. No database, no FastAPI, no LLM imports. Limits are read from `safety_config.py`.
**Why:** easy to unit-test, and guarantees "the LLM never does math".

## D-006 — Schema design choices (schema proposed in the first-task reply)
**Status:** Accepted in principle (the schema is built table by table in Phase 2; details can still change then)
- `profiles.id` = `auth.users.id` (no separate user table).
- Weights stored in kg, heights in cm, nutrition per 100 g in the DB, converted for display.
- Foods and exercises are shared read-only reference tables (RLS: anyone signed in can read, nobody can write from the client). Custom user foods are a later addition.
- Plans are versioned and stored as rows (not JSON blobs) so logs can reference plan items.
- Proposals store the full change as JSON (`payload`) because their shape differs by type; everything else is relational.
- Meal and workout logs store a snapshot of nutrition values so history doesn't change if a food row is corrected later.

---

## D-007 — Output guard runs before streaming
**Status:** Accepted
Options: (A) guard the full text, then stream the approved text; (B) stream immediately and retract if the guard fails.
Choice: A.
Why: nothing unsafe is ever shown. B is more complex and can briefly show unsafe text. Cost: slightly later first token on multi-agent answers; single-agent answers use a fast code-only guard, so the cost is small.

## D-008 — Plan generation and check-in run as background jobs
**Status:** Accepted
Choice: the API starts the job and returns a job id; the UI polls a status endpoint. No long-running HTTP requests.
Why: Gemini free-tier rate limits (retries/backoff take time) and Render's request timeouts. Job state is stored in the database so it survives a page refresh.

## D-009 — Sex "other / prefer not to say"
**Status:** Accepted
Choice: `sex` accepts `female`, `male`, `other`. For `other`, BMR uses the average of the male (+5) and female (-161) Mifflin-St Jeor constants (-78), and the calorie floor is 1500 kcal (the higher of the two).
Why: the formula needs a constant, and the higher floor is the safer default. We ask for sex only because the formula needs it.

## D-010 — Surplus cap
**Status:** Accepted
Choice: calorie target is capped at TDEE + 10% for weight gain and muscle gain. Lives in `safety_config.py`.
Why: the brief capped deficits but not surpluses; a large surplus mostly adds fat.

## D-011 — Food dataset licenses reviewed in Phase 4
**Status:** Accepted
Before importing IFCT 2017, INDB or USDA data, I check each license and format and report to Kruthi with a recommendation.

## D-012 — LangGraph checkpointer connection confirmed in Phase 2
**Status:** Accepted
The Postgres checkpointer may not work over Supabase's pooled connection. In Phase 2 we test which connection string works (direct vs pooler) and record the result here.

## D-013 — Cost reporting: SQL view + script
**Status:** Accepted
Options: admin UI page, or a SQL view plus a script.
Choice: a view over `agent_runs` (daily cost, tokens, latency per model) and a small script that prints it. No admin UI.
Why: Kruthi is the only admin; far less work.

## D-014 — `needs_profile_update` becomes a pending proposal
**Status:** Accepted
When the router sets this flag, the relevant step creates a `plan_proposals` row of type `profile_change`. The user approves it in the UI before `profiles` changes. The chat never writes profile changes directly.
Why: matches the rule "no plan changes without user approval".

## D-015 — Gemini model IDs
**Status:** Accepted (checked 2026-11-03 on https://aistudio.google.com/docs/models)
Options:
- (a) Stable models: small `gemini-3.5-flash-lite` (Stable, recommended for new projects) and mid `gemini-3.6-flash` (Stable). This was Claude's recommendation.
- (b) `gemini-2.5-flash` for both tiers.
Choice: **(b)**, Kruthi's choice.
Known trade-offs, accepted:
- `gemini-2.5-flash` is deprecated. API access is limited to existing users, so a new key may be refused.
- Google routes it to `gemini-3.5-flash-lite` on **2026-12-01**. After that, the requests silently go to a different model.
- Using a Flash-class model for the small tier costs more per call than Flash-Lite. That doesn't matter on the free tier.
- **Revisit before 2026-12-01** (tracked in PROGRESS.md reminders). Switching to (a) is two lines in `.env`.
Not chosen at all: `gemini-3.8-flash` (labeled "New", not Stable) and any `-preview` model.
The IDs live only in `.env` (`GEMINI_SMALL_MODEL`, `GEMINI_MID_MODEL`), so switching models is a config change, not a code change.
