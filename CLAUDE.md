# CLAUDE.md — AI Fitness Agent

## About this project and me

I'm Kruthi. I'm building an AI fitness coach web app: personalized Indian meal plans, gym and home workout plans, logging through chat, and weekly plan adjustments.

- Stage: portfolio project first (me and a few friends), with a possible path to paying users later.
- My background: I've built LangGraph and RAG projects before, but I'm still learning full-stack development, databases, and deployment.
- Your role: my guide and pair programmer for the whole project, from setup to deployment. I want to understand everything we build, not just receive code.

Key documents (keep them up to date):
- `docs/PROJECT_BRIEF.md` — the full product and technical spec. Read it before starting any phase.
- `docs/PROGRESS.md` — what's done, what's in progress, what's next. Update it at the end of every step.
- `docs/DECISIONS.md` — every architecture decision, with the options considered and why we chose one.

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
- Run the tests: `uv run pytest -v`
- Add a package: `uv add <package>` (dev-only: `uv add --dev <package>`)

**Frontend (`frontend/`)**
- Run the dev server: `npm run dev` → http://localhost:5173
- Run the tests: `npm test`
- Lint: `npm run lint`
- Production build: `npm run build` (output goes to `dist/`)

**Git (project root)**
- The remote is HTTPS: https://github.com/yvenkatnihit-arch/ai-fitness-agent (private). Branch: `main`.

**Not set up yet:** migrations (Phase 2), evals (Phase 7), deployment (Phase 3).

**Windows notes**
- If `npm` fails with "running scripts is disabled": `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- If Python crashes printing emoji (`UnicodeEncodeError`): set `$env:PYTHONIOENCODING = 'utf-8'`
