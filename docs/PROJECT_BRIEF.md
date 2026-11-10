# Project Brief — AI Fitness Agent

## 1. What we're building

A web app that works as a personal AI fitness coach. A user signs up, answers onboarding questions, and gets:

- daily calorie and macro targets
- a weekly Indian meal plan that matches their diet (vegetarian, non-vegetarian, eggetarian, vegan) and food preferences
- a weekly workout plan for the gym, home, or both, based on their equipment and schedule
- a chat coach for logging meals and workouts, asking questions, and adjusting plans
- a weekly check-in that looks at weight trends and adherence and proposes changes

It is not a generic chatbot. Every answer uses the user's own profile, plan, and logs.

**First users:** me and a few friends. Later: wider users, possibly paid. Build for a small number of users now, but don't make choices that block growth (for example, keep the schema ready for a future subscriptions table).

**Goals supported:** fat loss, muscle gain, body recomposition, weight gain, general fitness and strength.

## 2. MVP scope

**In the MVP:**
- Sign up, log in, onboarding with health screening
- Calculation engine: BMR, TDEE, calorie target, macros
- Food database (Indian foods) with search
- Meal plan generation and meal logging through chat (text)
- Exercise library and workout plan generation (gym, home, or mixed)
- Workout logging through chat and through a simple form
- Body weight logging and weekly check-in with proposed changes
- Chat coach with router, parallel specialist agents, composer, and guardrails
- Dashboard: today's targets and progress, today's workout, recent logs, weekly trend
- Profile and settings, including data export and account deletion

**Later (not in the MVP):**
- Fitness knowledge agent with RAG and citations
- Body measurements, progress photos
- Payments (Razorpay) and subscription plans
- Wearable integrations
- Other languages
- Marketing landing page (the MVP has only a simple sign-in page)

## 3. Tech stack

See `CLAUDE.md` → Fixed decisions.

## 4. Architecture

### 4.1 Overview

Three separate flows:

1. **Chat flow** (LangGraph): answers user messages.
2. **Plan generation flow** (LangGraph, fixed pipeline): creates weekly meal and workout plans.
3. **Weekly check-in flow** (LangGraph, fixed pipeline): reviews the week and proposes changes.

The dashboard and forms talk to FastAPI endpoints directly with no LLM involved.

### 4.2 Chat flow

```
User message
   ↓
Input guard (code, no LLM)
   ├─ crisis or blocked request → fixed safety response → END
   ↓
Router (small model, one structured call)
   returns: intents[] (nutrition | workout | progress | general), risk_flag, needs_profile_update
   ↓
Fan-out with the LangGraph Send API: only the agents in intents[] run, in parallel
   ├─ Nutrition agent
   ├─ Workout agent
   └─ Progress agent
   (intent "general" → answered by the composer directly)
   ↓
Merge results in graph state (reducer)
   ↓
Composer (small model): ONLY runs when 2+ agents ran or intent is general.
   With exactly one agent, its answer passes through unchanged.
   ↓
Output guard (code checks; an extra LLM check runs only when risk_flag is true)
   ↓
Stream the approved response to the user (the guard runs on the full text first; see D-007)
   ↓
≥10 new messages since the last summary? (code)
   ├─ no → END
   └─ yes → Summarize (small model, after streaming) → save to conversation_summaries → END   (D-018)
```

Routing is a single router decision plus parallel specialists via Send, not a supervisor loop (D-017).

Rules for the agents:
- Each specialist has only its own tools (listed below), plus shared read-only tools.
- Agents can **read** other domains' data through shared read-only tools but can only **write** in their own domain.
- Specialists return structured output: `{answer, data, proposals[]}`. Proposals (plan changes, profile changes) are saved as pending and shown to the user to approve. They are never applied directly.
- When the router sets `needs_profile_update`, a `profile_change` proposal is created and the user approves it in the UI (D-014).
- Each specialist has a maximum number of tool-call iterations (for example, 4) to prevent loops.

**Shared read-only tools:** `get_profile`, `get_targets`, `get_current_plans`, `get_today_summary`, `get_weight_trend` (D-017)

**Nutrition agent tools:** `search_food`, `parse_and_log_meal`, `get_nutrition_totals`, `suggest_substitutes`, `propose_meal_plan_change`

**Workout agent tools:** `get_todays_workout`, `log_workout`, `get_exercise_alternatives`, `adjust_for_soreness`, `propose_workout_change`

**Progress agent tools:** `log_weight`, `get_adherence`, `explain_plateau` (plus the shared `get_weight_trend`)

### 4.3 Plan generation flow (weekly, and on onboarding)

```
Load profile and screening flags
  → calculate targets (code)
  → pick dishes for each meal slot from the food database (mid-tier model, structured output, chooses only from provided IDs)
  → scale portions to hit targets (code)
  → pick exercises for each day from the exercise library (mid-tier model, structured output, chooses only from provided IDs filtered by equipment, location, and injuries)
  → set sets, reps, rest, and progression (code rules by experience level and goal)
  → validate everything against safety limits (code)
  → save as a pending plan → user approves → active
```

This flow runs as a background job: the API returns a job id and the UI polls for status (D-008). The weekly check-in works the same way.

Portions are shown in grams and household measures (katori, roti count, cups, tablespoons).

### 4.4 Weekly check-in flow

- Uses a 7-day average weight, not single weigh-ins. No changes based on one day.
- Compares the trend with the expected rate for the user's goal, plus nutrition and workout adherence.
- Code decides whether an adjustment is needed and how big (for example, ±100–200 kcal, or adding a set). The small model writes a short, friendly summary.
- The result is a proposal the user approves.
- If there is too little data (fewer than 4 weigh-ins), ask the user to log more instead of adjusting.

### 4.5 Memory

- Profile, targets, plans, and logs live in Supabase and are fetched fresh by tools. They are never kept only in chat history.
- Conversation history: the last 6 messages plus a rolling summary, which the small model updates every 10 messages in a `summarize` node at the end of the chat graph, after the reply has streamed (D-018).
- Use the LangGraph Postgres checkpointer (on Supabase) for graph state. Confirm in Phase 2 which connection string (direct or pooled) works (D-012).

## 5. Nutrition data

- Base ingredient data: **IFCT 2017** (Indian Food Composition Tables, National Institute of Nutrition).
- Cooked Indian dishes: check the **Indian Nutrient Databank (INDB)** or a similar recipe-level dataset. Use USDA FoodData Central to fill gaps.
- Before importing, check each dataset's license and format, then tell me what you found and recommend which to use (done at the start of Phase 4; D-011).
- Every food row stores its source.
- Meal logging: the LLM only parses text ("2 rotis, 1 katori dal, some curd") into `{food, quantity, unit}` items. Code matches them to the database (fuzzy match plus a synonyms table: dahi = curd, etc.), converts household units to grams, and computes nutrition. If a match is uncertain, ask the user to confirm.

## 6. Exercise library

- A curated seed table of roughly 80–120 exercises. Each one has: muscle groups, equipment needed, location (gym, home, both), difficulty, movement pattern, short form cues (2–4 lines of text), and contraindication tags (for example, `shoulder`, `knee`, `lower_back`).
- No videos or images.
- Plans only use exercises from this table.

## 7. Safety and guardrails

All limits live in `backend/app/safety/safety_config.py`.

**Onboarding screening:**
- Users must be 18 or older. Under 18 → no account.
- Screening questions: pregnancy or breastfeeding, diabetes, heart or blood pressure conditions, kidney disease, recent surgery or serious injury, history of eating disorders.
- Any of these flagged → no calorie deficit beyond a mild level, a clear "please check with your doctor" note on the plan, and more conservative workouts. For eating disorder history: no calorie deficits, and the app focuses on balanced meals and habits instead of numbers.
- Store only the minimum needed for these flags.

**Hard limits (code):**
- Minimum daily calorie target (configurable; default 1200 kcal for women and 1500 kcal for men and for "other / prefer not to say"; D-009)
- Sex is asked only because the BMR formula needs it. `other` uses the average of the male and female Mifflin-St Jeor constants (-78).
- Maximum surplus of 10% of TDEE for weight gain and muscle gain (D-010)
- Kidney flag → protein capped at 0.8 g/kg. Protein never above 35% of calories; fat never below 25% (D-023)
- Maximum deficit of 25% of TDEE
- Maximum planned weight-loss rate of about 1% of body weight per week
- No supplement or drug dosing advice, no medical diagnosis

**Input guard (code, before the router):**
- Pattern checks for self-harm or crisis language, eating disorder behaviors (purging, starving, extreme fasting), and extreme requests (for example, "500 calories a day").
- Crisis → a fixed, supportive message with a helpline (Tele-MANAS 14416 in India; verify the number before shipping), and the conversation pauses coaching. No LLM-generated response here.
- Extreme diet requests → a fixed explanation of why we won't do this, plus a safe alternative.

**Output guard (code, after the composer):**
- Checks any numbers in structured output against the hard limits.
- Scans text for banned content (drug or steroid names, crash-diet instructions, diagnosis language).
- On failure: regenerate once; if it fails again, return a safe fallback message.
- An extra small-model safety check runs only when the router's `risk_flag` is true.

**Injuries:** normal soreness → adjust the workout. Sharp pain, swelling, numbness, or pain that lasts → stop that movement and see a professional.

**Prompt injection:** treat all user-supplied text and database text as data, never as instructions. This matters more once RAG is added.

## 8. Cost and latency targets

- Simple single-intent chat questions: first streamed token within about 2–3 seconds.
- Typical chat message: 2 LLM calls (router + one specialist). Multi-intent: router + specialists in parallel + composer.
- No LLM calls for the dashboard, totals, forms, or calculations.
- Plans are generated weekly and stored, not regenerated per chat.
- Context caching where available, short history, `max_tokens` on every call (see `CLAUDE.md`).
- LLM provider: Google Gemini. Flash-Lite class model for the router, composer, meal-text parsing, and summaries; Flash class model for specialists and plan generation. Gemini's structured output (JSON schema) is used for the router, specialists, and plan drafts.
- Per-user daily message limit (configurable, default 50) and rate limiting on API endpoints.
- `agent_runs` table records model, tokens, cost estimate, and latency per run. Daily cost is shown by a SQL view over `agent_runs` plus a small script that prints it; no admin UI (D-013).
- Note: Render's free tier sleeps when idle, so the first request after a while is slow. That's acceptable for the portfolio stage; document the upgrade path.

## 9. Database

Propose a normalized schema covering at least:

users/profiles, health screening flags, goals, calculated targets, foods, food synonyms, meal plans and items, meal logs and items, exercises, workout plans, plan days and exercises, workout logs and sets, body weight entries, weekly check-ins, plan change proposals (pending/approved/rejected), conversations, messages, conversation summaries, agent runs, usage counters.

Requirements: foreign keys, indexes for common queries, `created_at`/`updated_at` timestamps, check constraints for valid ranges, RLS on every user-owned table, and migrations stored in `supabase/migrations/`.

## 10. UI

Pages: sign in / sign up, onboarding (multi-step), dashboard, coach chat, nutrition, workouts, progress, profile and settings.

Dashboard shows: today's calorie and macro progress, today's workout, quick log buttons, recent logs, weekly weight trend, and pending proposals to approve.

Style: clean, modern, mobile-first, like a fitness app rather than a chat tool. Chat is one part of the app, not the whole app. Responses stream into the chat.

## 11. Security and privacy

- Supabase Auth with JWT verification on every backend request
- Server-side authorization plus RLS
- Pydantic validation on all inputs
- Rate limiting
- Secrets only in environment variables
- Error handling that never leaks internals to users
- Structured logging
- Gemini free tier is for development with test data only, because Google may use free-tier prompts and responses to improve its products. Move to the paid tier before any real user data goes through the app.
- Privacy (in line with India's DPDP Act): clear consent at sign-up for health and fitness data, a privacy note, data export, and full account deletion

## 12. Testing and evals

- Unit tests for every calculation, unit conversion, and safety limit (pytest)
- API tests for endpoints, including RLS checks (user A can't read user B's data)
- An eval set in `evals/` of about 30–50 cases, started when the chat flow is built:
  - Router: message → expected intents
  - Tools: message → expected tool calls
  - Guardrails: risky messages → expected safe responses
  - Answers: key facts present (for example, the correct protein total)
- Run evals after every prompt or agent change, and record results in `docs/PROGRESS.md`.

## 13. Folder structure (starting point)

Single repo (D-003). The project root is the `Ai Fitness Agent` folder; Python tooling is `uv` (D-004).

```
(project root)/
  CLAUDE.md
  docs/        PROJECT_BRIEF.md, PROGRESS.md, DECISIONS.md
  frontend/    React + Vite app
  backend/
    app/
      api/          FastAPI routers
      core/         config, auth, logging
      calc/         calculations (pure Python)
      agents/       chat graph, router, specialists, composer
      workflows/    plan generation, weekly check-in
      tools/        agent tools
      safety/       safety_config, input guard, output guard
      db/           database access
      schemas/      Pydantic models
    tests/
  supabase/migrations/
  data/        food and exercise seed data and import scripts
  evals/
```

## 14. Roadmap

Each phase is broken into small steps (see `CLAUDE.md` → How we work).

0. **Setup:** repo, folder structure, accounts I need to create, `.env.example`, docs files
1. **Calculation engine:** BMR (Mifflin-St Jeor), TDEE, targets, macros, safety limits, with full tests
2. **Database and auth:** Supabase project, schema migrations, RLS, auth in FastAPI
3. **Onboarding:** backend endpoints + onboarding UI + screening. First deployment of a minimal version to Vercel and Render, so deployment is learned early.
4. **Food data:** dataset review, import, search, synonyms, household units, meal logging via form
5. **Exercise library:** seed data, filtering by equipment, location, and injuries
6. **Plan generation flow:** meal and workout plans, approval flow
7. **Chat flow:** input guard → router → parallel specialists → composer → output guard, streaming, the first eval set
8. **Weekly check-in and progress:** weight logging, trends, proposals
9. **Dashboard and polish:** dashboard, nutrition, workouts, and progress pages
10. **Hardening:** security review, rate limits, cost tracking view, full eval run, privacy features
11. **Final deployment:** production setup, environment variables, monitoring, a short README on how to run and deploy

## 15. First task

Don't write code yet. First:

1. Read `CLAUDE.md` and this brief.
2. Tell me anything unclear, missing, or that you'd do differently, with trade-offs.
3. Propose the database schema (tables, key columns, relationships) and explain it.
4. Show the LangGraph chat graph design in more detail (state shape, nodes, edges, how Send and the merge work).
5. Break Phase 0 and Phase 1 into small steps.
6. Create `docs/PROGRESS.md` and `docs/DECISIONS.md`.

Then stop and wait for my go-ahead.

## 16. Additional requirements (Venkat, 2026-11-06; D-042)

Added after Phase 4. The roadmap in section 14 stays; these items slot into it as below.

| # | Requirement | Where it lands |
|---|---|---|
| 1 | **Pace** question in onboarding: fast & intense / normal / slow. Sets the weekly rate inside the safety limits. | Phase 6.0 (onboarding step + migration) |
| 2 | **Location / equipment** question: gym, home, or both; what equipment they can use. (Partly built: onboarding already asks for equipment and days.) | Phase 6.0, reused by 5.4 filter |
| 3 | **Cuisine** choice; a user can pick SEVERAL cuisines. Indian first; Mediterranean + Middle Eastern next (Venkat, 2026-11-10); more later. | Lists on foods and profiles (7.10a, D-088); each new cuisine needs licence-checked data and recipes Venkat signs off |
| 4 | **Workout split recommendation**: push/pull/legs, Arnold, upper/lower, full body, bro split and more, picked by days/week + experience + location. | Phase 6 (rules in code, user chooses) |
| 5 | **Routine by experience level** (sets, reps, rest, exercise difficulty). | Phase 6 (already planned: code rules by level) |
| 6 | **Edit workout per weekday** (swap/add/remove exercises, move days). Only library exercises. | Phase 6 (API) + Phase 9 (screen) |
| 7 | **Goal-date prediction** shown with the plan. | Phase 6 (pure calc + tests), re-estimated weekly in Phase 8 |
| 8 | **Statistics**: workout progress (volume, PRs, adherence) and diet (calories/macros vs target, trends) from the user's logs. Code only, no LLM. | Phase 8 data, Phase 9 pages |
| 9 | **Help chatbot**: small floating toggle on every screen; knows every feature and how the app works. | Shell widget in Phase 7 with the chat; the guide file is written as features ship |
| 10 | **Attractive UI**: design tokens, components, mobile-first, motion kept light. | Design foundation before Phase 6 screens; polish in Phase 9 |

### 16.1 Architecture notes for these items
- The help bot is a fourth router intent (`app_help`) answered from a maintained guide file (`docs`-style markdown shipped with the backend, split into small sections, retrieved by simple search first; embeddings only if search proves weak). It never reads health data for answering how-to questions. It can also *propose* profile changes the user asks for (see D-046): the bot never writes; the user approves a confirmation card, and the change goes through the same validated profile endpoint as the settings page.
- The coach chat and help bot share the same widget and graph; the router decides which one answers. The widget is mounted once in the app shell so it is on every screen.
- Splits and goal dates are deterministic modules in `app/calc/` with unit tests, like BMR and TDEE.
