# CLAUDE.md — AI Fitness Agent

## About this project and me

I'm Kruthi. I'm building an AI fitness coach web app: personalized meal plans (Indian first; Mediterranean and Middle Eastern next, more later, D-088), gym and home workout plans, logging through chat, and weekly plan adjustments.

- Stage: portfolio project first (me and a few friends), with a possible path to paying users later.
- My background: I've built LangGraph and RAG projects before, but I'm still learning full-stack development, databases, and deployment.
- Your role: my guide and pair programmer for the whole project, from setup to deployment. I want to understand everything we build, not just receive code.

Key documents (keep them up to date):
- `docs/PROJECT_BRIEF.md` — the full product and technical spec. Read it before starting any phase.
- `docs/PROGRESS.md` — what's done, what's in progress, what's next. Update it at the end of every step.
- `docs/DECISIONS.md` — every architecture decision, with the options considered and why we chose one.
- `docs/AGENT_ARCHITECTURE.md` — **read first when resuming**: where we are, the agent/harness flowcharts (when agents are created and deleted, when ad-hoc agents are used), the roadmap and open items.
- `docs/FLOWS_GUIDE.md` (+ PDF) — Venkat's study guide to the six flows to learn (request and identity, onboarding to targets, propose and approve, the meal plan solver, the chat flow, observability and evals), written as if the project were finished. Update flows 5 and 6 when Phase 7 is built.
- `docs/DESIGN_BRIEF.md` — Venkat's frontend design prompt plus the decisions on it (the redesign starts only after the backend is done).

## How we work (always follow this)

1. **One small step at a time.** A step is something I can run and see working within about 15–30 minutes: one endpoint, one table, one tool, one page. Never build several features at once.
2. **For every step:**
   - Before coding: explain in plain language what we're building and why, and which files will change.
   - Write the code.
   - Tell me exactly how to run it and what I should see.
   - Write or update tests for it and run them.
   - Then **stop and wait for me to say "go"** before the next step.
3. **Explain new concepts briefly** the first time they appear (for example: RLS, JWT, migrations, CORS, Docker image, the LangGraph Send API). Short and concrete, using our code as the example.
4. **At the end of each phase:** summarize what we built, update `docs/PROGRESS.md`, and ask me 2–3 short questions to check my understanding.
5. **Tell me clearly when I need to do something myself**: creating accounts (Supabase, Google AI Studio, Vercel, Render), copying API keys into `.env`, approving a payment, clicking something in a dashboard. You can't do these for me.
6. **Ask before major decisions.** If something in the brief is unclear or you think a different approach is better, explain the trade-off and let me choose. Log the choice in `docs/DECISIONS.md`.
7. **When something breaks**, explain what the error means before fixing it.

## Fixed decisions (don't change without asking me)

- Frontend: React + Vite + TypeScript + Tailwind CSS
- Backend: Python + FastAPI + Pydantic
- Agents: LangGraph (LangChain components only where they clearly help)
- LLM: Google Gemini API (through `langchain-google-genai`), with two tiers configured through environment variables: a small fast model (Flash-Lite class) and a mid-tier model (Flash class). Look up the current stable model IDs in Google's docs; avoid preview models and don't hardcode model IDs in logic. Keep all LLM setup in one module so the provider can be swapped later.
- Gemini data use: on the free tier, Google may use prompts and responses to improve its products. Use the free tier only with test data during development. Before real users (including my friends) enter health data, remind me to enable billing so we're on the paid tier.
- Database and auth: Supabase (Postgres + Auth + Row Level Security), with SQL migrations in the repo
- Observability: LangSmith (free tier) for agent traces, plus our own `agent_runs` table for tokens, cost, and latency
- Hosting: Vercel (frontend), Render (backend, Docker), Supabase hosted (database)
- Food logging is text only. No image input in the MVP.
- No exercise videos or images. Workouts are text instructions with short form cues.
- English only for now.

## Non-negotiable rules

- **The LLM never does math.** Calories, macros, portions, BMR/TDEE, progression, and trends are calculated in plain Python functions with unit tests.
- **The LLM never invents foods or exercises.** It selects from our food database and exercise library; code computes quantities.
- **Safety limits live in code**, in one config module (`safety_config.py`), and the LLM can't override them. See the Safety section of the brief.
- **No plan changes without user approval.** Agents create a *proposal*; the user approves it in the UI; then the change is saved.
- **No secrets in code.** Everything goes in `.env` (never committed). Keep `.env.example` updated.
- **No mock data in real workflows.** If a placeholder is needed, label it clearly with `# MOCK:` and track it in `docs/PROGRESS.md`.
- **Small files with clear names.** No giant files. Follow the folder structure in the brief.
- **Every user-owned table has RLS enabled** and is also checked server-side.

## Cost and latency rules

- Use the small model by default. Use the mid-tier model only for weekly plan generation and plan adjustments.
- Never call an LLM for something code can do: dashboard data, totals, form-based logging, calculations, simple lookups.
- Skip the composer when only one agent ran.
- Use Gemini context caching for system prompts and tool definitions where it's available and actually saves money (check the current docs for which tiers and models support it).
- Watch Gemini rate limits (requests per minute and per day). Handle rate-limit errors with retries and backoff, and show the user a friendly message instead of an error.
- Send only the last 6 messages plus a rolling summary as conversation history, never the full history.
- Set `max_tokens` on every LLM call. Responses should be short and direct by default.
- Log tokens, cost, and latency for every agent run.

## Commands

Run each block from the folder named in its heading. Requires `uv` (Python 3.14) and Node 24 + npm.

**First-time setup**
- Backend: `cd backend`, then `uv sync`, then `Copy-Item .env.example .env` and fill in the values
- Frontend: `cd frontend`, then `npm install`, then `Copy-Item .env.example .env`

**Backend (`backend/`)**
- Run the dev server: `uv run uvicorn app.main:app --reload` → http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs
- Run the tests: `uv run pytest -v` (fast, offline; database tests are left out)
- Run the database tests against Supabase: `uv run pytest -m db -v`
- Add a package: `uv add <package>` (dev-only: `uv add --dev <package>`). Versions newer than `exclude-newer` in `pyproject.toml` are ignored on purpose (D-030).
- Check the database is reachable: http://127.0.0.1:8000/ready

**Database migrations (`backend/`)**
- New migration: add `supabase/migrations/<YYYYMMDDHHMMSS>_<name>.sql` (every `create table` needs `enable row level security`)
- Preview: `uv run python scripts/migrate.py --dry-run`
- Apply: `uv run python scripts/migrate.py` (Supabase CLI pinned to 2.121.0, D-024; reads `DATABASE_URL` from `.env`; then sets up LangGraph's checkpointer tables in the `langgraph` schema, D-012)
- LLM cost per day: `uv run python scripts/daily_cost.py` (last 14 days; pass a number for more)
- Check the Gemini key and models with one tiny real call (about $0.00005): `PYTHONPATH=. uv run python scripts/llm_smoke.py [small|mid]` (PowerShell: `$env:PYTHONPATH='.'` first)
- Try the exercise picker for a made-up user (real library + real Gemini, about a cent, saves nothing): `PYTHONPATH=. uv run python scripts/pick_demo.py ppl_3 intermediate gym knee`

**Food data (`backend/`, D-037)**
- Download/verify the open datasets into `data/raw/` (git-ignored): `uv run python -m fooddata.download` (add `--check` to verify without network). Sources, licences, credits and SHA-256 are in `data/sources.json`.
- Run every validation check over the full datasets (nothing is imported): `uv run python -m fooddata.audit`
- Find a food's exact source id: `uv run python -m fooddata.find "pigeon peas" "paneer"`
- Validate our ingredient list (`data/ingredients.csv`) and recipes (`data/recipes.csv` + `data/recipe_items.csv`: raw grams + cooked weight; sign off a recipe by filling `reviewed_by`) → `data/foods_validated.csv` + `data/reports/ingredients_review.md`: `uv run python -m fooddata.build`
- Household units (`data/food_units.csv`: usda portion / katori-glass volume / recipe piece, D-040) are checked by the same build → `data/food_units_validated.csv`
- Load the validated foods into Supabase (`foods` + `food_synonyms` + `food_units`; upsert by key, safe to re-run, D-039): `uv run python -m fooddata.load --dry-run`, then `uv run python -m fooddata.load`

- See how many food choices each diet has per meal and role (real foods, saves nothing): `PYTHONPATH=. uv run python scripts/pool_report.py [dislike1,dislike2]`

- Try the portion solver on a real day (real foods and engine targets, no LLM, saves nothing): `PYTHONPATH=. uv run python scripts/solver_demo.py vegetarian fatloss_f protein` (diet, profile, pick)

- Build a full 7-day meal plan on real foods with REAL Gemini (about $0.04, saves nothing; `fallback` switches Gemini off): `PYTHONPATH=. uv run python scripts/meal_week_demo.py vegetarian fatloss_f model`

**Exercise data (`backend/`, D-041)**
- The Free Exercise DB file is downloaded/verified by the same command as the food data: `uv run python -m fooddata.download`
- Find an exercise's Free Exercise DB id (to cite in `data/exercises.csv`): `uv run python -m exercisedata.find "goblet squat" "pushups"`
- Validate `data/exercises.csv` (sign off an exercise by filling `reviewed_by`) → `data/exercises_validated.csv` + `data/reports/exercises_review.md`: `uv run python -m exercisedata.build`
- Load the validated exercises into Supabase (upsert by key, safe to re-run): `uv run python -m exercisedata.load --dry-run`, then `uv run python -m exercisedata.load`

**Docker (`backend/`)**
- Build the image: `docker build -t ai-fitness-backend .`
- Run it locally (secrets from `.env` at run time, never in the image): `docker run --rm --name ai-fitness-backend-local --env-file .env -p 8000:8000 ai-fitness-backend` → http://127.0.0.1:8000/health
- Logs: `docker logs ai-fitness-backend-local` (JSON lines). Stop: `Ctrl+C` or `docker rm -f ai-fitness-backend-local`

**Frontend (`frontend/`)**
- Run the dev server: `npm run dev` → http://localhost:5173
- Run the tests: `npm test`
- Lint: `npm run lint`
- Production build: `npm run build` (output goes to `dist/`)

**Git (project root)**
- The remote is HTTPS: https://github.com/yvenkatnihit-arch/ai-fitness-agent (private). Branch: `main`.

**Evals (`backend/`, D-079)**
- Guard evals and the regression gate (free, offline): `uv run python -m evals.run` (exit code 1 when the gate fails); lock in improvements with `--update-baseline`. The same gate runs inside `uv run pytest`.
- Model-based evals with REAL Gemini calls (router about $0.003, composer about $0.003, nutrition specialist about $0.01; cached in `evals/cache/`, `--fresh` ignores the cache, `--show` prints every answer; use `--fresh` after changing a tool or the data, the cache cannot see that): `uv run python -m evals.run_llm router|composer|nutrition|workout|meal|summary|specialists` (specialists: 19 questions through the real chat for the exercise, meal-logging and my-plan specialists against a scratch user with real plans, a few cents; summary: 10 made-up chats for the rolling summary, about $0.001; workout: 14 made-up users through the real exercise picker, about $0.02; meal: 7 made-up users through the real dish picker and solver, about $0.05, `--limit=N` for a subset) (exit code 1 when below `evals/llm_thresholds.json`).

**Protein check (`backend/`, D-093)**
- How much of the protein target do meal plans reach? Offline, real validated foods, no model, no database, no cost: `PYTHONPATH=. uv run python scripts/protein_report.py [indian|mediterranean]`. The same numbers are a regression gate inside `uv run pytest` (`tests/test_protein_regression.py`).

**Not set up yet:** CI, deployment (Phase 3).

**Windows notes**
- If `npm` fails with "running scripts is disabled": `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- If Python crashes printing emoji (`UnicodeEncodeError`): set `$env:PYTHONIOENCODING = 'utf-8'`
