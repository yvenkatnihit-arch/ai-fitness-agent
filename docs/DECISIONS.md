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
