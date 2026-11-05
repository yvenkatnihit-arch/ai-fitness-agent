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
