# AI Fitness Coach: the demo model, explained

This guide covers **only what is built and working today** (the demo model). It does not describe the plans for later. Every file name below exists; every number was checked against the project.

How to use it (about 3 hours): read sections 1 and 2 first (15 minutes), then follow the flows in section 4 with the code open next to you (about 2 hours), then the glossary (section 6) and the talk track (section 7). Section 9 is a reading order for the 10 most important files.

---

## 1. What the demo model does

| Screen (route) | What the person does | What it demonstrates |
|---|---|---|
| Sign in / sign up (`/sign-in`) | Creates an account | Supabase login; the backend never sees a password |
| Onboarding (`/onboarding`) | Six short forms: consent, body, goal and pace, diet and cuisines, training setup, health screening | Safety-aware personalisation; ends with daily targets |
| Home = dashboard (`/`) | Sees today's calories and macros against targets, what they logged, what today's plan says, a weight log with a trend chart, their targets, a goal-date forecast, and starter questions for the coach | Everything here is calculated by code, no AI |
| Meal plan (`/meal-plan`) | Generates a 7-day plan, reads it, presses **Approve** | AI picks dishes, code works out portions, the user decides |
| Workout (`/workout`, `/splits`) | Picks a split, generates a plan, approves it, can edit a day | Same pattern, with exercises from our library |
| Log a meal (`/log`) | Searches foods, picks amounts in household units | Code-only nutrition from a validated database |
| Chat (round button, `/chat`) | Asks about foods, exercises, their own plan and progress, or tells the coach what they ate | Guards, a router, four specialists, a confirm step |
| Settings (`/settings`) | Changes details, diet, cuisines, dislikes | Changing them marks plans "out of date" |
| How the AI works (`/how-it-works`) | Reads the rules, the eval scores, and their own AI usage | The engineering made visible |

## 2. The mental model in one page

```
 Browser (React)  --- login token --->  FastAPI backend  ---> Supabase Postgres (data, login, row-level security)
                                              |
                                              +---> Google Gemini (only where language is needed)
```

Four ideas explain almost every design choice. If you remember nothing else, remember these:

1. **The AI never does math and never invents foods or exercises.** Calories, macros, portions, targets, trends and totals come from plain, tested Python (`backend/app/calc/`). The AI only chooses from lists we give it, and understands and writes language.
2. **The AI proposes; the person decides.** A plan or a meal to log is saved as a *pending proposal*. Nothing changes until the user presses Approve, and at that moment the backend re-checks everything.
3. **Safety lives in code the AI cannot change.** Limits are constants in one file; dangerous messages are stopped by code before any AI runs; replies are checked on the way out.
4. **Everything is measured.** Every AI call is logged (tokens, cost, time). Evals score the AI against pass lines. An audit of 50 real questions found and fixed 11 problems.

Two model sizes are used, both Gemini, configured in `.env`: a small fast one for chat, and a mid-tier one for generating plans (the only place where it is worth paying more).

## 3. Map of the project (what exists)

```
backend/app/
  main.py            builds the web app: middleware, CORS, and attaches every router
  api/               one file per area; each is thin: check login, call a workflow, return JSON
                     onboarding, targets, plans, meals, foods, exercises, splits, profile, training,
                     chat, dashboard, weight, insights, me
  workflows/         the steps of a job, in order (the "what happens when you press the button" layer)
                     complete_onboarding, generate_meal_plan, generate_workout_plan, decide_proposal,
                     meal_log_proposal, chat_turn, dashboard, weight_log, ai_usage, update_profile, edit_workout
  calc/              ALL the math, as pure functions with unit tests (no database, no AI)
                     bmr, tdee, goals, clamps, macros, engine (targets) | portions, meal_pool, meal_solver,
                     meal_week, meal_plan_payload (meal plans) | workout_plan, splits, exercise_filter,
                     weekly_cap (workouts) | forecast, weight_trend, week_summary, food_rank, exercise_search
  agents/            the chat: chat_graph (the flow), router, specialists, tools, composer, summarizer,
                     claims, fallback, runner, spec, menu, approvals, checkpointer, gemini_model
  safety/            safety_config (every limit), guards (the input and output checks), messages
  llm/               client.py: the ONE place that calls Gemini (retries, limits, logging); pricing, prompts
  db/                small functions that run SQL; transactions.py decides whose data a query may see
  schemas/           the shapes of requests and responses (Pydantic)
  core/              auth (login check), config, errors, logging, chat_limits, vocabulary, time
frontend/src/        pages and components by area: auth, onboarding, pages (Home, SignIn), dashboard, weight,
                     chat, plans, meals, settings, splits, insights, targets; lib/api.ts talks to the backend
supabase/migrations/ the database schema, one file per change (27 tables, all with row-level security)
data/ + backend/fooddata, exercisedata/   how foods and exercises were gathered, checked and loaded
backend/evals/       the quality tests for the AI (scores, pass lines, published results)
backend/tests/       the unit and database tests (about 2,840 offline + 500 database tests)
docs/                DECISIONS.md (every decision and why), PROGRESS.md, this guide, AGENT_ARCHITECTURE.md
```

## 4. The flows, end to end

### Flow 1: who are you? (login and data privacy)
1. The browser signs in with Supabase (`frontend/src/auth/AuthProvider.tsx`, `lib/supabase.ts`) and gets a **token** (a signed proof of who you are).
2. Every call to our backend carries it: `frontend/src/lib/api.ts` adds `Authorization: Bearer <token>`.
3. The backend checks the token's signature with Supabase's public keys (`backend/app/core/auth.py`): signature, expiry, audience, issuer. No secret needed. The result is a `CurrentUser(id, email)`.
4. When a query runs "as the user", `backend/app/db/transactions.py` → `user_transaction(user_id)` tells Postgres *who is asking* (it switches to a restricted role and sets the user id). **Row-level security (RLS)** then makes the database itself hide other people's rows. A bug in our code still cannot leak another user's data.
5. `admin_transaction(reason)` bypasses RLS and is only for system jobs (applying an approved proposal, logging AI usage); it requires a reason, which is logged.

What to say: *"Privacy is enforced twice: in the code and in the database."* Check it yourself: every table in the database has RLS on.

### Flow 2: onboarding to daily targets
1. Six forms save one at a time (`frontend/src/onboarding/*Step.tsx`, `api/onboarding.py`).
2. `workflows/complete_onboarding.py` runs `calc/engine.py`:  **BMR** (Mifflin-St Jeor, `bmr.py`) → **TDEE** with the activity level (`tdee.py`) → **goal target** with a pace (`targets.py`) → **safety clamps** (`clamps.py`) → **macros** (`macros.py`).
3. `safety/safety_config.py` holds the limits the clamps use: calorie floors (1,200 for women, 1,500 otherwise), a deficit of at most 25% of TDEE, a surplus of at most 10%, weight loss of at most about 1% of body weight a week, a mild deficit if a health flag is set, no deficit at all and no numbers shown for an eating-disorder history, a protein cap for kidney problems, protein at most 35% of calories, fat at least 25%.
4. The numbers are saved (`calculated_targets`) with the reasons ("We limited your calorie deficit to a safe level"), and Home shows them (`pages/HomePage.tsx`, `targets/TargetsView.tsx`). A goal-date range comes from `calc/forecast.py`.

What to say: *"Every number on Home comes from this one pipeline; the AI is not involved."*

### Flow 3: the meal plan (propose, then approve)
1. Press Generate → `api/plans.py` → `workflows/generate_meal_plan.py`.
2. `calc/meal_pool.py` builds the **pool**: the foods this user may eat (their diet, dislikes and cuisines) grouped by meal and role (staple, protein, vegetable, side).
3. `workflows/pick_meals.py` asks the mid-tier model to **choose dishes** from that pool for each day and meal. The model only picks keys from the list; if it fails or picks badly, code picks instead (`calc/meal_week.py`), so a plan always arrives.
4. **Code works out the portions**: `calc/meal_solver.py` finds amounts in household units (katori, piece, cup) that hit the calorie and protein targets inside the safety limits. `calc/meal_plan_payload.py` assembles and verifies the plan.
5. The plan is saved as a **pending proposal** (`plan_proposals`), and the screen shows it with a "How this plan was made" panel (which days the AI chose and which code chose, the checks it passed).
6. **Approve** → `api/plans.py` → `workflows/decide_proposal.py` **re-verifies the plan against the database and today's targets** and only then writes the active plan. Reject changes nothing.

What to say: *"The AI picks the dishes, code does the arithmetic, and the user has the last word."*

### Flow 4: the workout plan
Same shape. A split is chosen (`calc/splits.py` recommends one from days per week and level), `workflows/pick_exercises.py` has the model choose exercises from the **library** filtered for this person (`calc/exercise_filter.py`: injuries, level, place, equipment), `calc/workout_plan.py` validates the plan, `calc/weekly_cap.py` enforces a limit on weekly hard sets, and it waits for approval like a meal plan. The user can edit a day afterwards (`workflows/edit_workout.py`), and code re-checks every edit.

### Flow 5: logging, the dashboard and the weight log (no AI at all)
- **Log a meal** (`api/meals.py`): the browser sends food ids, amounts and units; `calc/portions.py` turns "2 pieces" into grams and nutrition from the database values. The browser never sends calories.
- **Dashboard** (`workflows/dashboard.py`, `GET /dashboard/today`): eaten today (summed in code) against targets, with percentages computed in code; today's planned meals and workout from the approved plans.
- **Weight log** (`workflows/weight_log.py`, `calc/weight_trend.py`): one weigh-in a day; code computes change, distance to target, percent of the way, weekly rate. A weigh-in moves the goal-date forecast but deliberately does **not** change the daily targets (those change only when weight is edited in Settings).
- Users with an eating-disorder history get no calories, macros or weights anywhere: removed on the server, not just hidden on screen.

### Flow 6: one chat message, end to end (the centrepiece)
Take: *"I ate 2 rotis and dal for lunch"*. Files in order:
1. **Chat screen** (`frontend/src/chat/ChatPage.tsx`) posts to `POST /chat` (`backend/app/api/chat.py`).
2. **`workflows/chat_turn.py`** runs the turn: checks the **rate limit** (`core/chat_limits.py`: 15 messages in 10 minutes, 150 a day, counted from saved messages), **saves your message** (`db/chat_history.py`), reads the **last 6 messages and a rolling summary** (the only history the AI ever sees).
3. **The chat graph** (`agents/chat_graph.py`, built with LangGraph) runs these steps:
   - **Input guard** (`safety/guards.py`): plain pattern checks, no AI. Crisis, extreme diets, medical-advice requests, dizziness or sharp pain, and prompt-injection attempts are stopped here with a fixed, safe reply, before any model runs.
   - **Router** (`agents/router.py`): one small-model call picks which specialists should handle the message. Its answer is validated against the menu (`agents/menu.py`), so it cannot invent a specialist. It also rewrites follow-ups so they stand alone ("and how much fat?" becomes a full question).
   - **Specialists** run **in parallel**, each created fresh for this message and then discarded (`agents/runner.py`, `spec.py`). A specialist is a prompt plus an **allowlist of tools**; the runner enforces step, token and time limits and injects *your* identity, which the model can never set.
   - **Composer** (`agents/composer.py`) only runs when two or more specialists answered; code checks that it invented no numbers (otherwise the answers are just joined).
   - **Claims rule** (`agents/claims.py`): for a specialist that can propose something, the words about the proposal come from code, so it can never say "saved" when nothing was.
   - **Output guard**: the reply is checked on the way out and replaced if unsafe.
   - **Approval pause**: if a proposal exists, the graph **pauses** (`interrupt`, state saved by `agents/checkpointer.py`) and the screen shows a "Please confirm" card.
4. The reply and what ran are saved; in the background `agents/summarizer.py` folds old messages into a short summary (checked by code: no new numbers, no unsafe text).
5. **You press Approve** → `POST /chat/{id}/decide` → `agents/approvals.py` → `workflows/decide_proposal.py` → `workflows/meal_log_proposal.py` re-finds the foods and amounts in the database and writes the meal exactly like the form would.

**The four specialists and their tools** (all read-only except the last row's proposal):

| Specialist | Answers | Tools (all in `agents/*_tools.py`) |
|---|---|---|
| nutrition | "protein in paneer", "calories in 2 rotis", "high-protein vegan foods" | `search_foods`, `portion_nutrition` (code does the multiplication), `find_foods` (code ranks) |
| my_plan | "my calorie target", "dinner on Wednesday", "workout on Friday", "how many calories left today", "how much weight have I lost" | `get_my_targets`, `get_my_meal_plan_day`, `get_my_workout_day`, `get_today_logged`, `get_week_logged`, `get_my_weight` |
| exercises | "how do I do a plank", "alternative to lunges for a knee injury" | `search_exercises`, `get_exercise`, `find_alternatives` (each marks whether it fits *you*) |
| meal_logger | "I ate 2 rotis and dal for lunch" | `search_foods`, `propose_meal_log` (the only tool that creates a proposal) |

If no specialist fits ("hello"), or the user asks the chat to make a plan ("make plan for me", "prepare a diet for me": caught by code before the router, D-119), `agents/fallback.py` gives a fixed, topic-aware reply that points to the right screen (Meal plan or Workout plan).

Every coach answer has 👍 / 👎 buttons (D-120). The choice is saved on the message (`chat_messages.feedback`, `PUT /chat/messages/{id}/feedback`), so wrong answers can be found later: `select content, meta from chat_messages where feedback = 'down'`.

The output guard (D-118) lets true reports such as "So far you have logged 700 kcal for the day" through; it still blocks advice below the calorie floor.

What to say: *"The model reads and writes language. Code decides what it may do, does the maths, and checks the result."*

### Flow 7: the three layers of safety
1. **Limits in code** (`safety_config.py`): the AI cannot change a calorie floor.
2. **Guards in code** (`safety/guards.py`, `agents/claims.py`, the number checks in the composer and summarizer): stop or replace bad input and output without asking a model.
3. **Structure**: proposals need approval, tools are allowlisted and read-only, row-level security, no secrets in code, a rate limit.

### Flow 8: how we know it works
- **Evals** (`backend/evals/`, run with `uv run python -m evals.run_llm <name>`): the router (91 cases), the composer, the nutrition specialist, the rolling summary, meal and workout plan quality, and the three newest specialists end to end (19 questions through the real chat). Pass lines live in `evals/llm_thresholds.json`; a run below a line fails.
- **Guard evals** (`uv run python -m evals.run`): free and offline, with a baseline that must not get worse.
- **Cost log**: every call is written to `agent_runs` (tokens, estimated cost, time) by `llm/client.py`; the "How the AI works" page shows your own usage.
- **The audit**: 50 realistic questions through the real chat found 11 real problems (for example "pushup" not matching "Push-Up", a deadlift reported as missing when it was merely unsuitable, "may help with back pain" wording). Each was fixed with a test. See D-115 in `docs/DECISIONS.md`.
- **`backend/scripts/demo_check.py`**: runs a brand-new account through the whole demo and prints PASS or FAIL for each of 20 steps.

### Flow 9: where the food and exercise data come from
Foods come from open datasets (USDA SR Legacy, UK CoFID), exercises from the Free Exercise DB plus our own curation. `backend/fooddata/` and `exercisedata/` download them, validate every row (diet class, plausible calories, cross-checks), and load them into the database. Dishes like idli are **calculated from recipes** (raw ingredient weights plus cooked weight). A food shows "values being checked" until a person signs it off (`reviewed_by`). Today: 277 foods, 152 household units, 102 exercises. Poha is a known gap (no verified source), and nothing is invented to fill it. Credits and licences are on the Data sources page.

## 5. The database in one minute
27 tables, all with row-level security. The ones to know:
`profiles`, `health_screening`, `goals`, `calculated_targets` (who you are and your numbers) · `body_weight_entries` · `foods`, `food_synonyms`, `food_units`, `exercises` (shared reference data) · `meal_plans` + `meal_plan_items`, `workout_plans` + days + exercises (approved plans) · `plan_proposals` (everything waiting for a yes) · `meal_logs` + `meal_log_items` · `chat_conversations`, `chat_messages` · `agent_runs` (cost log; no user policy on purpose) · a separate `langgraph` schema where the paused chat state lives. Some tables exist for later features and are empty (for example `workout_logs`, `weekly_checkins`).

## 6. Glossary
- **Token (JWT)**: signed proof of identity sent with every request.
- **RLS (row-level security)**: the database refuses to show a row to someone who does not own it.
- **Proposal**: a saved suggestion waiting for the user's Approve or Reject.
- **Router / specialist / composer**: the chat's three roles: choose who answers, answer from tools, merge several answers.
- **Tool**: a function the model may call (a database lookup or a calculation). It runs as you, and it is on an allowlist per specialist.
- **Guard**: a code check, without AI, on what comes in or goes out.
- **LangGraph / interrupt / checkpoint**: the library that runs the chat as a graph; an `interrupt` pauses it for your approval; a checkpoint saves its state so it can resume.
- **Eval / pass line**: a repeatable test of AI quality and the minimum score it must reach.
- **Token (AI)**: a unit of text the model reads or writes; cost is counted in them.
- **Small / mid tier**: two Gemini models; the cheaper one for chat, the stronger one only for generating plans.

## 7. A 5-minute talk track
1. (30 s) "This is a fitness coach where the AI is deliberately on a short leash." State the four ideas from section 2.
2. (60 s) Sign up, onboarding, land on Home: "These targets come from a tested formula with safety limits, not from the AI." Open the "why these numbers" list.
3. (60 s) Generate the meal plan, open "How this plan was made": "The AI chose some days, code chose others, and every plan passed these checks." Press Approve: "Nothing is saved until I do."
4. (45 s) Home: log a meal, watch the dashboard bar move; log weights with the Date box and watch the chart and goal date.
5. (90 s) Chat: tap the starter questions; ask "how many calories do I have left today" ("code worked that out, the AI only read it"); say "I ate 2 rotis and dal for lunch" and show the confirm card before approving.
6. (30 s) Open "How the AI works": rules, eval scores against pass lines, your own usage and cost.
7. (15 s) Close: "Every claim here is backed by a test; the guard evals and the 50-question audit are in the repository."

## 8. Questions you may be asked
- **Why not let the AI compute calories?** Models make arithmetic mistakes and confidently invent numbers; a wrong calorie target is a health risk. So the maths is code with unit tests.
- **How do you stop it inventing foods?** It can only choose from lists returned by tools, and code checks every key against the database again before saving.
- **What stops it changing my plan?** It can only create proposals; saving needs your approval; approval re-validates in code.
- **Can one user see another's data?** No: the database enforces it (row-level security), independent of our code.
- **How do you know it is accurate?** Evals with pass lines, the guard regression gate, and a 50-question audit that found and fixed 11 problems; the numbers are on the "How the AI works" page.
- **What does it cost?** A chat message is a few small-model calls (in our logs, 10 calls for four questions cost about $0.003); a 7-day plan is about $0.04 to $0.07. Every call is logged.
- **What if Gemini is down or busy?** Calls are retried with backoff; if it still fails the user gets a friendly message; meal and workout plans fall back to code picks so a plan still arrives.
- **Why specialists instead of one big agent?** Smaller prompts, a smaller tool allowlist per job, easier to test and to keep safe.
- **How does it remember the conversation?** The last 6 messages plus a short, code-checked rolling summary, never the whole history (cost and privacy).
- **What about someone with an eating-disorder history?** The server removes every calorie, macro and weight number for them, in plans, dashboard, weight log and chat.
- **What is not finished?** (Answer plainly, section 10.)
- **Is the nutrition data reliable?** Open government datasets; each row is cross-checked and labelled "ready" or "values being checked" until someone signs it off. Recipe values are calculated, not typed.

## 9. Reading order: the 10 files that explain the project
1. `backend/app/safety/safety_config.py` (the limits; 5 minutes)
2. `backend/app/calc/engine.py` and `clamps.py` (targets and how limits apply)
3. `backend/app/db/transactions.py` and `core/auth.py` (identity and privacy)
4. `backend/app/workflows/generate_meal_plan.py` and `decide_proposal.py` (propose, then approve)
5. `backend/app/calc/meal_solver.py` (the code that does the portions; skim the docstring)
6. `backend/app/agents/chat_graph.py` (the chat, top docstring and the graph at the bottom)
7. `backend/app/agents/runner.py` and `spec.py` (how a specialist is built and limited)
8. `backend/app/agents/plan_tools.py` and `log_tools.py` (what tools look like: typed arguments, no user field)
9. `backend/app/safety/guards.py` and `agents/claims.py` (the code that stops bad input and over-claims)
10. `backend/evals/run_llm.py` and `evals/llm_thresholds.json` (how quality is measured)

Then on the frontend: `frontend/src/App.tsx` (the routes), `lib/api.ts`, `pages/HomePage.tsx`, `chat/ChatPage.tsx`.

## 10. What the demo model does not do (say this plainly if asked)
- It runs on a laptop; it is not deployed.
- No weekly check-in or weekly chart, and no workout logging yet. Planned for later (see `docs/PROGRESS.md`): workout logging, and a coach that reads the logs and messages the user on its own (as suggestions only, never overriding the user).
- The chat cannot create or change plans (those are on the plan screens) and cannot edit or delete a logged meal. It answers with whole replies, not streaming.
- Two cuisines (Indian; Mediterranean and Middle Eastern), English only.
- Some foods and all recipes are drafts marked "values being checked" until reviewed.
- The visual design is functional, not polished.
- It uses the free Gemini tier with test data; real users would need the paid tier first.

## 11. Commands you will use
```powershell
# run it (two terminals)
cd backend ; uv run uvicorn app.main:app --reload      # http://127.0.0.1:8000  (docs at /docs)
cd frontend ; npm run dev                              # http://localhost:5173

# check the demo works for a brand-new account (20 steps, about a cent with --chat)
cd backend ; uv run python scripts/demo_check.py --chat

# tests and evals
cd backend ; uv run pytest ; uv run pytest -m db ; uv run python -m evals.run
cd backend ; uv run python -m evals.run_llm router     # also: specialists, nutrition, summary
cd frontend ; npm test
```
