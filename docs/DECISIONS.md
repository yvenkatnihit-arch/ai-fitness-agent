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
**Result (Step 2.10, 2026-11-05): the Session pooler (port 5432) works.** `tests/db/test_checkpointer.py` shows state surviving a brand-new connection, 12 runs on one connection (psycopg's prepared statements are fine in session mode), and thread deletion.
- Connection settings: `autocommit=True`, dict rows, `search_path = langgraph`.
- Tables live in a private `langgraph` schema (migration 7) with no access for `anon`/`authenticated`, not in `public` next to our RLS tables.
- `scripts/migrate.py` runs `PostgresSaver.setup()` after our migrations, so it is idempotent and schema changes stay in one command.
- Don't use the Transaction pooler (port 6543) for the checkpointer. The direct connection is IPv6-only on the free plan.
- Phase 7 swaps the single connection in `app/agents/checkpointer.py` for an async pool with the same settings.

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

## D-016 — "Mild" deficit for users with screening flags
**Status:** Accepted (Venkat chose the recommended 10%, 2026-11-05)
The brief says flagged users get "no calorie deficit beyond a mild level" but doesn't give a number.
Options: 5%, **10%**, or 15% of TDEE.
Choice: 10% (`FLAGGED_MAX_DEFICIT_FRACTION = 0.10` in `safety_config.py`). That's less than half the normal 25% cap, and roughly 200–250 kcal/day for most adults: a slow, gentle deficit.
Eating disorder history stays at 0% (no deficit), as the brief says. With several flags, the strictest rule wins.

## D-017 — Router + Send, not a supervisor loop
**Status:** Accepted (Venkat, 2026-11-05)
Options:
1. Router + Send (one routing decision, specialists in parallel). Add a bounded "needs another agent?" round later, only if evals show it's needed.
2. Full supervisor loop: an LLM picks the next agent after each one finishes.
3. Hybrid from the start.
Choice: **1**.
Why: 3–4 LLM calls per multi-intent message instead of 5+. Agents run in parallel, which fits the 2–3 s first-token target and puts less pressure on Gemini rate limits. Routes are predictable, so evals stay simple. Cross-domain needs are covered by shared read-only tools.
Follow-ups:
- `get_weight_trend` becomes a shared read-only tool, so the workout and nutrition agents can see weight trends without a supervisor.
- In Phase 7, keep the graph easy to extend with one optional extra routing round after the merge. Revisit if Phase 7 evals show that cross-agent follow-ups fail often.

## D-018 — Summarize node at the end of the chat graph
**Status:** Accepted (Venkat, 2026-11-05)
Options: (a) summarize every 10 new messages; (b) summarize when recent history passes a token threshold.
Choice: **(a)**.
Design:
- An explicit `summarize` node is the last node of the chat graph. It runs **after** the reply has streamed, so the user never waits for it.
- A plain-code conditional edge runs it only when there are ≥10 new messages since the last summary. Otherwise the graph goes straight to END.
- The summary rolls forward: its input is the previous summary plus the new messages, never the full history, so its cost stays flat.
- Small model, `max_tokens` capped (~300). It keeps goals, preferences, injuries and recent decisions, and leaves out numbers, because tools always fetch targets fresh.
- It writes only to `conversation_summaries`. If it fails, chat still works and it retries at the next trigger.
Why: it saves LLM tokens (each call sends the last 6 messages + summary), not database space. Full messages stay in `messages` for chat history and data export.
Revisit (b) if long messages turn out to be common.

## D-019 — Plausible input ranges for body measurements
**Status:** Accepted (Venkat said "go" without changes, 2026-11-05)
The brief asks for check constraints on valid ranges but gives none. Proposal, in `safety_config.py`:
- Age 18–100 years (18 is the brief's minimum).
- Weight 30–300 kg.
- Height 120–230 cm.
Why: values outside these ranges are almost always typos (height entered in metres, weight in pounds) and would give nonsense or unsafe targets. Calculations raise a clear error; onboarding will show a friendly message instead. Phase 2 database check constraints will use the same ranges.

## D-020 — Activity levels and TDEE multipliers
**Status:** Accepted (standard values; change if you prefer)
Five levels, with the widely used multipliers on Mifflin-St Jeor BMR:
- `sedentary` 1.2: desk job, little or no exercise
- `light` 1.375: exercise 1–3 days a week
- `moderate` 1.55: exercise 3–5 days a week
- `active` 1.725: exercise 6–7 days a week
- `very_active` 1.9: hard daily training or a physical job
They live in `app/calc/tdee.py`. They're calculation constants, not safety limits. Onboarding shows the descriptions so users pick honestly. People tend to overestimate their activity, so the weekly check-in (Phase 8) corrects for that using real weight trends.

## D-021 — Default calorie adjustment per goal
**Status:** Accepted (Venkat, 2026-11-05)
Fraction of TDEE, in `app/calc/targets.py`:
- `fat_loss` −20%: sustainable, roughly 0.5 kg/week for most people
- `muscle_gain` +8%: lean bulk
- `weight_gain` +10%: at the surplus cap (D-010)
- `recomp` −10%: small deficit plus high protein
- `general_fitness` 0%: maintenance
These are the *ideal* targets. The safety clamps (Step 1.5: calorie floor, screening flags, 1%/week loss rate) run afterwards and can only make a target more conservative. A test checks that every default stays within the `safety_config.py` caps.

## D-022 — Safety clamp order and the kcal-per-kg figure
**Status:** Accepted (Venkat said "go", 2026-11-05)
- `KCAL_PER_KG_FAT = 7700` (the standard approximation) turns "≤1% of body weight per week" into a daily cap: `weight × 0.01 × 7700 / 7`. For 80 kg, that's 880 kcal/day.
- Clamp order in `app/calc/clamps.py`: surplus cap → deficit cap (25% / 10% flagged / 0% eating disorder history) → loss-rate cap → calorie floor. **The floor goes last, so it always wins.** Each clamp can only make the target more conservative.
- The result carries `reasons` (codes such as `screening_deficit_cap`) so the UI can explain any change, plus `doctor_note` (any flag) and `focus_on_habits` (eating disorder history: show balanced meals, not numbers).
- Edge case: if TDEE is below the floor (for example a very small, sedentary person), the floor still applies and the target ends up slightly above TDEE. That's the safer outcome.

## D-023 — Macro rules
**Status:** Accepted (Venkat, 2026-11-05)
- Protein g per kg body weight, by goal (`app/calc/macros.py`): fat loss 2.0, recomp 2.0, muscle gain 1.8, weight gain 1.6, general fitness 1.6.
- Safety limits (`safety_config.py`):
  - **Kidney flag → protein ≤ 0.8 g/kg.** High protein can strain damaged kidneys. This wasn't in the brief; Claude flagged it.
  - Protein ≤ 35% of calories, so very heavy users don't get huge protein targets. A height-based reference weight was considered and rejected as more complex.
  - Fat = 25% of calories (the minimum, for hormones and absorbing vitamins A, D, E and K).
- Carbs fill the remaining calories. With protein ≤ 35% and fat = 25%, carbs are always ≥ 40%, never negative.
- Energy per gram: protein 4, carbs 4, fat 9. Macros always add up exactly to the safe calorie target.
- Values are kept unrounded; rounding happens only for display.

## D-024 — Migrations with the Supabase CLI
**Status:** Accepted (Venkat, 2026-11-05)
Options: (a) Supabase CLI; (b) our own Python migration script.
Choice: **(a)**. It's run with `npx supabase@2.121.0`, pinned. 3.0.0 came out on 2026-11-04 and is too new to trust yet; revisit later.
- Migrations are SQL files in `supabase/migrations/`, named `<timestamp>_<name>.sql`, applied in order with `db push --db-url`. That means no `supabase login` or `link` and no Docker.
- `backend/scripts/migrate.py` reads `DATABASE_URL` from `.env` and runs the push, so the URL never has to be typed or shown.
- The CLI records applied migrations in `supabase_migrations.schema_migrations`, so each file runs exactly once.

## D-025 — Backend queries run under RLS
**Status:** Accepted (Venkat, 2026-11-05)
Options: (a) per-request transaction as Supabase's `authenticated` role with the user's JWT claims; (b) Supabase REST client with the user's token; (c) admin connection plus manual `where user_id = ...`.
Choice: **(a)**. For each user request: `begin; set local role authenticated; select set_config('request.jwt.claims', <claims>, true); ...queries...; commit;`. RLS then applies to every query exactly as if the user had made it.
- The admin (`postgres`) connection is only for migrations and system jobs (e.g. `agent_runs`, background workers), in clearly named functions.
- Implemented in Step 2.7: `app/db/transactions.py` provides `user_transaction(user_id: UUID)` and `admin_transaction(reason)`. The reason is required and logged. A DB test proves pooled connections never carry a user's role or claims into the next use.
- Server-side checks stay as well (CLAUDE.md: RLS **and** server-side).
Why not (c): one forgotten filter would leak another user's health data, with no second line of defence.

## D-026 — Where database tests run
**Status:** Accepted (Venkat, 2026-11-05)
Options: (a) the current Supabase project with throwaway test users; (b) a second Supabase project; (c) local Supabase in Docker.
Choice: **(a)** for now. The project holds only test data until friends join.
- DB tests are marked `@pytest.mark.db` and are **opt-in**: plain `uv run pytest` leaves them out (fast, offline), and `uv run pytest -m db` runs them against Supabase.
- Tests create their own users and rows inside a transaction that is always rolled back, so nothing is left behind (checked after each step).
- **Revisit before real users join:** move tests to (b) so they never touch real data.

## D-027 — User-written vs server-written tables
**Status:** Accepted (Claude's default in Step 2.4; Venkat can revert)
Two kinds of user-owned tables:
- **User-written** (`profiles`, `health_screening`, `goals`; later the log tables): the user's own answers and records. RLS lets users read and write their own rows.
- **Server-written** (`calculated_targets`, `meal_plans` + items, `workout_plans` + days + exercises, `plan_proposals`): produced by code that applies the safety limits. Users can only **read** their own rows. No write policies and no write privileges, so not even the public Supabase API with the user's own token can change them. The backend writes them with the admin connection, in clearly named functions, after verifying the user from their JWT.
Why: targets and plans must always pass through the calc engine and safety validation. If users could insert rows directly, that would be a way around both. Approving a proposal goes through a backend endpoint that re-validates it before applying.
Changed in migration 4: `calculated_targets` lost its user insert policy from migration 2.
Child tables also carry `user_id` with a composite foreign key `(parent_id, user_id)`, so RLS stays a simple `user_id = auth.uid()` check and a child row can never belong to a different user than its parent.

## D-028 — Supabase Data API turned off for our tables
**Status:** Accepted (Venkat, 2026-11-05)
Problem found in Step 2.5: Supabase exposes every `public` table through its Data API (`/rest/v1`). A signed-in user could call it directly with their own token. RLS would hold, but our backend checks would be skipped entirely: the 18+ rule, nutrition computed by code, input validation.
Options: (1) remove `public` from the Data API's exposed schemas, so only our FastAPI backend can reach the tables; (2) keep it and make every write server-only via the admin connection.
Choice: **(1)**. The frontend only needs Supabase **Auth** (`/auth/v1`), which is a separate service and keeps working.
- Done 2026-11-05: Venkat turned off **"Enable Data API"** (Project Settings → Data API) and saved.
- What "off" looks like: Supabase points PostgREST at a placeholder schema `pg_pgrst_no_exposed_schemas` that doesn't exist (PostgREST logs: error `3F000`), so every `/rest/v1` request gets `503 PGRST002`. That's the expected disabled state, not a fault in our schema.
- `tests/db/test_data_api_closed.py` signs in a real throwaway user and checks that a direct `/rest/v1/profiles` request is refused with one of the "closed on purpose" answers (503 PGRST002, 406 PGRST106, or 404). Login (`/auth/v1`) is checked to still work.
- **If the Data API is ever needed again** (for example Supabase Realtime), revisit this decision first.
- Log tables are user-written under RLS; the backend acts as the user (D-025) and computes nutrition before inserting.
- RLS stays on everything as a second line of defence. D-027 server-written tables stay as they are.

## D-029 — How the backend verifies login tokens
**Status:** Accepted (Step 2.8, 2026-11-05)
The project signs tokens with **ES256** (asymmetric). Checked on 2026-11-05: JWKS has one EC P-256 key, and the token header names it.
- `app/core/auth.py` verifies each token against the public keys at `/auth/v1/.well-known/jwks.json`, cached for 1 hour with PyJWT's `PyJWKClient`. No JWT secret needed.
- Only `ES256`/`RS256` are accepted, which rules out `alg: none` and HS256 key-confusion attacks.
- Required claims: `exp`, `iat`, `sub`, `aud`, `iss`. Checks: `aud = "authenticated"`, `iss = <SUPABASE_URL>/auth/v1`, `role = "authenticated"`, not `is_anonymous`, and `sub` is a UUID. Clock tolerance is 30 s.
- `get_current_user` is a FastAPI dependency returning `CurrentUser(id, email)`. It returns 401 with a generic message; the detailed reason is logged only.
- The verified `id` goes straight into `user_transaction` (D-025). User ids are never taken from request data.

## D-030 — Python packages must be at least ~2 weeks old
**Status:** Accepted (Step 2.10, 2026-11-05)
Why: brand-new releases are where most supply-chain attacks and bad releases show up, and they get pulled or fixed within days. The same rule was already applied to the Supabase CLI (D-024).
- `backend/pyproject.toml` → `[tool.uv] exclude-newer = "2026-10-22T00:00:00Z"`: uv ignores any version uploaded after that date, for **every** package, including transitive ones.
- Applying it moved 20 packages back (e.g. fastapi 0.162.0 → 0.159.1, langchain-core 1.7.6 → 1.6.13, starlette 1.10.0 → 1.9.0). All 1024 fast + 146 DB tests pass on the older set. Side effect: starlette 1.9 no longer prints the `httpx2` deprecation warning from Step 0.2.
- LangGraph is pinned exactly: `langgraph==1.2.16`, `langgraph-checkpoint==4.3.0`, `langgraph-checkpoint-postgres==3.2.0`.
- `httpx2` (needed by `langsmith`) was checked: it's published by Tom Christie (author of httpx) from `github.com/pydantic/httpx2`.
- **To upgrade:** move the date forward on purpose (never to today), run `uv lock`, check what changed, run all tests.
- **Frontend too (Step 3.5):** `frontend/.npmrc` has `before=2026-10-22T00:00:00Z` and `save-exact=true`. Five Phase 0 packages were newer than that (tailwindcss and @tailwindcss/vite 4.3.4, @vitejs/plugin-react 6.2.1, oxlint 1.90.0, vitest 5.1.0). They were pinned to the newest older version in the same major, then `node_modules` and `package-lock.json` were rebuilt from scratch so transitive packages follow the rule too. 0 vulnerabilities; tests, build and lint pass. Added: `@supabase/supabase-js` 2.118.0, `react-router` 8.5.0.

## D-031 — Email confirmation at sign-up
**Status:** Accepted (Venkat, 2026-11-05)
Off while developing: Supabase's built-in email sender only allows a few emails per hour on the free plan. **Before friends join:** turn confirmation on and connect a proper email provider (custom SMTP).

## D-032 — Frontend login uses supabase-js for Auth only
**Status:** Accepted (Venkat, 2026-11-05)
The browser uses Supabase's JS client only for sign-up, sign-in and token refresh, then sends the access token to our FastAPI backend (D-029). With the Data API off (D-028), the client can't reach any table directly.

## D-033 — Build the Docker image locally before deploying
**Status:** Accepted (Venkat, 2026-11-05)
Venkat already has Docker Desktop, so the backend image is built and run locally first (fast feedback), then deployed to Render from the same `Dockerfile`.
Implemented (Step 3.9): `backend/Dockerfile` has two stages: `uv sync --frozen --no-dev` in a builder, then a slim runtime with only `.venv` + `app/`. Base `python:3.14.7-slim`, `uv` 0.13.4 (D-030). Runs as non-root `appuser`, listens on `$PORT` (Render) or 8000, `--proxy-headers`, Docker `HEALTHCHECK` on `/health`. `.dockerignore` keeps `.env`, tests, scripts and caches out. Image is 366 MB. Checked locally: health, ready (Supabase reachable), CORS, a real Supabase token on `/me`, onboarding status, a 422 with field list, JSON logs, `healthy` status.
**Render (2026-11-05):** web service `ai-fitness-agent`, https://ai-fitness-agent-5dq9.onrender.com. Docker runtime, branch `main`, region Singapore (nearest to Supabase Mumbai), Free plan, health check `/health`, auto-deploy on commit.
- The build context must be `backend/`. With Root Directory = `backend`, use Dockerfile Path `./Dockerfile` and Build Context `.`. The first deploy failed with `COPY app ./app: "/app" not found` because the context was the repo root.
- Env vars are set in the Render dashboard (never in the image): APP_ENV=production, LOG_LEVEL, CORS_ORIGINS, Gemini x3, Supabase x4, LANGSMITH_TRACING. Render sets PORT.
- The same checks pass there as locally (health, ready, CORS, real token on `/me`, onboarding status, 422).

## D-034 — Who uses the deployed app in Phase 3
**Status:** Accepted (Venkat, 2026-11-05)
Only Venkat, with test data. Before friends: privacy note and consent copy reviewed, data export and account deletion (Phase 10), Gemini billing on, email confirmation on (D-031), DB tests moved off the real project (D-026).

## D-035 — CORS, error format, logs
**Status:** Accepted (Step 3.4, 2026-11-05)
- **CORS:** only the exact origins in `CORS_ORIGINS`. No cookies (`allow_credentials=False`, Bearer tokens only). Methods GET/POST/PUT/DELETE. Headers Authorization, Content-Type and X-Request-ID; X-Request-ID is exposed to the frontend.
- **Errors:** every error is `{"detail": <safe message>, "request_id": ...}`. 422 adds `errors: [{field, message}]` and never echoes submitted values (could be health data). Unexpected exceptions → 500 with a generic message; `PoolTimeout` → 503. The traceback goes to logs only.
- **Logs:** JSON lines on stdout. One `request` line per request (method, path, status, duration_ms, request_id). Never request bodies, query strings, or Authorization headers.
- The request-context middleware is pure ASGI (works with streaming, Phase 7) and sits *inside* CORS, so 500s still carry CORS headers.
- Settings split: `AppSettings` (non-secret, defaults, safe at import) and `Settings` (adds secrets). `app.main` imports without a `.env`.

## D-036 — Frontend on Vercel
**Status:** Accepted (Step 3.10, 2026-11-05)
- Vercel project `ai-fitness-agent`, Root Directory `frontend`, Vite preset, production domain **https://ai-fitness-agent-one.vercel.app** (branch `main`, auto-deploys on push).
- Env vars: exactly three, all public by design, saved as **Config** (not Secret): `VITE_API_URL=https://ai-fitness-agent-5dq9.onrender.com`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`. **Vite bakes `VITE_*` into the JS at build time**, so changing one needs a redeploy. Never give a real secret a `VITE_` name.
- Backend variables were imported into Vercel by mistake and then removed. A scan of the public JS found no secrets (no `sb_secret_`, `AIza`, Postgres URL, pooler host, `lsv2_`, or JWT).
- Vercel's "Supabase integration" was **not** added: it would inject server keys into the frontend project.
- `frontend/vercel.json`: rewrite every path to `/index.html` (SPA reloads work) + headers `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- Render `CORS_ORIGINS=http://localhost:5173,https://ai-fitness-agent-one.vercel.app`. Vercel's other preview domains are intentionally not allowed.
- Supabase Auth Site URL = the Vercel domain, and redirect URLs for it and localhost (needed once email confirmation is on).
- Checked 2026-11-05: full onboarding through production with the Vercel origin (CORS ok on every response), targets match a hand calculation, about 0.5–0.65 s per request (Singapore ↔ Mumbai).

## D-037 — Food data sources
**Status:** Accepted (Venkat, 2026-11-05: "option 2 + 1, and make sure the data is valid and right")
License review (Phase 4 start, not legal advice):
- **IFCT 2017** (NIN-ICMR): © NIN-ICMR, no public reuse license; ICMR terms forbid commercial reuse without permission. → permission needed.
- **INDB** (Jaacks Lab, 2024): the paper is CC BY, but the GitHub data has **no license** (all rights reserved). It is derived from IFCT, and its recipes come from copyrighted cookbooks and blogs. → permission needed.
- **USDA FoodData Central**: public domain (CC0); credit requested. → usable freely.
- **UK CoFID**: Open Government Licence (credit required) for the GOV.UK **file download**; the Quadram CoFID **API** is CC BY-NC-SA, so we don't use it. → usable with credit.
Choice: **2 + 1**.
- Build now on **USDA FDC + UK CoFID** ingredients, plus **our own Indian dish recipes**: ingredient lists in raw grams + cooked yield, drafted by Claude, reviewed by Venkat, nutrition computed by tested code, `source = computed`.
- In parallel, Venkat asks NIN (IFCT 2017) and the INDB authors for permission. If granted, add them as a higher-priority source (the `foods.source` column + unique (name, source) already support several sources).
- Every source is credited in the app ("Data sources").
- Raw downloads are kept out of git (`data/raw/`, re-downloadable). The download script records URL, date and SHA-256 for provenance.
- **Validation is code, with tests** (Phase 4 plan): units and ranges, energy consistency (Atwater 4/4/9 vs stated kcal), macros ≤ 100 g per 100 g, diet-class rules, duplicates, cross-source agreement where both sources have the item, plausibility bands for cooked dishes, and a review report of flagged rows for a human to check.

## D-038 — "Carbs" means available carbohydrate, as weighed; fibre is separate
**Status:** Accepted (Venkat, 2026-11-06)
Problem (found by the Step 4.3a audit): USDA gives **total carbohydrate by difference** (includes fibre); CoFID gives **available carbohydrate in monosaccharide equivalents** (excludes fibre, and is slightly heavier on paper: starch × 1.10, disaccharides × 1.05). Storing both unchanged would mix two definitions in one day's total.
Options: (A) total carbs; (B) available carbs, fibre separate; (C) keep each source's definition.
Choice: **(B)**. `foods.carbs_g_per_100g` = available (digestible) carbohydrate **as weighed**; `fiber_g_per_100g` stored separately.
Why: it matches how our carb **target** is set (remaining calories ÷ 4 = digestible carbohydrate), so logged foods and targets count the same thing.
Conversion (`fooddata/carbs.py`, tested):
- USDA: available = by-difference − total dietary fibre. If fibre is unknown, we can't convert → flagged, not guessed.
- CoFID: as weighed = starch/1.10 + oligosaccharides/1.10 + (glucose + fructose + galactose) + (sucrose + maltose + lactose)/1.05 when the breakdown is known. If only starch and total sugars are known: starch/1.10 + sugars/1.05, marked approximate (a warning in the review report). Otherwise flagged.
Trade-off: differs slightly from the "Total carbohydrate" printed on Indian packaged-food labels (FSSAI); the app labels the figure "carbs (excl. fibre)".

## D-039 — Foods get a stable key; the loader upserts and never deletes
**Status:** Accepted (Step 4.5a, 2026-11-06; Venkat said "go" on the plan)
Problem: meal plans and logs point to `foods.id` (`on delete restrict`), so reloading the food data by deleting and re-inserting rows would break them or change ids.
Options: (A) upsert on the existing unique (name, source); (B) add our own stable `key` (`toor_dal`, `idli`) and upsert on it; (C) delete and reload.
Choice: **(B)**. Migration `20261106120000_foods_key_review.sql` adds `foods.key` (unique, `^[a-z0-9_]{1,60}$`) and `foods.review_status` (`ready` | `review`).
Why: renaming a food (fixing its display name) must not create a second row; (A) would. (C) is impossible once logs exist.
- `uv run python -m fooddata.load` runs in one transaction and is idempotent: a second run updates every row and inserts none (tested). Synonyms are replaced from `local_names` each run.
- Foods removed from the CSV are reported, never deleted.
- Both `ready` and `review` rows are loaded while we use test data; the app can later prefer `ready` foods or show a "values being verified" badge.

## D-040 — Household units: measured USDA portions, standard katori/glass volumes, recipe pieces
**Status:** Accepted with defaults (Step 4.5b, 2026-11-06); **Venkat to confirm the katori/glass sizes**
Problem: people log "1 katori dal" or "2 rotis", not grams. Each unit needs a gram weight we can justify.
How each unit's grams are known (`fooddata/units.py`, `data/food_units.csv`, tested):
- **usda**: a measured portion from USDA SR Legacy `food_portion.csv` (1 large egg = 50 g, 1 tsp oil = 4.5 g). The build checks that the cited portion and grams exist in the USDA file exactly.
- **volume** (katori, glass): standard volume × density from a measured USDA cup weight. Liquid dishes (dal, sambar, curries, kheer) use a prepared vegetable soup (241 g/cup, ≈1.02 g/ml), because USDA's "cooked lentils" cup (198 g) is drained lentils, not dal. Dry sabzi uses cooked mixed vegetables (182 g/cup); rice dishes use cooked rice (158 g/cup).
- **recipe**: the piece size our recipe defines (idli 40 g, dosa 50 g).
Standard volumes: **katori = 150 ml, glass = 250 ml** (one constant, `VOLUME_ML`). Options considered for katori: 100 ml (small), 150 ml (common standard), 200 ml (large). Home sizes vary; the UI should let people adjust portions.
- No unit is guessed: foods without a citable weight (paratha, puri, samosa, gulab jamun, paneer cube) have no unit yet and are logged in grams.
- The loader replaces each food's units on every run (nothing references `food_units`; logs store grams).

## D-041 — Exercise library: curated by us, cross-checked against a public-domain dataset
**Status:** Accepted (Venkat, 2026-11-06: "Curate ~100, cross-check")
Checked 2026-11-06:
- **Free Exercise DB** (github.com/yuhonas/free-exercise-db): **The Unlicense** (public domain, SPDX `Unlicense` per GitHub). 876 exercises with name, level (beginner/intermediate/expert), equipment (sometimes missing), primary/secondary muscles, category, long instructions, images. **No injury/contraindication fields.**
- **wger**: code AGPL-3.0; exercise data "Creative Commons, see individual entries" (licence varies per exercise, some share-alike). → not used.
Options: (1) curate ~100 ourselves and cross-check against Free Exercise DB; (2) import Free Exercise DB and filter; (3) curate with no cross-check.
Choice: **(1)**.
- `data/exercises.csv` (Step 5.2): ~100 common gym + home exercises in our vocabulary (`app/core/vocabulary.py`), our own 2–4 line form cues, and conservative injury (contraindication) tags. No dataset has injury tags, so these are ours: code rules require them for risky patterns, and Venkat reviews them.
- Each row cites a Free Exercise DB id where one exists; code checks the id exists and compares level, equipment and main muscles. We never copy its instructions or images.
- The dataset is pinned to one commit (`f00c92c7dcf1`, 2026-09-27) with SHA-256 in `data/sources.json`, downloaded to `data/raw/` like the food data.

## D-042 — Scope additions requested by Venkat (2026-11-06)
**Status:** Accepted as roadmap items (build order in `PROJECT_BRIEF.md` section 16). Nothing here changes a fixed decision yet; two items need a go-ahead from Venkat when we reach them (marked ⚠).
Requested: (1) user edits their own workout per weekday; (2) an always-on small help chatbot that knows the whole app; (3) workouts chosen by gym experience level; (4) progress statistics for workouts and diet; (5) cuisine choice (Indian first, others later); (6) several workout splits recommended (push/pull/legs, Arnold, upper/lower, full body, ...); (7) a pace question at onboarding (fast/intense, normal, slow); (8) a goal-date prediction after the plan; (9) location/equipment question (gym, home, both); (10) an attractive UI.
Rules that stay in force:
- **Pace never overrides safety (`safety_config.py`).** "Fast and intense" means the fastest rate inside the limits (max 25% deficit, ~1% body weight/week, +10% surplus); it is not a way around them. The prediction uses the same capped rate.
- **Goal date is computed in plain Python** (weight gap ÷ planned weekly rate, from the 7-day trend), shown as an estimate with a range. The LLM only words it.
- **Splits are rules in code** (days per week + experience + location → candidate splits with a reason); the LLM never invents a split or an exercise. The user picks one.
- **User's own edits to their plan apply immediately** (they are the user's decision). Only *agent-made* changes need the approval step. ⚠ Confirm this reading of the "no plan changes without approval" rule when we build it (Phase 6).
- **Help bot answers from a written app guide** (one maintained source file, tested against the real routes), not from the model's memory. It is separate from the coach: it never reads health data and never gives fitness advice.
- **Cuisines:** the foods table gets a `cuisine` column; Indian stays the only cuisine until its data is validated. ⚠ Each new cuisine needs its own licence-checked dataset (same D-037 process), and it changes the "Indian foods" wording in the brief; ask before starting.
- **UI:** shared design tokens and components first, so every new screen looks consistent; full polish in Phase 9.

**Answers (Venkat, 2026-11-06):** (1) Yes: the user's own workout edits apply immediately; only agent-made changes need approval. (2) The design-foundation step comes right after Phase 5.

## D-043 — NVIDIA NeMo Guardrails for input and output guardrails
**Status:** Requested by Venkat (2026-11-06); to be built after Phase 5, before/with the chat flow (Phase 7). **Final design confirmed with Venkat at that step.**
What NeMo Guardrails is: an open-source toolkit that wraps an LLM app with "rails" (input rails, output rails, topic/dialog rails), written as config + Colang flows, with built-in checks for jailbreaks, off-topic requests and self-checks.
Plan: **layered, not replaced.**
1. **Layer 1, code (stays):** crisis/self-harm and eating-disorder patterns, extreme-diet requests, and numeric limits from `safety_config.py`. Deterministic, no LLM, no extra cost. A crisis message must never depend on a model call.
2. **Layer 2, NeMo (new):** input rails (jailbreak/prompt-injection, off-topic, medical-diagnosis and drug/steroid requests) and output rails (banned content, tone, "no diagnosis", self-check of the answer). Its `risk_flag`-style extra check replaces the custom small-model safety check in the brief.
Trade-offs to settle at build time:
- **Cost/latency:** some rails call an LLM. Use the small Gemini model, run LLM rails only when Layer 1 or the router flags risk, and measure with `agent_runs`.
- **Dependencies:** check Python 3.14 support, the `exclude-newer` age rule (D-030), Docker image size on Render's free tier, and `langchain-google-genai` compatibility *before* adding it. If it does not fit, fallback: keep the code guards and implement the same rails as our own small-model checks.
- **Streaming:** output rails need the full text, which already matches D-007 (guard runs before streaming).
- **Testing:** each rail gets eval cases in `evals/` (Phase 7), and results are recorded in PROGRESS.md.
Brief sections 4.2 and 7 are to be updated when this is built.
- **Filing convention (Step 5.2):** the `movement_pattern` list has no slot for isolation moves, so each is filed under the pattern it most resembles (curls → `pull_horizontal`, lateral raises → `push_vertical`, calf raises → `squat`, clamshell → `mobility`). Pattern rules then demand that pattern's injury tags, which can be slightly over-cautious (calf raise is tagged knee). Over-cautious only hides an exercise; it never shows one to an injured user.

## D-044 — Design foundation: tokens, light + dark, shared page frame
**Status:** Accepted (Venkat, 2026-11-06: "Fresh & energetic", light and dark mode)
Options for the look: fresh & energetic (green brand + orange accent), dark & bold, calm & clean. Chosen: **fresh & energetic**, plus **dark mode that follows the phone's setting**.
- **Tokens** (`frontend/src/index.css`): every colour is a named CSS variable (`--brand`, `--ink`, `--surface`...), swapped for dark under `prefers-color-scheme`, and exposed to Tailwind (`bg-surface`, `text-ink`, `border-line`, `bg-brand`, `text-on-brand`...). Screens never use raw palette colours any more, so changing the brand is a one-file edit.
- **Checked by a test** (`src/theme.test.ts`): dark defines exactly the light tokens, and 16 text/background pairs meet WCAG AA (4.5:1) in both themes.
- **Fonts:** Bricolage Grotesque (headings) and Source Sans 3 (text), loaded from Google Fonts with `display=swap` and system-font fallbacks. Trade-off: the browser asks Google's servers for the font, which shares the visitor's IP with Google. If that matters later (privacy notice, paying users), self-host them with `@fontsource` packages (needs the D-030 age check).
- **Shared pieces** (`components/ui.tsx`): `PageShell` (page background, one column, title row, optional Back/action) and `ButtonLink`; used by Home, Meal log and Exercise library. Remaining screens (sign-in, onboarding, sources) already use the tokens through the colour swap and move to `PageShell` as they are touched.
- **Not themed yet:** the macro donut uses fixed colours chosen for colour-blind safety (`targets/macroColors.ts`); checked on light backgrounds only, to revisit with the Phase 9 polish.

## D-045 — How pace changes the calorie target
**Status:** Accepted with defaults (Step 6.1, 2026-11-06); Venkat can tune the table
Pace is a lookup in plain code (`app/calc/targets.py`), per goal, as a fraction of TDEE. "Normal" is the original D-021 value, so nothing changed for existing users.

| goal | slow | normal | fast |
|---|---|---|---|
| fat loss | -10% | -20% | -25% (the deficit cap) |
| muscle gain | +4% | +8% | +10% (the surplus cap) |
| weight gain | +5% | +10% | +10% (normal is already at the cap) |
| recomposition | -5% | -10% | -15% |
| general fitness | 0 | 0 | 0 (no weight change, so no pace) |

Options considered: (a) scale every goal by one factor per pace; (b) an explicit table. Chose **(b)**: each cell is visible, reviewable and tested, and the caps differ by goal.
Rules that make it safe:
- The safety clamps run **after** pace, unchanged: 25% deficit cap, 10% surplus cap, 1% body weight/week, calorie floor, flag caps. A test runs every combination of 5 body types × 4 flag sets × 5 goals × 3 paces and checks no limit is broken.
- **Anyone with a health flag gets at most "normal"** (diabetes, pregnancy, eating-disorder history...). The user is told: "Because of your health answers, we used a normal pace instead of the fastest one." Eating-disorder history still gets no deficit at all.
- The pace used is saved in `calculated_targets.inputs`, so each stored number says what it was based on.
- Pace changes calories only. It does not change protein (which follows body weight) and not yet the workout; training intensity by pace comes with the routine rules.

## D-046 — The help bot can change the user's profile, through a proposal the user approves
**Status:** Requested by Venkat (2026-11-06); design accepted as the default, field tiers to be confirmed
Request: the help bot should update or modify the user's profile when the user asks in chat.
This touches two earlier rules: the help bot reads no health data (D-042), and nothing changes without the user's approval (CLAUDE.md, D-014). Design that keeps both:
- **The bot never writes.** Its only profile tool is `propose_profile_change(field, new_value)`. It creates a pending `profile_change` proposal (the table already exists) and the chat shows a confirmation card with the old value, the new value, and, when numbers would change, the new calorie target worked out by code. The change happens only when the user taps **Approve**.
- **One path to change a profile.** Approve calls the same endpoint as the Profile & settings page (`PATCH /profile`, to be built first), so the bot gets the same validation and the same safety rules as the forms: ranges, 18+, vocabulary lists, pace held to "normal" with a health flag, and a fresh `calculated_targets` row whenever a number-affecting field changes. Today profile steps are locked once onboarding is done (409), so this endpoint is a prerequisite.
- **Fields by tier:**
  1. *Chat + confirm card:* display name, workout location, equipment, days per week, experience level, diet type, cuisine, disliked foods, pace, activity level.
  2. *Chat + confirm card showing the new targets:* weight (logged as a weigh-in), target weight, goal, height.
  3. *Form only:* health screening answers and injury areas. The bot can say "open Health check" and link to it, because a wrong guess here changes safety limits. (A temporary soreness note is handled by the soreness agent, not the profile.)
  4. *Never in chat:* consent, date of birth, email, account deletion.
- **Data the bot sees:** only the field being changed and its current value (a `get_profile_field` tool), never the whole profile or screening answers.
- **Cost:** profile requests are one small-model call to understand the request plus a code-validated proposal; no mid-tier model.
- **Safety text:** the input guard and NeMo rails still run first, so a message like "set my calories to 800" is refused before any proposal exists (targets are calculated, never typed in).
Roadmap: `PATCH /profile` and the settings screen come before the bot tool (Phase 9 "Profile and settings" is pulled earlier, right after the plan screens); the `propose_profile_change` tool is built with the chat in Phase 7/8.

## D-047 — Agent build order, and consistency reminders ("nudges") shown by the help bot
**Status:** Requested by Venkat (2026-11-06); design accepted as the default
**Order:** (1) router + Nutrition, Workout, Progress specialists + help bot + composer + guards (Phase 7, as planned); (2) the soreness/injury agent and the meal swap agent right after; (3) workout logger and "what can I eat now?" later, if wanted.
**Reminders.** When a user is slipping away from their goal, the app says something, through the help bot's widget. Split into the part that decides and the part that talks:
- **Code decides *whether* to nudge** (no LLM): a daily job checks simple rules per user: no meal logged for 2 days; fewer workouts this week than planned by mid-week; no weigh-in for 7+ days; pending plan or check-in proposal waiting; no activity for 5+ days. Each rule has a cooldown, so the same nudge is never repeated within a few days, and at most **one nudge a day**.
- **Words are templates first.** A nudge is a short, kind, fixed sentence per rule ("You haven't logged a meal since Monday. Want to log today's lunch?") with a one-tap action. An LLM (small model, one short call) is optional later, only to vary the wording; it never decides who gets a nudge or what is true.
- **Channels:** in-app first (a badge on the widget and a message when it opens). Email, push or WhatsApp are a later step because each needs a provider, cost and separate consent. Nothing is sent outside the app without the user turning it on.
- **Respect and safety:** consent and an off switch in settings (per type and all); quiet hours; no shaming or guilt wording; users with an eating-disorder history get habit nudges only (no calories, weight or "you're behind" wording); no nudges for 7 days after a user dismisses three in a row.
- **Running it:** the job needs a scheduler. Render's free web service sleeps, so it can't run its own timer; a scheduled trigger (Supabase `pg_cron`, GitHub Actions or Render cron) calls one protected backend endpoint once a day. Decide which at build time.
- **Data:** a `nudges` table (user, rule, text, created, seen, dismissed, acted) with RLS; the same table feeds the "pending proposals" badge on the dashboard.
- **Tests:** each rule is a pure function over dates and logs (unit tested), plus cooldown, daily cap, opt-out, and eating-disorder wording tests.

## D-048 — Workout splits: a fixed catalogue and transparent ranking, in code
**Status:** Accepted with defaults (Step 6.2, 2026-11-06); Venkat can tune the table
The model never invents a split. `app/calc/splits.py` holds 10 splits (full body 1/2/3/4 days, push-pull-legs 3 and 6 days, upper/lower 4, upper/lower + PPL 5, body-part 5, Arnold 6). Each lists its training days, the muscles and the movement patterns of each day (the library's own vocabulary, now shared in `app/core/vocabulary.py`).
Ranking rule (visible, tested): candidates are the splits with exactly the user's number of training days (7 days = a 6-day split plus one easy recovery day). Score = level suitability (0 too demanding, 1 works, 2 well suited; a fixed table per split) + 1 if each muscle is trained twice a week or more. "best" = top score (and at least 2), "good" = 2 or more, "possible" otherwise. Reasons and cautions are generated from the same facts (days, frequency, level, goal), so the wording is always true to the numbers.
Options considered: (a) let the LLM propose splits; (b) a fixed catalogue with a score. Chose **(b)**: predictable, testable, and the plan generator needs a known structure to pick exercises for.
Not decided yet: home- or equipment-specific splits. The frequency rule is a rule of thumb, not medical advice.

## D-043 addendum — NeMo Guardrails compatibility check (2026-11-06)
Tried in a throwaway environment outside the project (nothing was added to `pyproject.toml`):
- **Python 3.14:** `nemoguardrails 0.24.1` resolves and installs with our D-030 cutoff (2026-10-22), alongside our pinned packages (57 → 105 packages), and imports. Caveat: PyPI's page lists support for Python 3.10–3.13 only, so 3.14 is unofficial: pin the exact version and re-run our tests on every upgrade.
- **Size and memory:** about +100 MB of installed packages (numpy, onnxruntime, fastembed and friends), about +60 MB of memory and 3 s to import. The embedding model was not loaded in checker-only mode. Render's free tier has 512 MB, so watch memory when it is added.
- **Checker-only mode works:** with `options={"rails": ["input"]}` / `["output"]` NeMo only runs our input or output rails and leaves the answer to our own LangGraph. A rail written as a Python action (no LLM) blocked "500 calories a day" and a banned word in 10–25 ms and passed normal text through unchanged. Default mode (NeMo writing the reply itself) needs an LLM, so we never use it.
- **Not tested yet:** the built-in LLM-based rails (self-check, jailbreak, topic checks) with Gemini through `langchain-google-genai`. Needs the Gemini key and a measured cost; done when the chat is built (Phase 7).
- **Honest scope:** for plain pattern checks our own Python functions are just as good. NeMo earns its place with the LLM-based rails and readable Colang rules. Layered plan from D-043 stands: crisis, extreme-diet and numeric limits stay as code; NeMo adds the LLM-judged rails, run only when flagged.

## D-049 — Routine rules: sets, reps, rest and progression by level, goal and pace
**Status:** Accepted with defaults (Step 6.4, 2026-11-06); Venkat can tune the tables. These are common coaching rules of thumb, not medical advice.
`app/calc/routine.py`, plain code. Each exercise is one of four kinds: **compound** (works 2+ muscle groups), **isolation** (one muscle group: curls, lateral raises, calf raises), **core**, or **timed** (planks, wall sit, holds: 1 rep, the hold length goes in the note). Cardio and mobility are timed work, so they get no sets/reps here; the plan generator will give them minutes.
- **Sets** (before pace): beginner 2 for everything; intermediate 3; advanced 4 on compound lifts, 3 otherwise. Pace: slow −1; fast +1 on compound lifts for intermediate and advanced only. Always kept between 2 and 5 (the plan table allows 1–10).
- **Reps:** beginners get the same moderate range for every goal (compound 8–12, isolation and core 10–15) while they learn technique. Others: muscle/weight gain compound 6–10; recomposition, fitness and fat loss compound 8–12; isolation 10–15 (fat loss 12–15); core 10–15 (fat loss 12–20).
- **Rest:** compound 90 / 120 / 150 s (beginner / intermediate / advanced), 30 s less for fat loss, recomposition and general fitness; isolation 60 s; core and holds 45 s.
- **Progression** (double progression): keep the weight until every set reaches the top of the rep range, then add 2.5 kg (upper body) or 5 kg (lower body). Two sessions in a row with a set below the bottom of the range → take off 10%, rounded **down** to the nearest 0.5 kg, so a reduction is never heavier than intended. One bad session changes nothing (sleep, stress). We never invent a starting weight: with no history the user picks one they can lift comfortably. Bodyweight exercises progress by making the movement harder, not by weight.
- **Safety link:** `prescribe` takes the pace actually used (after `effective_pace`), so people with a health flag never get the extra "fast" set.
- **Tests:** hand-worked values for each rule, every level × goal × pace combination checked against the plan table's limits, and every strength exercise in our real library gets a valid prescription (exactly five are timed: plank, side plank, hollow body hold, Superman hold, wall sit).

## D-050 — Goal-date prediction: a week-by-week replay of the plan, shown as a range
**Status:** Accepted with defaults (Step 6.5, 2026-11-06); Venkat can tune the adherence numbers
`app/calc/forecast.py`, plain code, no LLM. It replays the plan week by week with the same engine that sets the calorie target, so every safety limit applies (D-045 pace, deficit and surplus caps, 1% weekly loss cap, calorie floor, flag caps).
- Each week: weekly change = (calorie target − TDEE) × 7 ÷ 7700 kcal per kg; new weight = old weight + change × adherence; then TDEE and the target are recalculated for the new weight. TDEE falls as weight falls, so progress slows. A fixed "0.5 kg a week" would be too hopeful.
- **A range, never a promise:** earliest = follow the plan fully (100%), likely = 85%, latest = 70% of the time. The Home card shows the likely date and the range, with the line "This is an estimate."
- **When there is no date, we say why instead of inventing one:** no target weight, or a goal that doesn't aim at a body weight (general fitness, recomposition); already within 0.5 kg; target on the wrong side of the goal (fat loss with a target above today's weight); the plan, held within safe limits, doesn't move the weight toward the target (for example a small person whose 1200 kcal floor is above their maintenance); more than two years away at a safe pace.
- **Eating-disorder history gets no weights and no dates** (habits only), like the calorie numbers (brief section 7).
- Energy per kg is 7700 kcal (D-022), also for gains; real gains are a mix of muscle and fat, so for gain goals the date is rougher still.
- Worked example (80 kg man, TDEE 2759, normal pace, 75 kg target): 71 days earliest, 84 likely, 102 latest; slow pace 142 / 167 / 203 days; fast 57 / 67 / 81 days.
- **Test hygiene lesson:** a database test I wrote updated goals with no user filter, which would have changed every real user's goal. The tool's safety check refused to run it. All DB tests that update or delete must filter by the scratch user's id.

## D-051 — One LLM module: tiers from .env, required max_tokens, own retries, every call logged
**Status:** Accepted (Step 6.6a, 2026-11-06)
`app/llm/` is the only code that knows about Gemini (`client.py`, `pricing.py`, `runs.py`), so the provider can be swapped later.
- **Tiers:** "small" and "mid" read model IDs from `GEMINI_SMALL_MODEL` / `GEMINI_MID_MODEL`; no ID in logic. Both are `gemini-2.5-flash` today (D-015), which Google retires on 2026-12-01: change `.env` before then.
- **`max_tokens` is required** and must be positive, so no call can run away.
- **We retry ourselves** (LangChain's retry is off): up to 3 retries after 1, 3 and 8 seconds plus jitter, only for 429 / quota / 503 / overloaded. Still failing: `LLMBusy` ("The coach is busy right now..."). Any other error: `LLMFailed` with a generic message; the real error goes to the logs only (it could contain a key).
- **Every call is logged** to `agent_runs` (tokens, cached tokens, estimated cost, latency, status). Logging can never fail a user's request. Only the final outcome of a retried call is logged.
- **Cost is an estimate** from a price table in code (paid-tier text prices). An unknown model is billed at the highest known price so a surprise never looks cheap.
- **Not done yet:** Gemini context caching (CLAUDE.md says use it only where it really saves money; system prompts are still short) and LangSmith tracing; both are revisited when the prompts grow (Phase 7).
- Verified with two real calls (small and mid): reply "ready", 8 in / 18 out tokens, about $0.00005 each.

## D-052 — Exercise picking: the model chooses keys, code decides what is allowed
**Status:** Accepted (Step 6.6b, 2026-11-06). Venkat chose the recommended "stable" option.
`app/calc/day_picks.py` (rules), `app/llm/picker_prompt.py` (prompt + parsing), `app/workflows/pick_exercises.py` (the loop).
- **Candidates per day (code):** from the exercises already filtered for this user (injuries, level, place, equipment), a day gets those whose movement pattern is one of the day's patterns AND that train one of the day's muscles. Blocked exercises are never used. Exercises still in "review" status ARE allowed (none are signed off yet; the library screen shows them as unverified). Revisit when Venkat signs off the injury tags.
- **Exercises per day:** beginner 4, intermediate 5, advanced 6 (fewer if the library has fewer).
- **The model (mid tier, temperature 0, JSON only):** gets only our own exercise list (key, name, muscles, pattern), the day labels, level and goal. No user free text and no health data go in, so there is nothing to inject. It is told not to write numbers; any numbers are ignored anyway (sets/reps/rest come from D-049 in 6.6c).
- **Validation (code):** every key must be in that day's list, no repeats, exactly the wanted count, no more than 3 from one movement (more for a day with one movement, like a chest day), and enough different movements. A day that fails is re-asked ONCE with the reasons (only the failed days, to save tokens). If it still fails, or the model is down or rate-limited, code picks (round-robin over the day's movements, big lifts first, easiest first, avoiding exercises used on other days). So a plan is always complete and valid.
- **Order is fixed by code:** big compound lifts, then single-muscle work, then core. The model's own order is kept inside each group.
- **A day with no allowed exercise** (e.g. a home user with no equipment on a leg day) is reported as "none" with a plain note, never filled with something unsuitable.
- **Stable on purpose (temperature 0):** the same inputs gave the identical week on three real runs. Variety can be added later (a "swap this exercise" action is planned).
- **Real-run check:** intermediate gym user with a knee injury, PPL: 68 of 102 exercises allowed; the leg day got hinge/hip work and no squats or lunges. Beginner at home with no equipment: 28 allowed; days A and C share two exercises because the pool is small. Cost about $0.001 per week-plan pick.
- The Gemini reasoning tokens count toward `max_tokens`, so the picker allows 4000.

## D-053 — A generated workout is a pending proposal; code lays out the week and sets the numbers
**Status:** Accepted (Step 6.6c, 2026-11-06)
`app/calc/workout_plan.py`, `app/workflows/generate_workout_plan.py`, `app/db/proposals.py`, `app/api/plans.py`.
- **Endpoints:** `POST /plans/workout/generate` (one mid-tier model call, about 13 s with Gemini 2.5 Flash, so the screen needs a loading state) and `GET /plans/proposals/pending`. The result is a `plan_proposals` row (type `workout_change`, source `plan_generation`, status `pending`). **No `workout_plans` row exists until the user approves (Step 6.6d).**
- **Payload** (versioned JSON): split, week start, level, goal, an optional doctor note, and seven days (Monday to Sunday). Each training day lists exercises by stable `exercise_key` (not database id) with position, sets, reps min/max, rest and a note. Keys are mapped to ids on approval.
- **Week layout is fixed in code:** 1 day → Wed; 2 → Mon, Thu; 3 → Mon, Wed, Fri; 4 → Mon, Tue, Thu, Fri; 5 → Mon, Tue, Wed, Fri, Sat; 6 → Mon to Sat. The plan starts on the coming Monday (today if it is Monday). The user can move days later (weekday editing is a separate roadmap item).
- **Numbers come only from `prescribe()` (D-049)** using the effective pace. **Health flags** (any screening flag) make the plan more conservative: one set fewer per exercise (never below 2) plus a "check with your doctor" note on the plan (brief section 7).
- **Cardio and mobility are skipped** (they have no prescription yet). Timed holds (plank, wall sit) are stored as 1 rep with the note "Hold 30-45 seconds"; the screen must show the note, not "1 x 1".
- **Validated twice:** `validate_payload` runs before saving (a failure is our bug, so it raises and saves nothing) and will run again when the user approves. It checks seven days in order, 1 to 10 exercises on training days, no duplicates, positions, sets 1-10, reps, rest 0-600, and that every key is in the library.
- **Too few exercises means a refusal, not a thin plan:** a training day needs at least 3 possible exercises (`MIN_DAY_EXERCISES`). Found by testing: with every injury ticked, only 2 of 102 exercises were allowed and the picker would have produced a one-exercise day. The user now gets a 409 naming the days and no proposal is saved.
- **Double-tap protection:** a pending proposal for the same split made in the last 60 seconds is returned instead of calling the model again. A newer generation expires the older pending one (status `expired`), so there is at most one pending generated workout per user.
- **Nothing sensitive in the model call** (D-052); no database transaction is open while the model thinks.
- Real run: intermediate gym user, upper/lower 4 days: 20 exercises, all four days chosen by the model, rules applied by code, cost under a cent.

## D-054 — Approving a proposal: one transaction, checked twice, only workouts for now
**Status:** Accepted (Step 6.6d, 2026-11-06)
`app/workflows/decide_proposal.py`, `app/db/workout_plans.py`, `POST /plans/proposals/{id}/approve` and `/reject`.
- **Approve is one all-or-nothing transaction:** lock the proposal (`for update`, so two taps cannot both apply it) -> check it is this user's and still pending -> re-run `validate_payload` against the library -> archive the user's active plan -> write the new plan, its 7 days and its exercises as `active` -> mark the proposal approved. Any failure rolls everything back.
- **Ownership is checked in code**, because the admin connection bypasses RLS: every query filters by `user_id`. Someone else's proposal gets 404, the same as one that doesn't exist (no hint it exists).
- **The stored plan is not trusted:** it is validated again at approval. A tampered plan (invented exercise) gets 422 "did not pass our safety checks", nothing is written, and the proposal stays pending.
- **Only `workout_change` can be applied.** Other types get 422 "cannot be approved yet" and stay pending; they are never silently marked approved. Each type gets its own apply code in its own step (meal plan, profile change, weekly adjustment).
- **Stale start date:** if the planned Monday's week is over by the time the user approves, the plan starts on the coming Monday. Approving in the planned week keeps the planned Monday.
- **Versions:** one active plan per user (database rule). A second approval for the same Monday archives the first and is version 2.
- **Reject** marks the proposal rejected and changes nothing else; a decided proposal gives 409 if decided again.

## D-055 — The workout plan screen: proposal first, plan second
**Status:** Accepted (Step 6.6e, 2026-11-06)
`/workout` (`frontend/src/plans/`), `GET /plans/workout/active` (reads under RLS, no LLM).
- **A pending proposal is shown above everything else**, in a highlighted card with Approve and Reject, and is labelled as not yet your plan. Approving reloads the page and shows it as "Your plan". Rejecting keeps the current plan.
- **Generating takes about 15 seconds**, so the button is disabled and says "Building your plan…" with a status line. Errors (not ready, coach busy) show the backend's message; "not ready" also links to choosing a split or to onboarding.
- **Holds are shown as time** ("3 × Hold 30-45 seconds"), never "1 reps". Rest of 60 s or more in whole minutes shows as minutes (2 min).
- **The reps-in-reserve reminder** ("Stop each set with 2 good reps left in the tank") is shown once above the week, not on every line. Form cues sit in a "How to do it" fold-out on the active plan only (a proposal does not carry them).
- Home gets a "Workout plan" button. Replacing a plan means asking for a new one ("Make me a new plan"), which goes through the same approval.

## D-056 — No exercise library screen; the split work gets three upgrades
**Status:** Accepted (2026-11-06), Venkat's request
- **The Exercise library screen (Step 5.5) is removed from the app.** Users get a split and a plan, they don't need to browse exercises. The exercise data, filter and `GET /exercises` stay in the backend: plans use them, and "swap this exercise" / weekday editing will need them. The "Exercise library screen" line in the brief (section 6) is no longer a user-facing page.
- **Three upgrades chosen to make splits more effective** (each is its own small step, in this order):
  1. **Time per session** (6.6f): a new Training question (30 / 45 / 60 / 90 minutes). Code turns minutes into the number of exercises per day (today fixed by level at 4/5/6) using set count and rest time, so a 30-minute user gets a short session that fits.
  2. **Focus areas** (6.6g): the user names up to two muscle groups to bring up. Those get extra exercises and one more set; everything else stays at maintenance volume. Capped in code so total weekly volume stays safe.
  3. **Auto-progression and deloads** (needs workout logs, so it lands with Phase 8 logging): the double-progression rules (D-049, already built) raise weights/reps from logged sessions, and an easier deload week is scheduled every 4 to 6 weeks.
- Not chosen for now: goal-shaped cardio finishers and denser fat-loss sessions. Can be added later.

## D-057 — Time per session decides how many exercises a day has
**Status:** Accepted (Step 6.6f, 2026-11-06)
`app/calc/session_time.py`, migration `20261106200000_session_minutes.sql`, a new question in the Training step.
- **The question:** "How long can a workout last?" 30 / 45 / 60 / 90 minutes, required for new users. Stored as `profiles.session_minutes` (nullable; an account made before the question is planned as 60 minutes).
- **The rule (code, from the routine rules in D-049):** minutes minus a 5-minute warm-up is the budget. Each exercise costs sets × (40 s of work + its rest) + 30 s setup. We add exercises in a typical order (two big lifts, then single-muscle work with a core exercise in the middle, then more) until the next one no longer fits. Sets and rest depend on level, goal and pace, so a hard-training advanced user fits fewer exercises in the same time than a beginner.
- **Limits:** never fewer than 3 exercises, and never more than 5 for a beginner, 7 for intermediate, 8 for advanced (more time is not more exercises for a beginner). Results for muscle gain at normal pace, for 30 / 45 / 60 / 90 minutes: beginner 5, 5, 5, 5; intermediate 3, 6, 7, 7; advanced 3, 4, 6, 8.
- **Each plan day shows "about N min"**, estimated from its real sets and rest and rounded to 5 minutes (a day with the minimum of 3 hard exercises can run a little over a 30-minute wish; the estimate shows that honestly).
- This replaces the old fixed 4 / 5 / 6 per level as the normal path (the fixed numbers remain only as the fallback inside the picker when no count is given).
- Health-flag plans still take one set off each exercise, so they come out slightly shorter than estimated, never longer.
- Existing accounts can only change their answer once Profile & settings exists (roadmap); until then they get 60.

## D-058 — The frontend design pass happens after the backend is finished
**Status:** Accepted (2026-11-07), Venkat's request
- Venkat will provide one large design prompt for making the frontend attractive. Only its frontend and visual-design content is used; any backend instructions in it are ignored.
- The redesign starts only after the backend roadmap is complete (plan generation, chat and agents, check-ins, logging, stats data). Until then new screens stay simple and use the existing design tokens (D-044), so the later pass has a consistent base to restyle.
- The prompt arrived 2026-11-07 and is saved word for word in `docs/DESIGN_BRIEF.md` (Part 2), with an analysis (Part 1): what we use as written, 7 clashes with fixed project rules for Venkat to decide (exercise/food images, the removed exercise library, a mic button, dark-only vs light + dark, LLM vs code for daily insights, fonts), and which widgets need backend data first. It becomes the F phase, in small steps.

## D-059 — Answers to the design brief's seven clashes (Venkat agreed, 2026-11-07)
**Status:** Accepted. These apply to the F phase (frontend redesign, D-058); see `docs/DESIGN_BRIEF.md` Part 1 B.
1. **No exercise images or anatomy drawings.** Clean muscle-group icons and the text form cues (CLAUDE.md: no exercise videos or images).
2. **No food photos.** Category icons and colour chips. One or two licensed or self-made hero visuals on the landing page only.
3. **No exercise library screen** (D-056).
4. **No microphone button** until voice is a real feature (no controls that do nothing).
5. **Dark only** (black + neon lime). The earlier light + dark choice (D-044) is superseded when the redesign lands; until then the current tokens stay.
6. **Daily insights are code rules** over today's real numbers, styled as "AI". No model call (cost rule: never call the LLM for what code can do).
7. **One self-hosted font** (Manrope proposed) so visitors' IPs don't go to Google. Needs the D-030 age check on the `@fontsource` package.
- **Water tracker: yes**, added to the backend roadmap after Phase 8 logging (a water log table, a daily target computed in code, quick-add buttons).
- **Body composition: no for now** (body-fat is hard to measure reliably; a wrong number is worse than none).
- **Notifications bell: yes**, but only once the reminders feature (D-047) exists.
- **Every number on a redesigned screen must be real data.** Where data doesn't exist yet, the screen shows a designed empty state, never a fake chart.
- **Effects are used sparingly** (glow, particles) and tested on a mid-range phone; reduced-motion is always respected.

## D-060 — Focus areas: up to two muscles to bring up, extra volume inside a hard cap
**Status:** Accepted (Step 6.6g, 2026-11-07)
`app/calc/focus.py`, `profiles.focus_areas` (migration `20261107120000_focus_areas.sql`), `GET/PUT /training/focus-areas`, a chip picker on the Workout plan page.
- **Choices:** chest, back, shoulders, biceps, triceps, quads, hamstrings, glutes, calves, abs; at most two. Checked in the API, in code (`check_focus`) and by a database check. Venkat's earlier muscle list (chest, back, shoulders, biceps, triceps, legs, abs, traps) maps onto these; "legs" is split into quads, hamstrings, glutes and calves because they are trained differently. Traps are left out of focus (they are trained by pulls already).
- **What a focus muscle gets (code only):** (1) a day that trains it gets one more exercise (never above 8); (2) each exercise that trains it gets one more set, in week order, never above 5 sets, and only while every focus muscle that exercise trains stays within the weekly cap; (3) the picker is told the priority muscles and the code fallback prefers those exercises.
- **Weekly cap:** `MAX_WEEKLY_SETS_PER_MUSCLE = 20` in `safety_config.py`. Focus can only add sets up to this; a compound lift counts for each focus muscle it trains. The cap limits what focus adds; it does not trim the base plan (a high-frequency split can already be near it).
- **Users with a health flag get no extra volume** (conservative, like the one-set-fewer rule). Their plan records an empty focus.
- **Where it is chosen:** on the Workout plan page right before generating, so accounts that finished onboarding earlier can use it. Saved immediately, used the next time a plan is made. Onboarding is not changed.
- The plan payload records `focus_areas` and `focus_sets_added`; day length ("about N min") is worked out after the extra sets, so it stays honest.

## D-061 — Engineering showcase: the backend should use real, advanced AI-engineering techniques
**Status:** Accepted (Venkat, 2026-11-07, "go with your recommendation"). **Firm commitments: 1, 2, 3 and 6.** Stretch goals: 4 (hybrid retrieval) and 5 (adaptive estimation). 7 and 8 are picked up as their phases arrive.
**Goal:** the main purpose of the project is a portfolio piece that looks like an AI engineer built it, not a normal CRUD app with a chatbot. **Rule that keeps it honest:** every technique must (1) solve a real problem in this app, (2) have a measurable benefit, (3) have tests or evals, and (4) be visible (a trace, a metric, a "how this was made" panel). No buzzword stacking. The non-negotiables stay (the LLM never does math or invents foods and exercises).

Candidates, each mapped to a step where it fits naturally:
1. **"LLM selects, solver computes" for meal plans (6.7).** The model chooses dishes from the food database; a constraint solver (linear programming) sets portions to hit calories and macros inside the safety limits, with household-unit rounding. A verify-and-repair loop retries with the solver's feedback. Replaces hand-tuned portion rules with an optimiser.
2. **LangGraph with human-in-the-loop (Phase 7).** A supervisor/router and parallel specialists (Send API), proposals created inside the graph, and `interrupt()` pausing for the user's approval, resumed from the Postgres checkpointer (already set up). Approval becomes part of the graph, not an afterthought.
3. **Evals with a regression gate (Phase 7).** Golden datasets and adversarial cases (injury violations must be 0, safety-limit breaches must be 0, constraint satisfaction rate, fallback rate, cost and latency per plan), programmatic checks plus an LLM judge where needed, run in CI so a prompt or model change that makes plans worse fails the build. Includes a red-team set for the NeMo Guardrails rails (D-043).
4. **Hybrid retrieval (RAG) with citations.** Postgres full-text + pgvector embeddings + a reranker, used for (a) parsing "2 rotis and dal" into foods and (b) grounding the help bot in our own docs and a small curated nutrition/training knowledge base, with sources shown.
5. **Adaptive estimation from logs (Phase 8).** Smooth the weight trend (exponentially weighted / Kalman-style) and estimate the user's real TDEE from logged intake vs weight change, so weekly adjustments use evidence instead of formulas alone. Pure code, unit-tested.
6. **Observability that is visible.** LangSmith traces plus our `agent_runs`, a per-plan "How this plan was made" panel (which days the model chose vs code, checks passed, repairs, tokens, cost, latency), and a small admin view of cost per day and eval scores.
7. **Reliability engineering.** Idempotent generation (already started), Gemini context caching where it saves money, a per-user token budget, a circuit breaker on the provider, and graceful fallbacks (already the pattern).
8. **Layered safety.** NeMo input/output rails, prompt-injection defences on all user text that reaches a model, PII-free prompts (already true), and the code-owned limits.

Later (Venkat said yes to A2A on 2026-11-07): **A2A (Agent2Agent protocol)** after Phase 7: publish an Agent Card and expose the coach as an A2A server (an adapter over the existing LangGraph graph), and optionally call outside agents. Check the current A2A spec before building. Also optional: expose the app's tools as an MCP server; offline replay of traces to compare model versions.

## D-062 — Meal planning, step 1: a role-based food pool (no LLM)
**Status:** Accepted (Step 6.7a, 2026-11-07). First step of the "LLM selects, solver computes" meal planner (D-061 technique 1). Venkat chose a full 7-day plan with variety.
`app/calc/meal_pool.py` (rules), `app/db/meal_foods.py` (reads foods + synonyms + household units), `scripts/pool_report.py`.
- **Four meals a day:** breakfast, lunch, evening snack, dinner, carrying 25 / 35 / 10 / 30 % of the day's calories (the solver aims for these). The table also has `mid_morning`; generated plans do not use it yet.
- **A meal is built from roles**, so a plan looks like real Indian meals: lunch and dinner = staple (rice or bread) + protein (dal, rajma, kadhi, curry, paneer, egg, boiled chana/egg/chicken) + vegetable dish (sabzi) + optional side (curd, chaas, raita, boiled potato); breakfast = a main (idli, dosa, upma, oats, bread, egg) + an optional extra (fruit, curd, milk); snack = one item (fruit, nuts, curd, chaas, boiled chana).
- **Filters, all in code:** diet type (a food's `diet_class` is the strictest diet that can eat it; vegetarians never see egg or meat, vegans never see dairy), dislikes (case-insensitive match on the name and local names), and category. **Left out on purpose:** sweets and fried snacks (a "treat" rule can add them later), spices, oils, sweeteners, and raw meat and fish (raw versus cooked weight is ambiguous; cooked dishes cover non-veg protein), and raw ingredients (not meals).
- **Foods whose numbers are still "review" are allowed** but listed after verified ones (same approach as exercises); the plan screen will show which foods are unverified.
- **Thin choices are reported, never hidden:** a role with fewer than 3 options is flagged (`thin`), and a required role with none is `missing`. The generator must refuse or warn, not invent.
- **Finding on the real data (pinned by a test):** vegetarian, eggetarian and non-veg diets have plenty of choice everywhere. **Vegan is thin**: 4 protein and 3 vegetable dishes for 14 lunches and dinners, so a vegan week will repeat dishes. Fix = add vegan recipes (data work, `data/recipes.csv`), not code. Tracked as an open item.
- 17 dishes have no household unit (paratha, puri, omelette, chicken...): the solver (6.7b) will portion them in grams rounded to 10 g.

## D-063 — Specialists are ephemeral: built per task from a spec, given a tool allowlist, gone when done
**Status:** Accepted (Venkat, 2026-11-07: "specialists are created to accomplish the task, we assign them tools, and after the task is completed they vanish"). Built in Phase 7; this is the orchestrator-worker pattern with an agent factory (D-061 technique 2).
- **A specialist is a spec, not a process.** `SpecialistSpec`: name, system prompt, model tier (small by default; mid only for plan generation and adjustments), a **tool allowlist**, an output schema, `max_tokens`, a step limit. A **factory** turns a spec into a runnable agent for one task. When the task ends, the agent and everything it held are discarded.
- **Tools live in one registry.** Each tool is a typed function (Pydantic arguments) with a scope: `read` (look something up), or `propose` (create a PENDING proposal). **No tool applies a change**; only the user's approval does (CLAUDE.md rule). Our existing calculators become tools (portion solver, targets, forecast, exercise filter, food search).
- **The harness, not the model, owns identity and limits.** `user_id` is injected by the harness from the verified login and is never an argument the model can set; tools run under `user_transaction` (RLS). A specialist can call only the tools on its allowlist (anything else is refused and logged). Each run has a step limit, a token budget and a timeout.
- **State lives outside the agents:** in the Postgres checkpointer and the database. Nothing carries over between two spawns of the same specialist (tested).
- **One user message = one loop:** the router classifies -> the needed specialists are spawned in parallel (LangGraph Send API) -> they return structured results -> the composer writes one reply (skipped when only one specialist ran, a cost rule) -> state saved -> everything vanishes. The next message repeats the loop.
- **Visible:** every spawn is an `agent_runs` row (node = specialist name, tools used, tokens, cost, latency) and a LangSmith trace, and appears in the "How this was made" panel (D-061 technique 6).
- **The specs are predefined by us; only the instances are created dynamically.** The menu (nutrition, workout, progress, help bot, later soreness and meal swap) is written, reviewed and tested by us. The router picks from the menu and the graph decides how many copies run (for example one day-planner spec run 7 times in parallel). The model never writes a prompt, a tool or an allowlist at runtime: permissions and safety limits must be human-written and covered by evals. Stretch goal after Phase 7: a **planner** specialist that returns an ordered plan built from the predefined specs (plan-and-execute), validated by the harness against the menu before running.
- **Honest detail:** "vanish" means per-task state is discarded. The compiled agent object may be reused between tasks because it is stateless.
- **Planned Phase 7 order (each its own step):** 7.1 tool registry + specialist factory, tested with a fake model (no LLM, enforcing allowlist, user_id injection, step limit, no state leak); 7.2 first real specialist (food lookup/nutrition) with Gemini; 7.3 router + parallel spawn; 7.4 composer; 7.5 human-in-the-loop approval of proposals via LangGraph `interrupt()`; 7.6 NeMo Guardrails (D-043); 7.7 evals (D-061 technique 3). Help bot (D-046) and the soreness and meal swap specialists (D-047) are added as new specs, not new machinery.
- **Why this prepares today's work:** the meal portion solver (6.7b) is written as a plain, typed function so it can become a tool unchanged.

## D-064 — Dynamic agents: a planner now, bounded ad-hoc agents after the evals
**Status:** Accepted (Venkat, 2026-11-07). Both are committed stretch goals AFTER the Phase 7 core (D-063); the predefined specialists stay the core.
Question asked: "can the LLM create agents depending on the requirements?" Answer: yes, but only in a bounded form, because a model that picks its own tools can widen its own permissions (prompt injection), cannot be evaluated in advance, and our domain is health data.
1. **Planner (dynamic composition).** A planner specialist turns a messy request ("I'm travelling for a week, adjust everything") into an ORDERED PLAN of predefined specs. The harness validates the plan against the menu (only known specs, sensible order, size limit) before running anything. No new permissions are created.
2. **Bounded ad-hoc agents (dynamic creation inside a locked template).** For read-only long-tail questions (analysis and explanation across logs and plans) an agent-builder LLM writes a spec, but the harness enforces:
   - a fixed safety preamble is always prepended (the model cannot remove or edit it);
   - requested tools are INTERSECTED with a read-only allowlist; propose tools are never granted;
   - limits (steps, tokens, timeout) are capped by the harness; the model can only ask for less;
   - same output schema, guardrails (NeMo) and logging as any specialist; small model only;
   - an ad-hoc agent can NEVER create proposals: a change must go through a predefined, tested specialist and the user's approval;
   - marked "ad-hoc" in the "How this was made" panel and in `agent_runs`.
   **Gate:** built only after the eval harness (7.7) exists, with a red-team set (injection attempts to widen tools, to remove the preamble, to request writes, runaway limits). Without those results it does not ship.
- Order: predefined specs (7.1 to 7.6) -> evals (7.7) -> planner -> bounded ad-hoc agents.

## D-065 — Meal planning, step 2: the portion solver (mixed-integer linear programming, no LLM)
**Status:** Accepted (Step 6.7b, 2026-11-07). "The LLM selects, a solver computes" (D-061 technique 1).
`app/calc/meal_solver.py`, `app/calc/meal_portions.py`, `scripts/solver_demo.py`; `scipy` (HiGHS) added as a dependency (1.18.1, passes the D-030 age rule; about 35 MB, remember for the Docker image).
- **Unknowns are whole numbers of household steps**, so every amount is measurable and nothing is rounded afterwards: pieces (roti, idli, egg, fruit), half-katoris (dal, rice, sabzi), half-glasses (milk, chaas), or 10 g steps (5 g for nuts). A piece smaller than 15 g (an almond, 1.2 g) is not a meal unit and falls back to grams. Each food has a minimum and maximum number of steps, and **side dishes, breakfast extras and snacks are capped by role** (about 260 to 300 g) so they cannot grow into a second meal. Found on real data: the first version produced 2 glasses of milk plus 2 glasses of buttermilk and "2 almonds (2.4 g)".
- **Hard limits (never traded away):** calories in a band of plus or minus 4% around the target **built with the engine's own `apply_safety_clamps`** (calorie floor, deficit and surplus caps, weekly-loss cap, health-flag caps), so `safety_config.py` stays the only source of safety numbers; protein never above its cap (the kidney flag caps it at the target itself, D-023; otherwise 15% headroom and never above 35% of calories); every portion between its step bounds. The result is **verified again on the numbers the user will see** (rounded to 0.1) before it is returned.
- **Soft goals (minimised):** distance of calories, protein, carbs and fat from target, each meal's distance from its share of the day (25/35/10/30%), and distance from a comfortable portion. Deterministic (same input, same answer).
- **Honest output:** achieved totals, percent of target, per-meal calories, and plain-words `issues` (protein under 90% of target, fat or carbs far off, a meal far from its share). Statuses: ok, issues, infeasible. Infeasible says why: "even the smallest portions give X kcal", "even the largest give only X", "these dishes need about X g protein, above the Y g cap", or "no combination fits". Step 6.7c uses these messages in its repair loop.
- **Findings on the real data (pinned by tests):**
  1. A muscle-gain day of about 3,000 kcal is **infeasible with one dish per role in four meals** (largest portions give 2,200 to 2,300 kcal). Plan for 6.7c: add the mid-morning meal (the table already has the slot) and scale portion limits for large targets, then flip the pinned test.
  2. **High protein targets are hard for vegetarian and especially vegan diets**: 116 g in 1,408 kcal reaches about 80% (vegetarian) and 52% (vegan) with real dishes. The solver reports this as an issue instead of hiding it. Plan for 6.7c: after the repair attempts, accept a documented shortfall and show it with a suggestion (paneer, soy, whey) rather than looping forever. Whether the engine's protein target itself is too high for vegan users is an open question for Venkat.
  3. A kidney-flag user can be infeasible for protein-dense dishes: correct, the cap wins. The picker must be told to prefer lower-protein dishes for that flag.
  4. For users with eating-disorder history (`focus_on_habits`) numbers are hidden (brief section 7): 6.7c builds balanced meals at maintenance and the screen shows no calories or macros.
- **Next:** 6.7c, the dish picker (Gemini chooses dishes per slot for 7 days from the pool; the solver sets portions; issues drive one repair round).

## D-066 — Meal planning, step 3: the 7-day dish picker (model picks, code validates, solver portions, code repairs)
**Status:** Accepted (Step 6.7c, 2026-11-07). Same pattern as the exercise picker (D-052) plus the solver (D-065).
`app/workflows/pick_meals.py`, `app/calc/meal_week.py`, `app/llm/meal_prompt.py`; `app/calc/meal_pool.py` and `meal_portions.py` extended.
- **Shape decided by code:** days under 2,500 kcal have four meals; **big days (2,500 and up) add a mid-morning meal** and main dishes (staple, protein, vegetable, breakfast main) may be up to 1.6 times bigger (`portion_scale_for`); sides, extras and snacks never grow. This resolves the 6.7b finding: a 2,984 kcal muscle-gain day is now feasible for every diet.
- **One model call asks for the whole week** (mid tier, temperature 0, JSON). The prompt lists, per meal and role, only the allowed dishes by key and name with **code-made tags** ("protein-rich", "light", "calorie-dense"), never raw numbers or health data. Code decides an **emphasis**: "low protein" for the kidney flag, "high protein" when protein is 25% or more of the day's calories.
- **Checks on every day (code):** every meal present; required roles filled; each key is in that meal and role's allowed list (a real dish in the wrong role is refused); a main, protein or vegetable dish is never repeated in the same day; and a **weekly repeat cap** per group (breakfast mains; lunch and dinner proteins; lunch and dinner vegetables): at least twice, or more when the diet has few dishes.
- **Per day:** valid picks go to the solver. A day is accepted when the solver says "ok". Days that are invalid, missing or have solver issues are **re-asked once**, with the problems (for solver issues, the solver's own words). Then, for any day still not ok, the code fallback runs: rotate through each role's options (week-aware: the least-used dish wins, so a thin pool spreads out), up to 12 rotations, scored by the solver; the better of the model's candidate and the fallback wins. **Score = ok first, then MORE protein (up to the target), then fewer issues.** (A first version counted issues only, and a day with better protein lost to a day with fewer minor issues.) If no safe day exists, the plan is refused with a clear message instead of an unsafe one.
- **Findings on real data (model on):** vegetarian fat loss (1,408 kcal, 116 g protein): 6 of 7 days came from the model, protein 67 to 76% of target. That shortfall is the data/target limit from D-065 (not enough protein in these dishes at this calorie level), reported honestly. Kidney user (cap 66 g): code picks land at 98 to 99% of the cap, the model's usually less exact, so code wins most days. 3,000 kcal non-veg: macros within 1 to 3% of target on the best days.
- **Cost and speed:** one week costs about $0.04 (two mid-tier calls, about 2.2k tokens in and 5k out each, about 22 s each, mostly Gemini's own reasoning). The screen needs a long waiting state: measured 65 s end to end through the API on 2026-11-07 (with the solver and checks), so about a minute. A background job is worth considering later.
- **Without the model the week still works:** with Gemini switched off, all 16 combinations of diet (4) and profile (4: fat-loss woman, muscle-gain man, maintenance, kidney) give a complete safe 7 days; all hard limits hold on every day (tests).
- **Not done yet:** saving the plan as a pending proposal and approving it (6.7d); the meal plan screen with the "How this plan was made" panel (6.7e). People with eating-disorder history (`focus_on_habits`) get balanced meals with numbers hidden; the generator (6.7d) must apply that rule.

## D-067 — Meal plan as a pending proposal: verified from the foods table, hidden numbers enforced by the server
**Status:** Accepted (Step 6.7d, 2026-11-07)
`app/calc/meal_plan_payload.py`, `app/workflows/generate_meal_plan.py`, `app/workflows/decide_proposal.py` (now handles meals), `app/db/meal_plans.py`, `POST /plans/meal/generate`; approval reuses `POST /plans/proposals/{id}/approve`.
- **Generate:** reads diet, dislikes and the saved inputs as the user, runs the week builder (D-066), builds the payload (7 days; per item: meal, role, position, food key, grams, household unit and quantity, and nutrition), **verifies it**, and saves it as a PENDING `meal_change` proposal. Same protections as workouts: a double-tap within 60 seconds returns the proposal just made, and a newer one expires the older pending one. No plan exists until the user approves.
- **Verification does not trust the saved JSON** (`verify_payload`, run when generating and again when approving): every item's nutrition is recomputed from the foods table and must match; each day's calories must sit in the user's safe band and protein under the cap, **both recomputed from the user's data as saved today** (not from numbers in the payload); every food must exist, be allowed for the user's diet and not be disliked; household units must be units that food really has and must equal the grams; meals and positions must be well formed. Tests tamper with portions, foods, units, slots and positions.
- **Approve:** one transaction (lock, verify, archive the active meal plan, write the new one, mark approved); it **writes code-recomputed nutrition**, not the payload's numbers, and links the user's latest targets row. A tampered plan gets 422 and nothing is written. Another user's proposal looks like it does not exist (404). The type is looked up under RLS first, so ownership is decided by the database as well as the code.
- **Eating-disorder history (brief section 7): the SERVER removes every number** from anything sent to the user (`hide_numbers` in the response model): calories and macros per item, day totals, percent of target, targets, the solver's issues, the day status (it says whether numbers hit targets), the emphasis and the portion scale (both derived from the numbers), and the summary says "balanced meals". Portions in grams and household units stay. The numbers still exist on our side (the plan tables require them and the safety check uses them). A test scans the whole payload for any leaked number key, even as a value. Found by that test: an early version still sent the day status "issues".
- Not done: the meal plan screen and "How this plan was made" panel (6.7e); reading the active meal plan (6.7e, applying the same hiding rule).

## D-068 — The meal plan screen and "How this plan was made": make the engineering visible
**Status:** Accepted (Step 6.7e, 2026-11-09). Implements D-061 technique 6 for meal plans.
`/meal-plan` (`frontend/src/plans/MealPlanPage.tsx`, `MealDays.tsx`, `HowMadePanel.tsx`), `GET /plans/meal/active`, `how_made` in the plan payload.
- **Screen:** generate (a waiting message says it takes about a minute and counts seconds; measured 65 s), a proposal card (summary, the panel, the 7 days grouped by meal, Approve and Reject), and below it your active plan. A proposal is always shown above, and labelled as not yet your plan.
- **The panel** ("How this plan was made") shows, from real data: how many days the AI coach chose and how many our rule-based planner chose; whether the AI was asked to repair days; **what the AI calls really cost** (calls, tokens, dollars, seconds, summed from the actual responses in `pick_meals`); the checks every plan passes; the average match to the user's targets and how many days have a number off target; and a warning when the diet gives little choice (dishes will repeat). It is stored inside the proposal payload (`how_made`) and read back for the active plan from the latest approved meal proposal.
- **Numbers are optional everywhere:** the server leaves out kcal, macros, day totals, targets and every number-derived field for users who must not see numbers; the screen renders only what it receives, so a hidden-numbers plan shows portions and no calories at all. The panel's check text is also reworded for them (no "calorie" or "protein"). Found while testing: the first checks wording mentioned both.
- **Bugs caught by tests this step:** a variable named `usage` in `pick_meals` was reused for the dish counter, so the plan would have stored the wrong object (caught by the usage-accounting test); the active-plan view trusted the database order of items, so it now sorts by position itself.
- **Kept simple on purpose:** this screen uses the current design tokens; the cinematic redesign (D-058, D-059) comes after the backend is done.
- **Phase 6 (plan generation) is complete:** splits, routine rules, goal forecast, workout plans, meal plans, all through proposals and approval. Weekday editing and Profile and settings remain as roadmap items.

## D-069 — Editing the profile after onboarding: one validated path, history kept, plans marked stale (never rewritten)
**Status:** Accepted (Step 6.8, 2026-11-09). Prerequisite for the help bot's profile proposals (D-046).
`GET /profile`, `PATCH /profile`; `app/workflows/update_profile.py` (the one function), `app/calc/profile_edit.py`, `app/db/profile.py`, `app/schemas/profile.py`, `app/api/profile.py`.
- **A change is a small dict** like `{"weight_kg": 74}`. Every field belongs to one onboarding section (basics, goal, preferences, training, screening). The server merges the change into the CURRENT values of that section and validates the MERGED section with the **same Pydantic model onboarding uses**, so ranges, 18+, vocabulary lists, clean-up of repeated dislikes and every cross-field rule are identical. A test keeps the field lists in step with the onboarding forms. Field errors have the same shape as onboarding's (`equipment.0`).
- **Not editable here:** consent, ids, `onboarded_at`, the chosen split and focus areas (they have their own endpoints): refused by name with a 422. An empty change is refused ("Nothing to change"). Editing needs finished onboarding (409 otherwise).
- **Only real changes are written.** Fields equal to the current value are ignored; if nothing changed, nothing is written and no targets row is added.
- **History is kept:** a new weight is today's weigh-in (one per day) and is added only when the weight really changed; a new goal type closes the old goal (`active = false`) and starts a new one from today's weight, so earlier progress is not rewritten; a new pace or target weight updates the goal in place (start weight and date untouched). Every recalculation adds a new `calculated_targets` row; old rows stay.
- **Targets use the same engine** (`calculate_targets`) whenever a number-affecting field changed (date of birth, sex, height, weight, activity, goal type, pace, any health flag). The calculation runs BEFORE the edit commits, inside the same user transaction: an impossible result raises and undoes the whole edit; the new row is then written through the admin door (server-written table). A new weight or target weight on the wrong side of the goal is refused (same check as onboarding).
- **Plans are never edited.** The response says which plans no longer match: workout plan stale (level, place, equipment, days, session length, injuries, goal, pace, any health flag), meal plan stale (anything that changes targets, plus diet, dislikes, cuisine). The screen offers to make a new one, which goes through the normal approval. A target weight change or a new name makes nothing stale. A test confirms an approved meal plan is unchanged after a diet edit.
- **Privacy:** for eating-disorder history the targets in the response have no numbers (same server-side rule as plans).
- **Accounts older than the session-length question** (null) get the app default of 60 minutes when they edit any training answer, so editing never fails on a missing old answer.
- **One function for two doors:** `update_profile(user_id, changes)` serves `PATCH /profile` now and will serve the approval of a help-bot `profile_change` proposal, so the bot gets the same validation and safety.
- **Not done yet:** the settings screen (next step, 6.8b); remembering "plan out of date" after the page is closed (today only the response tells; a persisted indicator is a later improvement); editing workouts per weekday.

## D-070 — The settings screen: change what changed, show what the server did
**Status:** Accepted (Step 6.8b, 2026-11-09)
`/settings` (`frontend/src/settings/`), a Settings button on Home, `api.patch` added to the API helper.
- **Five cards** (About you, Your goal, Food, Training, Health), each its own form with its own Save button, built from the same option lists as onboarding (`onboarding/options.ts`) so wording and allowed values cannot drift. A card says "unsaved changes" and its Save is disabled until something differs from what is saved.
- **Only what changed is sent** (`changedFields`): a weight edit sends `{"weight_kg": 74}`, a dislike edit sends the list, a goal edit sends only the goal fields that differ. The server (D-069) validates the merged section exactly like onboarding; its field errors appear beside the right field in the card that was saved, and what the person typed stays.
- **After a save the page shows what the server did,** not what the screen guesses: the plain messages, the new daily target when targets were recalculated (no numbers at all for users who must not see them, and the doctor note when there is one), and buttons "New meal plan" and "New workout plan" only for plans the server says are stale. Those buttons lead to the existing screens, so a new plan still needs approval. A save that changed nothing says "Nothing needed changing."
- **Before onboarding is finished** the page explains and links to onboarding (409).
- **Kept simple on purpose:** uses the current design tokens; the redesign (D-058, D-059) comes after the backend. Still missing: remembering a stale plan after the page is closed (a persisted indicator, listed in D-069).
- **Bug found by Venkat on first use (2026-11-09):** saving in Settings did nothing. Cause: CORS allowed GET, POST, PUT and DELETE but not PATCH, so the browser's pre-check for the PATCH was refused ("Disallowed CORS method") before it reached our code. Our tests did not catch it because they call the API directly and skip the browser's CORS check. Fix: PATCH added to `allow_methods`, plus a test that reads every route from the app's own API description and runs the browser's pre-check for each method, so a new method can never be forgotten. Lesson: a screen that talks to a new kind of request needs a test through the browser's rules, not only the API's.

## D-071 — Editing your own workout by weekday: immediate, but checked by code (no AI, no approval step)
**Status:** Accepted (Step 6.9a, 2026-11-09). Implements Venkat's original requirement "the user can modify their workout according to the week days".
`POST /plans/workout/edit`, `GET /plans/workout/options`; `app/calc/workout_edit.py` (pure rules), `app/workflows/edit_workout.py`, `app/db/workout_edit.py`, `app/schemas/workout_edit.py`.
- **Your own edits apply at once.** The "no plan change without approval" rule is about suggestions from the AI (proposals). A person editing their own workout is making their own choice, so there is no approval step, but every edit is checked in code first and the whole plan is validated again before it is written. No LLM is involved anywhere.
- **Four edits, one endpoint** (a tagged request, `op`): `move_day` (onto a rest day it moves; onto another training day the two swap), `swap_exercise` (the new one must share the old one's movement or a muscle), `remove_exercise` (a day always keeps at least one; make it a rest day by moving the day), `add_exercise` (appended; sets, reps and rest come from the same routine rules as the generator, one set fewer with a health flag; cardio and mobility are not plannable yet).
- **Checks:** the exercise must exist and not be blocked; it must pass the user's own filter (injuries, level, place, equipment) with the reason in plain words ("it could aggravate your knee"); no duplicate in a day; at most 10 a day; weekly hard-set cap; then `validate_payload` on the whole plan. Request shape is strict (unknown fields, days outside 1 to 7 and bad keys are refused like everywhere else).
- **Weekly cap on edits = 20 hard sets per MAIN muscle** (the first one listed for an exercise). An edit may not increase a muscle above the cap (a plan already over it can still be reduced). **Found by the real-database test:** counting every muscle an exercise lists put a normal generated pull day at 21 back sets, so swaps on it were refused. Counting the main muscle is also how the library is defined. Note: the focus-area logic (D-060) still counts every listed muscle (more conservative); aligning it is a small later cleanup.
- **`GET /plans/workout/options?day=&position=`** lists what the screen can offer: for a swap, exercises that fit the one being replaced; for an add, ones that train a muscle that day already trains. It uses the same checks, **including the weekly cap, so every choice offered will be accepted**; a rest day has none.
- **Day rows are kept.** A workout log points at a plan DAY (`workout_logs.plan_day_id`), so an edit updates each day's label and replaces only the exercise rows under it; moving a day swaps what the weekday rows contain. A move or edit does not create a new plan version. Only the ACTIVE plan can be edited (the row is locked during the edit so two edits at once cannot overwrite each other); archived plans are untouched.
- **Not done yet:** the screen for it (6.9b); editing sets, reps or rest by hand; a "rest day" button (use Move); remembering edits for the next generated plan.

## D-072 — The edit-workout screen offers only what the server says is valid
**Status:** Accepted (Step 6.9b, 2026-11-09). Frontend for D-071: `WorkoutEditor.tsx`, `ExercisePicker.tsx`, toggle in `WorkoutPlanPage.tsx`.
- **"Edit my plan" / "Done editing"** on the Workout plan page switches between the read view and the editor. Plain styling on purpose: the visual redesign comes after the backend is finished (D-058/D-059).
- **The screen has no rules of its own.** Moving a day is a dropdown of the other six weekdays (labelled "rest day" or "swap with X") that applies at once. Swap and Add open a picker filled from `GET /plans/workout/options`, so every choice shown will be accepted (the server already applied injuries, level, equipment and the weekly cap). Each edit is POSTed to `/plans/workout/edit`; the server's message ("Swapped X for Y on Monday.") or its refusal is shown as is, and the plan only changes from the server's reply.
- **One edit at a time:** every control is disabled while a save is in flight, so a double click cannot send two edits.
- **Options considered:** drag-and-drop day reordering (nicer, but harder to test and to use with a keyboard; can be added in the redesign on top of the same endpoint); a client-side filter of the library (rejected: it would duplicate the safety rules in two places).
- **Tests (8):** controls appear and disappear, move, swap (query `?day=1&position=1`), remove, add (query without position), a refusal leaves the plan unchanged, the empty picker, no double submit.
- **Not done yet:** editing sets/reps/rest by hand; a persistent "plan out of date" indicator.

## D-073 — The agent harness core: tool registry, specialist spec, factory and loop (no LLM yet)
**Status:** Accepted (Step 7.1, 2026-11-09). Implements D-063. `app/agents/{context,tools,spec,runner}.py`, `tests/test_agent_factory.py` (26 tests, fake model).
- **Registry (`ToolRegistry`, `Tool`).** A tool = name, description, Pydantic argument model, function `(RunContext, args) -> dict`, scope `read` or `propose` (there is no "apply" scope: only the user's approval applies a change). Registering refuses: duplicate names, argument models that do not set `extra="forbid"`, and argument models with a field named `user_id`/`user`/`uid`/`owner_id` (identity is never a model argument).
- **Spec (`SpecialistSpec`).** Frozen: name, prompt, tool allowlist, tier (small by default), per-call max tokens, `max_steps` (1 to 10), `token_budget` (up to 20,000), timeout. `check()` refuses unknown tools and out-of-range limits before anything runs.
- **Factory + loop (`build_specialist`, `Specialist.run`).** The model is a plain callable returning a `Turn` (tool call or final answer plus tokens); a Gemini adapter comes in 7.2. The HARNESS enforces: allowlist first (a registered tool that is not on this specialist's list is refused and never runs), strict argument validation (extra fields such as a `user_id` are errors), identity from `RunContext`, tool failures turned into a generic message (the real error type is recorded, never shown to the model), and limits on steps, tokens and time (checked before each model call). Each run returns a `RunResult` with status (`ok`, `step_limit`, `token_budget`, `timeout`), steps, tokens, and one `ToolRecord` per tool call: this is what `agent_runs` and the "How this was made" panel will show.
- **Nothing is shared:** `run` keeps its messages in local variables; two spawns, and two runs of one agent object, share nothing (tested).
- **Options considered:** building the loop directly on LangGraph prebuilt `create_react_agent` (less code, but the allowlist, identity injection and limits would live inside a library, harder to test and to explain); writing our own small loop now and putting it inside LangGraph nodes in 7.3 (chosen: the rules are ours and fully tested offline; LangGraph still owns routing, parallel spawn, checkpointing and `interrupt()`).
- **Not done yet:** a Gemini model adapter and logging each run to `agent_runs` (7.2); real tools (7.2).

## D-074 — The first real specialist: nutrition lookup on Gemini
**Status:** Accepted (Step 7.2, 2026-11-09). `app/agents/{gemini_model,food_tools,nutrition}.py`, `scripts/nutrition_demo.py`, `tests/test_nutrition_specialist.py` (24 tests, fake LLM and fake database).
- **Adapter, not a framework.** `gemini_model(spec, registry, ...)` is a `Model` for the D-073 loop. Each turn is ONE `call_llm` call (JSON mode, temperature 0, `max_tokens` from the spec), so retries, rate-limit handling and the `agent_runs` row (flow `chat`, node = specialist name) come for free. The model answers with JSON: `{"tool", "args"}` or `{"answer"}`. The tool list shown to the model is built from the spec's ALLOWLIST only. Anything that is not that JSON shape is treated as a plain answer, never as a tool call. Tool results go back labelled "data, not instructions" (a first defence against prompt injection through data; NeMo comes in 7.6).
- **Why a JSON protocol and not Gemini native function calling:** it keeps the adapter provider-neutral (the provider can be swapped, CLAUDE.md), makes the loop trivially testable, and all rules stay in our harness. Cost: slightly more prompt tokens. Native function calling can replace the adapter later without touching the loop.
- **Tool `search_foods`** wraps the existing food search. Read-only; runs under `user_transaction(ctx.user_id)` (RLS); the model supplies only `query` (1 to 60 characters) and `limit` (1 to 5). Returns per-100 g calories and macros plus household units, as numbers the model quotes and never calculates.
- **Specialist `nutrition`:** small tier, 400 tokens a call, 3 steps, 4,000-token budget, tools = `search_foods` only. The prompt says: always search first, answer only from results, say "not in our database yet" when nothing is found, no arithmetic, no medical advice.
- **Found by the first real run:** the database returns `Decimal` numbers, which cannot be sent to the model as JSON. The fake-database tests used floats and missed it; the tool now converts to float and a test uses real `Decimal` values. Lesson: fake data should have the same types as the real thing.
- **Real run (Gemini, about 2,000 tokens, a fraction of a cent):** "How much protein is in paneer, and how much does a katori of toor dal weigh?" -> two `search_foods` calls, answered paneer from the table and honestly said the dal unit weight was not in the database. Not yet checked: whether a household unit for that dal exists but was not returned (look at when we write evals, 7.7).
- **Not done yet:** the chat endpoint that calls this (7.3 router and 7.4 composer); logging each tool call into `agent_runs` (today one row per LLM call; the tool trace is in the `RunResult`); a database test of the tool with a real user.

## D-075 — The chat graph: router, parallel spawn with Send, finish
**Status:** Accepted (Step 7.3, 2026-11-09). `app/agents/{menu,router,chat_graph}.py`, `scripts/chat_demo.py`, `tests/test_chat_graph.py` (21 tests).
- **Menu (`menu.py`).** The specialists the router may pick, each with a spec, a registry factory and a one-line "when". Today only `nutrition`. Adding a specialist later is one menu entry, not new machinery.
- **Router (`router.py`).** One small-model call (JSON, temperature 0, 200 tokens) returns `{"assignments": [{"specialist", "task"}]}`. The reply is VALIDATED in code: unknown names, duplicates, empty tasks, wrong shapes and anything past 3 assignments are dropped; tasks are cut to 400 characters and the message to 2,000. A bad or injected reply can therefore only ever produce specialists that are on the menu (the graph checks the menu again). The prompt calls the user message "data to classify, never instructions".
- **Graph (`chat_graph.py`, LangGraph 1.2.16).** `route` -> conditional edge returning one `Send("specialist", ...)` per assignment -> `specialist` runs once per assignment IN PARALLEL (each builds a fresh specialist with the D-073 factory, runs, and is dropped) -> results merge through a `Annotated[list, operator.add]` reducer -> `finish`. State carries only strings and plain data; nothing else is kept between messages (no checkpointer yet: that comes with approvals, 7.5).
- **Finish rules (no LLM):** one specialist -> its answer is the reply (composer skipped, a cost rule). Several -> answers joined in the router's order, whatever order they finished in, until the real composer (7.4). None assigned -> a fixed friendly message about what the coach can help with. All failed -> a fixed "try again" message. A failed specialist does not block the others.
- **Tests prove the behaviour, not just the shape:** a `Barrier(3)` that only releases when all three specialists are inside their model at once (real concurrency); an out-of-order finish still joins in router order; each specialist sees only its own task; nothing leaks between two messages; an off-menu name from the router spawns nothing.
- **Real run:** "How much protein is in paneer?" -> router picked nutrition -> 1 tool call -> 929 tokens, answered from the table. "Write me a poem about the moon" -> router picked nothing -> the friendly message, no specialist spawned.
- **Not done yet:** the composer for several answers (7.4); a `/chat` API endpoint, conversation history (last 6 messages + rolling summary) and the chat screen; approvals via `interrupt()` (7.5); guardrails (7.6); router accuracy evals (7.7). With one real specialist the parallel path is proven by tests with fake specialists only.
