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
