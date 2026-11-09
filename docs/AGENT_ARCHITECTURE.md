# Agent architecture and project notes (written 2026-11-07, for picking the project back up)

Everything we discussed and decided about the agents, the harness and the roadmap, in one place.
Details and reasons live in `docs/DECISIONS.md` (D-numbers are given in brackets). Day-to-day status lives in
`docs/PROGRESS.md`. Diagrams are plain text: open this file in the editor (monospace) to see them aligned.

---

## 0. READ ME FIRST (where we are, what to do next)

**Built and committed (latest commit `e4a5ebe`):** onboarding, calorie/macro targets with safety limits, pace,
goal-date forecast, workout splits (recommend + choose), routine rules (sets/reps/rest), the LLM module (Gemini,
retries, cost logging), exercise picker (model picks, code validates), workout plan generation as a PENDING
proposal, approve/reject, the /workout screen, session length (30/45/60/90 min), focus areas (up to 2 muscles), the meal-plan food pool (6.7a), the portion solver (6.7b) the 7-day dish picker (6.7c) and meal plan proposals with approval (6.7d).

**Built, NOT committed yet:** Step 7.5, approvals in the chat (D-077): propose tools report pending proposals, the graph pauses
with `interrupt()` and resumes with the user's approve/reject (through the same workflow as the proposal cards); checked on the
real Postgres checkpointer across a new connection. Committed: harness core (7.1), nutrition specialist (7.2), router + parallel
spawn (7.3), composer with number check (7.4). **Phase 6 (plan generation) is complete** (edit-workout screen 6.9b committed).


**Next:** 7.6 NeMo Guardrails (input and output checks around the chat graph); then Phase 7 (agents: tool registry and ephemeral specialist factory first, 7.1). The
Phase 6 check questions are still open.

**Study guide:** `docs/FLOWS_GUIDE.pdf` explains the six flows to learn, in order, with worked examples.

**To resume, type:** `commit and go` (saves 7.5, then starts 7.6); the Phase 6 questions are still open.

**Run the app locally** (two terminals; if a command crashes with a segmentation fault, just run it again):
- Backend, in `backend/`: `uv run uvicorn app.main:app --reload`
- Frontend, in `frontend/`: `npm run dev` then open http://localhost:5173
- Tests: `uv run pytest -q` (offline), `uv run pytest -m db -q` (real Supabase), `npm test` (frontend)

**Rules that never change** (CLAUDE.md): one small step at a time, explain first, tests, then stop and wait for
"go"; the LLM never does math and never invents foods or exercises; safety limits live in `safety_config.py`;
no plan change without the user's approval; no secrets in code; every user table has RLS.

---

## 1. The big picture and the goal

The project is a portfolio piece that must look like an AI engineer built it, not a normal app with a chatbot
(D-061). So the backend uses real techniques, and every one must solve a real problem, be measurable, be tested,
and be **visible** (a trace, a metric, a "How this was made" panel).

Firm commitments (D-061): (1) meal planning where **the LLM selects and a solver computes**; (2) **LangGraph with
human-in-the-loop** approval; (3) **evals with a regression gate**; (6) **visible observability**.
Stretch: hybrid RAG with citations, adaptive TDEE estimation. A2A comes after Phase 7. Dynamic agents (planner and
bounded ad-hoc agents) are committed stretch goals (D-064). The frontend redesign comes AFTER the whole backend
(D-058, D-059, `docs/DESIGN_BRIEF.md`).

---

## 2. The flowcharts (one user message, all routes)

Five small diagrams instead of one huge one, so they stay readable. **2A** is the whole flow; **2B to 2D**
are the three routes; **2E** is the loop inside an agent; **2F** shows when agents live and die.

### 2A. The whole flow
```
                                   USER SENDS A MESSAGE
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | STEP 0  load the saved conversation state (checkpointer)                       |
    | STEP 1  INPUT GUARDRAILS (harness, plain code; NeMo rails)                     |
    |         daily limit | crisis or sharp-pain words | injection check             |
    |         build context: last 6 messages + rolling summary                       |
    +--------------------------------------------------------------------------------+
          crisis / blocked --> canned reply, NO LLM, NO agent, coaching paused
                                             |
                                             | ok
                                             v
    +--------------------------------------------------------------------------------+
    | STEP 2  ROUTER  (one small-model call, a graph node, not an agent)             |
    |         returns: intents[], risk_flag, needs_profile_update, route             |
    |         the harness checks the route and the specialists are allowed           |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | ROUTE A  predefined specialists (the core)   -> diagram 2B                     |
    | ROUTE B  planner, messy multi-part request   -> diagram 2C (stretch)           |
    | ROUTE C  ad-hoc agent, read-only questions   -> diagram 2D (stretch)           |
    | ROUTE D  no agent: ask a question, or a fixed answer                           |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | FACTORY builds one INSTANCE per task from a SPEC       <-- CREATED             |
    |   instance gets: tools bound to THIS user, empty private state,                |
    |   step / token / time counters                                                 |
    +--------------------------------------------------------------------------------+
                                             |
                                             | specialists run IN PARALLEL
                                             v
    +--------------------------------------------------------------------------------+
    | INNER AGENT LOOP (inside each instance, diagram 2E)                            |
    |   LLM <-> harness-checked tools, until a final answer or a limit               |
    +--------------------------------------------------------------------------------+
                                             |
                                             | one structured result only
                                             v
    +--------------------------------------------------------------------------------+
    | INSTANCE DISCARDED                                        <-- DELETED          |
    |   its private state, tool history and prompt are dropped                       |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | STEP 3  COMPOSER (small LLM call), skipped if only ONE specialist ran          |
    | STEP 4  OUTPUT GUARDRAILS (harness): no invented numbers, health wording       |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
                            REPLY + PROPOSAL CARDS to the user
                                             |
                                             | PENDING: graph pauses (interrupt), no agent alive
                                             v
    +--------------------------------------------------------------------------------+
    | user taps APPROVE: code validates AGAIN, saves in ONE transaction,             |
    |                   the old plan is archived, the new one is active              |
    | user taps REJECT:  nothing changes                                             |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | ALL THE WHILE: checkpointer saves state (Postgres)                             |
    |                one agent_runs row per LLM call (tokens, cost, latency)         |
    |                LangSmith trace -> the 'How this was made' panel                |
    +--------------------------------------------------------------------------------+
```

### 2B. Route A: predefined specialists (the core)
```
    +--------------------------------------------------------------------------------+
    | ROUTE A  predefined specialists                                                |
    | router intents: nutrition and/or workout and/or progress and/or help bot       |
    +--------------------------------------------------------------------------------+
                                             |
                                             | fan-out: one instance per intent
                                             v
    +--------------------------------------------------------------------------------+
    | Nutrition instance   Workout instance   Progress instance   Help bot           |
    | (later also: Soreness, Meal swap; each a new SPEC, no new machinery)           |
    +--------------------------------------------------------------------------------+
                                             |
                                             | each uses ITS OWN tool allowlist
                                             v
          results are merged into the shared state; instances are DELETED
```

### 2C. Route B: the planner (stretch goal, D-064)
```
    +--------------------------------------------------------------------------------+
    | ROUTE B  planner (stretch, after the evals)                                    |
    | e.g. 'I am travelling for a week, adjust everything'                           |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | PLANNER instance (created)  ->  returns an ORDERED PLAN of predefined          |
    | specs, e.g. [workout, nutrition, composer]  ->  planner DELETED                |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | HARNESS VALIDATES the plan: known specs only, size cap, sensible order         |
    +--------------------------------------------------------------------------------+
                                             |
                                             | valid
                                             v
    +--------------------------------------------------------------------------------+
    | for each step of the plan: the factory creates that specialist's               |
    | instance (as in Route A), it runs, returns, and is DELETED                     |
    +--------------------------------------------------------------------------------+
```

### 2D. Route C: the bounded ad-hoc agent (stretch goal, D-064)
```
    +--------------------------------------------------------------------------------+
    | ROUTE C  ad-hoc agent (stretch, after evals + red-team set)                    |
    | read-only question no specialist covers, e.g. 'why did my weight stall?'       |
    | if the user wants a CHANGE it is never ad-hoc (it cannot propose)              |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | BUILDER (one small LLM call, not an agent) writes a DRAFT spec:                |
    |   task description, wanted tools, requested limits                             |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | HARNESS VALIDATOR (plain code) makes the final spec:                           |
    |   + fixed safety preamble, always prepended, cannot be edited                  |
    |   + tools = wanted  INTERSECT  the READ-ONLY allowlist                         |
    |   + limits = min(requested, hard caps)                                         |
    |   + small model only, and NO proposals field in the output                     |
    +--------------------------------------------------------------------------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    | FACTORY creates the ad-hoc instance <-- CREATED; loop with read tools;         |
    | returns {answer, data}; instance DELETED; logged and shown as 'ad-hoc'         |
    +--------------------------------------------------------------------------------+
```

### 2E. The loop inside every instance
```
    +--------------------------------------------------------------------------------+
    | INNER LOOP of ONE instance (the standard agent loop)                           |
    |                                                                                |
    |   private state -> LLM call -> tool request?                                   |
    |       no  -> FINAL ANSWER {answer, data, proposals[]}                          |
    |       yes -> HARNESS CHECKS the request:                                       |
    |              1. is the tool on this spec's allowlist?  (else refused, logged)  |
    |              2. are the arguments valid? (typed, Pydantic)                     |
    |              3. user_id injected by the harness, never by the model            |
    |              4. run it as the user (RLS)                                       |
    |              5. steps / tokens / time still within limits?                     |
    |            -> add the result to the PRIVATE state -> LLM call again            |
    |                                                                                |
    | limit hit or timeout -> stop, use the spec's failure policy                    |
    +--------------------------------------------------------------------------------+
```

### 2F. When agents exist (one message, left to right)
```
                        step 0  step 1  step 2  step 3-5                   step 6  step 7  step 8   step 9  
    --------------------------------------------------------------------------------------------------------
    graph state         [=========================== saved, loaded, saved again ===========================]
    input guardrails            [=code=]
    router (LLM)                        [1 call]
    instances (A)                               [=CREATED > loop > DELETED]
    planner (B)                                 [=created > plan > deleted]
    builder (C)                                 [==1 call, then validator=]
    ad-hoc instance (C)                         [=CREATED > loop > DELETED]
    composer (LLM)                                                         [1 call]
    output guardrails                                                              [=code=]
    reply + pause                                                                          [waiting]
    approval + apply                                                                                [=code=]
    --------------------------------------------------------------------------------------------------------
    Instances (agents) exist ONLY inside step 3-5. Between messages nothing is alive.
```

Reading guide: **model calls** are only the router, the builder (route C), the planner (route B), the
specialist or ad-hoc loop, and the composer. **Everything else is harness** (plain code). The harness is
not one box; it is the layer around all of them.

---

## 3. Step by step: one message, and exactly when agents are created and deleted

Nothing agent-like lives between messages. Between messages there is only saved state.

| # | What happens | Model call? | Agent instance? |
|---|---|---|---|
| 0 | Message arrives. The graph run starts and the checkpointer loads the conversation state (layer 1). | no | none alive |
| 1 | Input guardrails: limit, crisis/injection check, build context (last 6 messages + summary). A crisis ends here with a canned reply. | no | none |
| 2 | Router (a node, not a spawned agent) reads the message and writes `intents`, `risk_flag`, `needs_profile_update`, `route` into the state. The harness checks the route is allowed. | yes (small) | none |
| 3A | **Route A:** the graph fans out (Send API). The factory **CREATES** one instance per needed specialist from our predefined specs. | no | **created** |
| 3B | **Route B:** the factory creates a planner instance; it returns a plan; it is **deleted**; the harness validates the plan; then each plan step creates its specialist instance (as in 3A). | yes | **created, then deleted, then more created** |
| 3C | **Route C:** the builder writes a draft spec, the harness validator turns it into a safe spec, the factory **CREATES** one ad-hoc instance (read-only tools). | yes (builder) | **created** |
| 4 | Each instance runs the inner loop: LLM asks for a tool, the harness checks and runs it as the user, the result goes back into the instance's private state, repeat until a final answer or a limit. | yes (small) | alive |
| 5 | Each instance returns ONE structured result (`{answer, data, proposals[]}`; ad-hoc has no `proposals`). It is **DELETED**: private state, tool history and prompt are discarded. A limit hit or timeout also ends it, with the spec's failure policy. | no | **deleted** |
| 6 | Composer merges the results into one reply (skipped when one specialist ran). | yes (small) | none |
| 7 | Output guardrails check the reply. | no | none |
| 8 | Reply and proposal cards go to the user. Pending proposals pause the graph; the state is saved; nothing is alive. | no | none |
| 9 | Later the user approves or rejects. The graph resumes, code re-validates and applies in one transaction (approve) or does nothing (reject). | no | none |
| 10 | Rolling summary updated when needed, layer-1 state saved, `agent_runs` and trace complete. The run ends. | maybe | none |

**Instances live only from step 3 to step 5.** The next message repeats from step 0 with brand-new instances.
What persists is the conversation state and the database, never an agent.

---

## 4. When is each route used?

The router proposes a route and the harness checks it against rules (it can only pick routes that exist and
specialists that are on the menu).

| Situation | Route |
|---|---|
| Crisis words, or sharp pain / swelling / numbness (brief section 7) | Safety: canned reply, no agent, coaching paused |
| The message fits 1 to 3 predefined specialists ("log my lunch", "what is today's workout?", "how do I change my split?") | **A** predefined specialists |
| `needs_profile_update` ("my weight is now 74 kg") | **A** help bot specialist, which creates a `profile_change` proposal; user approves (D-046) |
| Messy multi-part request with ordering ("I'm travelling for a week, adjust everything") | **B** planner (stretch, after evals) |
| Read-only analysis no specialist owns ("why has my weight stalled? compare the last 3 weeks") | **C** ad-hoc agent (stretch, after evals and red-team set) |
| No specialist fits AND the user wants a change | Ask a clarifying question or hand to the closest predefined specialist; **never** ad-hoc (ad-hoc cannot propose) |
| Greeting, thanks, simple app question with a fixed answer | **D** no agent |

**Ad-hoc agent in short (D-064):** the builder fills in a locked template; the harness (1) always prepends a fixed
safety preamble, (2) intersects requested tools with the READ-ONLY allowlist (propose tools are never granted),
(3) caps limits (the model can only ask for less), (4) uses the small model only, (5) removes the `proposals`
field from its output schema. It cannot write to the database, cannot create other agents, and is marked "ad-hoc"
in `agent_runs` and in the panel. Any change it suggests must go through a predefined specialist and the user's
approval. It ships only after the eval harness (7.7) and its red-team set pass.

---

## 5. The three layers of state

```
 LAYER 1  GRAPH STATE      shared, saved by the Postgres checkpointer, survives between messages
          messages (last 6 + summary) | intents | route | specialist results | proposals | reply
              ^ inputs                                   | results written back
              |                                          v
 LAYER 2  INSTANCE STATE   private to ONE instance, thrown away when it finishes
          its LLM messages | tool calls | tool results | step and token counters
              | tools read and write
              v
 LAYER 3  DATABASE         the source of truth (profile, targets, plans, logs, proposals, agent_runs)
          always reached through tools, as the user, under RLS
```

Parallel instances never see each other's layer 2. Their results meet only in layer 1.

---

## 6. The harness, the spec, the tools

**Harness** = all code around the model: context builder, tool layer (argument validation), identity and
permissions, loop control, output control (schema, repair once, code fallback), safety gates, state and memory,
observability, cost control, evals. Rule of thumb: **the model decides what to try; the harness decides what is
allowed and what happens next.**

**Spec** (data we write, reviewed and tested; no user data, no state, no secrets): `name`, `version`,
`description` and `intents` (for the router), `system_prompt`, `model_tier` and `temperature`, `tools` (the
allowlist), `output_schema`, `limits` (max steps, tokens, timeout, per-tool caps), `context_policy` (history
window, which profile fields it may see), `can_propose` (which proposal types), `failure_policy`, `eval_suite`.
Safety numbers (calorie floors, weekly set cap of 20 per muscle) stay in `safety_config.py`; a spec cannot
override them.

**Tool registry:** every tool is a typed function (Pydantic arguments) with a scope.
- READ tools: `search_food`, `get_targets`, `get_todays_workout`, forecast, and later log and stats readers.
- PROPOSE tools: `propose_meal_change`, `propose_workout_change`, `propose_profile_change` (create a PENDING
  proposal only). **No tool applies a change; only the user's approval does.**
- Plain-code calculators sit behind the tools (portion solver, targets, filters, routine rules).
- The harness injects `user_id` from the verified login (never a model argument), runs tools under RLS, refuses
  anything off the allowlist, and counts steps and tokens.

**Predefined versus dynamic:** specs are predefined by us; instances are created dynamically from them (D-063).
Route C is the one place the model writes a spec, inside the locked template (D-064).

**Workflows versus agents:** the Phase 6 plan generators (workout now, meal soon) are fixed code pipelines with
one model step (the picker). In chat, the workout and nutrition specialists will call them through PROPOSE tools.
Other non-chat flows (weekly check-in, nudges and reminders, D-047) will reuse the same harness.

---

## 7. Standard agent loop versus ours

The standard loop (state -> LLM -> tool request -> tool node -> result -> LLM ... -> final answer) exists unchanged
INSIDE each instance. Ours adds an outer system:

| | Standard single-agent loop | Our design |
|---|---|---|
| Shape | one agent, all tools | router, fan-out to short-lived specialists, composer |
| Tools | one shared list | per-specialist allowlist from a registry |
| User identity | often a tool argument | injected by the harness, never by the model |
| Side effects | tools may write directly | only propose tools; approval applies |
| State | one growing message list | private per instance; shared only for results |
| Limits | a recursion limit | steps, tokens, timeout, cost per instance |
| Bad output | whatever the model said | schema check, repair once, code fallback |
| Parallelism | sequential | specialists in parallel |
| Safety | prompt instructions | code rails in and out, approval pause |
| Debugging | one long trace | one logged run per instance, shown in a panel |
| Testing | one big prompt | each specialist alone, with a fake model |

---

## 8. Safety and defense in depth

- Safety limits in code (`safety_config.py`): calorie floors, deficit and surplus caps, 1% weekly loss cap, weekly
  sets per muscle cap, health-flag rules (flagged users: milder deficit, one set fewer, doctor note).
- The LLM never does math and never invents foods or exercises; it picks keys from filtered lists and code
  validates every pick (with one repair and a code fallback).
- No change without approval (proposals). Approval re-validates in code and saves in one transaction.
- Layers for the ad-hoc agent: preamble added by code, tools intersected with a read-only list, no `proposals`
  field, a database identity that cannot write, limits capped, guardrails on output. Each layer is enough alone.
- Free-tier Gemini may use prompts for training: test data only until billing is enabled (before friends join).

---

## 9. Roadmap

**Phase 6 (plan generation)**
- Done: 6.0 to 6.6g (see section 0).
- 6.7a food pool: done. Finding: the vegan pool is thin (4 protein and 3 vegetable dishes).
- 6.7b portion solver (mixed-integer linear programming, safety limits from the engine, household steps, no LLM): done.
- 6.7c dish picker + week builder (Gemini picks the week, code validates, solver portions, one repair round, week-aware
  fallback, mid-morning meal for big days): done.
- 6.7d save as pending meal proposal + approve (re-verified from the foods table): done.
- 6.7e meal plan screen with the "How this plan was made" panel: built, not committed. **Phase 6 complete.**

**Then:** Profile and settings (`PATCH /profile`; also lets existing users answer the session-length question), meal
swap and other small features as scheduled in PROGRESS.

**Phase 7 (agents, D-063, D-064)**
- 7.1 tool registry + ephemeral specialist factory, tested with a fake model (allowlist, user_id injection, step
  limit, no state leak).
- 7.2 first real specialist (food lookup). 7.3 router + parallel spawn. 7.4 composer.
- 7.5 human-in-the-loop approval via LangGraph `interrupt()`. 7.6 NeMo Guardrails (input and output).
- 7.7 evals + regression gate in CI + red-team set. 7.8 planner. 7.9 bounded ad-hoc agents (gated by 7.7).
- Later specialists (soreness, meal swap), help-bot profile changes by proposal, consistency nudges.
- Stretch: hybrid retrieval with citations; A2A (Agent Card, coach exposed as an A2A server); MCP server.

**Phase 8:** workout logging, water tracker (D-059), weekly check-in, stats data, adaptive TDEE (stretch),
auto-progression and deload weeks from logs (D-056). **Phase 9:** polish and stats pages.
**Phase 10-11:** deployment (Render + Vercel + Supabase) and the rest in PROGRESS.
**Frontend redesign (F phase):** only after the backend is complete; `docs/DESIGN_BRIEF.md` holds the prompt and the
decisions: dark and lime, no exercise or food images, no mic button, code-made insights, one self-hosted font,
water tracker yes, body composition no, notifications bell once reminders exist.

---

## 10. Decision index (what to read for the reasons)

| D- | Topic |
|---|---|
| 042 | Scope additions: weekday editing, help bot, levels, stats, cuisines, splits, pace, goal date, gym/home |
| 043 | NeMo Guardrails (build in Phase 7; compatibility verified) |
| 044 | Design tokens (superseded by dark-only in D-059 when the redesign lands) |
| 045-050 | Pace, profile edits by proposal, agent build order and nudges, splits, routine rules, goal forecast |
| 051 | One LLM module: tiers from .env, required max_tokens, retries, logging |
| 052-055 | Exercise picker, pending workout proposal, approve/reject, workout plan screen |
| 056-057, 060 | Library screen removed; session length; focus areas |
| 058-059 | Frontend redesign after the backend; the seven design decisions |
| 061 | Engineering showcase goals and technique list |
| 062 | Meal planning step 1: role-based food pool |
| 063 | Ephemeral specialists built from predefined specs |
| 064 | Planner and bounded ad-hoc agents (stretch, gated by evals) |

---

## 11. Open items (yours, and reminders)

**For you:** read the exercise injury tags (`data/reports/exercises_review.md`) and fill `reviewed_by` (you asked
for no changes); send the data-permission emails (IFCT, INDB); confirm katori 150 ml and glass 250 ml (D-040); sign
off the 11 recipes; answer the two D-046 questions (injury areas form-only? weight changes via chat?); add vegan
recipes if you want a varied vegan week (data work); try the new screens in a browser (/splits, /workout, Goal date
card, Training question, focus chips); the Phase 4 and 5 check questions are still unanswered.

**Reminders:** enable Gemini billing before friends use it (health data); `gemini-2.5-flash` is retired by Google
on 2026-12-01, change `GEMINI_SMALL_MODEL` and `GEMINI_MID_MODEL` in `backend/.env` before then; verify the
Tele-MANAS 14416 helpline; before-friends checklist (privacy notice, email confirmation, export/delete, move DB
tests off the real project); docker-compose and bundle code splitting later; self-host the chosen font.

---

## 12. Glossary

- **Agent:** an LLM that can call tools in a loop to finish a task.
- **Spec:** the written recipe for a kind of agent (prompt, tools, limits). Predefined by us.
- **Instance:** one running copy built from a spec for one task; deleted afterwards.
- **Factory:** the code that builds an instance from a spec.
- **Harness:** all the code around the model that controls what it sees and may do, and checks what it returns.
- **Tool registry:** the typed functions agents may call, each marked read or propose.
- **Proposal:** a suggested change that stays pending until the user approves it.
- **Router:** one small-model call that decides intents and the route.
- **Composer:** one small-model call that merges several specialist answers into one reply.
- **Checkpointer:** saves the graph's shared state in Postgres between messages.
- **Interrupt:** a LangGraph pause that waits for the user (used for approvals).
- **Guardrails:** code rules (NeMo) that check input and output.
- **Evals:** automated tests that score the agents on golden and adversarial cases; the regression gate fails a build that makes them worse.
- **Plan-and-execute:** a planner builds an ordered plan from predefined steps, then each step runs.
- **A2A:** Agent2Agent protocol, for agents from different systems to talk to each other (planned after Phase 7).
- **MCP:** Model Context Protocol, for agents to reach tools and data (optional later).
