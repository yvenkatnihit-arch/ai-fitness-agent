# Progress — AI Fitness Agent

Updated at the end of every step. Format: `[x]` done, `[~]` in progress, `[ ]` not started.

## Current status

**Phase:** 5 — Exercise library, in progress (Phase 4 food data COMPLETE 2026-11-06).
**Decisions logged:** D-003 to D-042 (D-042 = added requirements, see below).
**Phase 5:** 5.1 Free Exercise DB download + reader + find done (D-041). 5.2 (102 exercises + validator + report) and 5.3 (loaded into Supabase) done. Phase 5 COMPLETE: 5.1–5.4 committed (`f33b756`); 5.5 library screen done, not committed. Design foundation D.1 (D-044) and 6.0 (pace + cuisine in onboarding) committed (`9976e0d`). 6.1 (pace changes the calorie target inside the safety limits, D-045) done, not committed. Next: 6.2 (workout split recommender).
**Last completed:** 3.10: frontend live at https://ai-fitness-agent-one.vercel.app (D-036). Checked: no secrets in public JS, backend URL baked in, SPA reloads, security headers, CORS from the Vercel origin, and a full onboarding through production (targets match a hand calculation). Venkat tested sign-up → onboarding → targets on the live site: works.
**Earlier:** 3.9: backend live on Render at https://ai-fitness-agent-5dq9.onrender.com (Docker, Singapore, Free). Dockerfile + `.dockerignore`; image checked locally, then the same checks pass on Render (health, ready, CORS, real Supabase token on `/me`, onboarding status, 422). First deploy failed on the build context (fixed in Render settings, see D-033).
**Earlier:** 3.8: results screen (`targets/TargetsView.tsx`): daily calories (Indian digit grouping) and macros exactly as the backend sent them, "Why these numbers", doctor note, habits view with no numbers for eating-disorder history; home loads `/targets/current` once onboarding is done. 48 frontend tests, build, lint passing.
**Earlier:** 3.7: onboarding screens for goal, food preferences (disliked-food chips), training (equipment, days) and health check (explicit Yes/No for all 6, injury areas), plus a Finish screen that calls `POST /onboarding/complete`. Shared `useSaveStep` hook and `Choice` component; `onboarding/options.ts` with a test that reads the backend's Python files and checks every option list matches. 43 frontend tests, build, lint passing. Venkat confirmed sign-up → consent → basics works in the browser.
**Earlier:** 3.6: `lib/api.ts` (token on every call, our error format → `ApiError` with field errors + request ID, "can't reach the server" message), `/onboarding` page driven by `GET /onboarding/status`, consent step (draft privacy notice `2026-11-draft`) and basics step, home redirects unfinished users to onboarding. 28 frontend tests, build, lint passing.
**Earlier:** 3.5: frontend sign up / sign in with supabase-js (Auth only), `AuthProvider` + `RequireAuth` + `/sign-in` page with friendly errors, react-router; `frontend/.npmrc` dependency-age rule (D-030), 5 frontend packages pinned older and tree rebuilt; `frontend/.env` created from public values; "Confirm email" already off (D-031 needs no dashboard change). 17 frontend tests, build, lint passing.
**Earlier:** 3.4: CORS (exact origins, no cookies), one error format with request_id (422 lists fields without echoing values; 500 generic; PoolTimeout → 503), JSON request logs with X-Request-ID (`app/core/{middleware,errors,logging}.py`), `LOG_LEVEL` setting, settings split so the app imports without `.env` (D-035). 1114 fast + 160 DB tests passing.
**Earlier:** 3.3: `POST /onboarding/complete` (`app/workflows/complete_onboarding.py`: read as user → `calculate_targets()` → one admin transaction marks onboarded + inserts targets; double-submit safe) and `GET /targets/current`. Display rounding + plain-English reasons + doctor note (`app/schemas/targets.py`); eating-disorder history → no numbers returned. Cross-user API tests (moved from 2.9). 1099 fast + 160 DB tests passing; 0 rows left behind.
**Earlier:** 3.2: onboarding endpoints (`app/api/onboarding.py` → `app/db/onboarding.py`, all under RLS): `GET /onboarding/status`, `PUT /onboarding/{consent,basics,goal,preferences,training,screening}`. Consent first (409), goal needs basics (409), target-weight direction check (`app/calc/goals.py`, 422), locked after onboarding (409). Migration 8: `profiles.consent_version`. 1096 fast + 153 DB tests passing; 0 rows left behind.
**Earlier:** 3.1: onboarding request models (`app/schemas/onboarding.py`), `app/calc/age.py`, `app/core/vocabulary.py`, `app/core/time.py`.
**Phase 4:** 4.0 licence review (D-037), 4.2 downloads, 4.3a readers + checks, 4.3b carb basis (D-038) + review report, 4.3c 121 ingredients, 4.3d 72 cooked dishes, 4.4a recipe calculator + 4.4b 11 recipes (total 95 ready, 84 review, 14 gaps), 4.5a 179 foods + 280 synonyms loaded into Supabase (D-039), 4.5b 96 household units (D-040), 4.6 food search endpoint, 4.7a meal logging endpoints, 4.7b meal logging screen (Venkat tested it), 4.8 data sources page done. 4.1: Venkat sends the two permission emails.
**Last commit:** `126a608` (4.7b). Step 4.8 not committed yet.
**Phase 2 check questions:** skipped for now; can revisit anytime.
**Phase 1 check questions:** skipped for now; can revisit anytime.

## Phase 0 — Setup

- [x] 0.1 Create repo folder structure and git init
- [x] 0.2 Backend skeleton: FastAPI "hello" + `/health` endpoint + pytest
  - Known: pytest shows a `StarletteDeprecationWarning` suggesting `httpx2`. Harmless. Not switching until we verify that package on the official Starlette changelog/PyPI.
- [x] 0.3 `.env.example`, config module (pydantic-settings), `.gitignore`
  - `.env` lives in `backend/` (the frontend will get its own in 0.4). Gemini model IDs are blank until 0.5.
- [x] 0.4 Frontend skeleton: Vite + React + TS + Tailwind showing a page
  - Tests: Vitest + Testing Library (`npm test`). `frontend/.env.example` holds public `VITE_*` values only.
- [x] 0.5 Accounts: Google AI Studio, GitHub, Supabase done. LangSmith (Phase 7), Vercel and Render (Phase 3) later.
- [x] 0.6 Fill in the `Commands` section of CLAUDE.md

**Phase 0 complete (2026-11-05).** Backend: 5 tests. Frontend: 1 test. Gemini, Supabase, and GitHub all verified.

## Phase 1 — Calculation engine

- [x] 1.1 `safety_config.py` (all limits in one place)
- [x] 1.2 BMR (Mifflin-St Jeor) + tests
- [x] 1.3 TDEE (activity multipliers) + tests
- [x] 1.4 Calorie target by goal + tests (caps are applied in 1.5)
- [x] 1.5 Safety clamps (calorie floor, 25% deficit cap, 1%/week rate cap, screening flags) + tests
- [x] 1.6 Macros (protein per kg, fat floor, carbs remainder) + tests
- [x] 1.7 `calculate_targets()` that ties 1.2-1.6 together + tests (debug endpoint skipped; Phase 3 builds the real one)

**Phase 1 complete (2026-11-05).** `backend/app/calc/`: `bmr.py`, `tdee.py`, `targets.py`, `clamps.py`, `macros.py`, `engine.py`, `validation.py`. All limits in `safety/safety_config.py`. 997 backend tests (most are property tests over input grids).

## Phase 2 — Database and auth

- [x] 2.1 Migration tooling + `profiles` (RLS, `updated_at` trigger)
- [x] 2.2 `health_screening`, `goals`, `calculated_targets`
- [x] 2.3 Reference tables: `foods`, `food_synonyms`, `food_units`, `exercises` (read-only)
- [x] 2.4 Plans: meal/workout plan tables + `plan_proposals`
- [x] 2.5 Logs: meal logs, workout logs, `body_weight_entries`, `weekly_checkins` + Data API turned off (D-028)
- [x] 2.6 Chat and costs: `conversations`, `messages`, `conversation_summaries`, `agent_runs`, `usage_counters` + daily-cost view
- [x] 2.7 Backend DB layer (`app/db/`, queries under RLS per D-025) + `/ready` DB check
- [x] 2.8 Auth: verify Supabase JWT in FastAPI + `/me`
- [→] 2.9 RLS tests with two users **through the API**: moved to Phase 3 (only `/me` exists so far). Table-level cross-user RLS is already tested for every table group.
- [x] 2.10 LangGraph checkpointer connection test (D-012) + dependency-age policy (D-030)

**Phase 2 complete (2026-11-05).** 7 migrations: 27 tables + 1 view, RLS everywhere, user-written vs server-written split (D-027), Data API off (D-028). Backend: `app/db/` (pool, `user_transaction`, `admin_transaction`), `app/core/auth.py` (ES256 JWT), `GET /me`, `/ready`, `app/agents/checkpointer.py`. Scripts: `migrate.py`, `daily_cost.py`. 1024 fast + 146 DB tests.

## Phase 3 — Onboarding + first deployment

Decisions: D-031 (email confirmation off for now), D-032 (supabase-js for Auth only), D-033 (local Docker build), D-034 (only Venkat uses the deployed app).

- [x] 3.1 Onboarding request models (Pydantic): 18+, ranges, allowed values
- [x] 3.2 Endpoints: save profile, screening, goal, first weigh-in (under RLS)
- [x] 3.3 `POST /onboarding/complete` (consent check → `calculate_targets()` → save targets) + API-level cross-user tests (moved from 2.9)
- [x] 3.4 CORS, consistent error responses, structured logging
- [x] 3.5 Frontend: sign up / sign in (Supabase Auth), protected pages
- [x] 3.6 Frontend API helper (attaches token) + onboarding step 1: consent + basics
- [x] 3.7 Onboarding steps 2–4: goal & activity, diet & preferences, equipment & schedule, screening
- [x] 3.8 Results screen: targets, reasons, doctor note, habits view
- [x] 3.9 Backend Dockerfile (built locally) + deploy to Render: https://ai-fitness-agent-5dq9.onrender.com
- [x] 3.10 Frontend deploy to Vercel + end-to-end check in production: live, checked by script, and tested by Venkat (2026-11-05)
- [x] 3.11 (requested by Venkat) Macro donut chart on the results screen: `calorie_shares()` in `app/calc/macros.py` (largest-remainder rounding, always sums to 100, tested) → `protein_pct/carbs_pct/fat_pct` in the targets API (hidden in the habits view); `targets/MacroDonut.tsx` draws an SVG donut (calorie total in the centre, 2.5 px gaps, segment tooltips, screen-reader summary) + a legend with grams and %. Colours from the data-viz palette, validated (CVD-safe; aqua <3:1 on white, so values are always shown as text). 1271 backend fast + 7 DB onboarding-complete + 50 frontend tests passing. Venkat tested locally; deployed as `c7cceef` (live API sends 33/42/25 for the test person; live site includes the donut; no secret keys in the public JS. The two `sb_secret_` text matches are key-type checks in supabase-js and our own guard, not keys).

**Phase 3 complete (2026-11-05)** apart from the optional 3.11. Live: https://ai-fitness-agent-one.vercel.app (Vercel) → https://ai-fitness-agent-5dq9.onrender.com (Render) → Supabase.

## Phase 4 — Food data (D-037: open data now + permission requests in parallel)

- [x] 4.0 Dataset license and format review (IFCT 2017, INDB, USDA FDC, UK CoFID) → D-037
- [~] 4.1 Permission request emails to NIN (IFCT 2017) and the INDB authors: drafted by Claude, **sent by Venkat**
- [x] 4.2 Download script (`backend/fooddata/download.py`) for USDA SR Legacy (7,793 foods) + UK CoFID 2021 → `data/raw/` (git-ignored); archive + expected-files checks; URL, date, size, SHA-256 in `data/sources.json`; refuses silently changed upstream files. USDA Foundation 2026-10 dropped: it lacks per-food summary files (recorded under `_not_used`).
- [x] 4.3a Readers (`fooddata/usda.py`, `fooddata/cofid.py` → `FoodRecord`; CoFID `Tr` → 0, `N` → unknown, never 0) + **validation checks** (`fooddata/checks.py`: required values, ranges, macro mass, energy using each source's carb basis, diet-class rules, duplicates, cross-source) + `fooddata/audit.py`. 44 tests. Audit: USDA 7,710/7,793 pass (83 energy warnings, e.g. chocolate: real food-specific factors); CoFID 2,844/2,887 pass (34 unmeasured spices, 5 carbs >100 g from monosaccharide equivalents). openpyxl added as a dev dependency.
- [x] 4.3b Carb basis decided (D-038: available carbs as weighed, fibre separate) → `fooddata/carbs.py` (tested); `fooddata/find.py` search tool; **first batch of 66 ingredients** in `data/ingredients.csv` (exact source ids, Indian names, diet class, match quality, cross-check ids); `fooddata/build.py` → `data/foods_validated.csv` + `data/reports/ingredients_review.md`. Result: 52 ready, 9 to review, 0 blocked, 5 gaps (ragi, bajra, poha, rohu, jaggery: need IFCT). The first build blocked 6 rows on false diet alarms (USDA's "Dairy and **Egg** Products" category, "coconut meat", "soya paneer"): the rule was refined (egg/dairy words checked on names only) and every case is now a test. Lauki moved to USDA "white-flowered gourd (calabash)" because CoFID lacks its carb breakdown. 72 food-pipeline tests.
- [x] 4.3c +55 ingredients (spices, aromatics, more vegetables/fruit, dairy, flours, breads, seeds): **121 total → 87 ready, 22 to review, 0 blocked, 12 gaps**. Careful non-matches recorded as gaps: makhana ≠ USDA "lotus seeds", semiya ≠ soy vermicelli, suran ≠ "yam"; lal mirch = USDA red/cayenne pepper (not the US "chili powder" blend). Diet rule refined again (vanaspati/"vegetable ghee", coconut milk "grated meat"), each as a test. 76 food-pipeline tests. Assumed (Venkat can change): close matches kept and flagged; guava kept (USDA 68 vs CoFID 26 kcal), to be replaced when IFCT arrives.
- [x] 4.3d CoFID's Indian dishes: 72 dish rows (59 mapped, 13 gaps: idli, dosa, upma, rasam, kadhi, keema, kheer, rasgulla, barfi, jalebi, ladoo, papad, chivda). New `check_dish_plausibility` (kcal/100 g bands per `dish_*` category, warning). Diet rule: dishes are vegan only when CoFID says "with vegetable oil" or the item is plain boiled; other homemade recipes are vegetarian until the fat is confirmed. Fixed a false alarm: "Eggs, chicken, …" is a hen's egg. Build: 193 rows → 95 ready, 73 review, 0 blocked, 25 gaps. 87 tests pass.
- [ ] Venkat reviews `data/reports/ingredients_review.md` ("To review" + "Gaps")
- [x] 4.4a Recipe calculator (`fooddata/recipes.py`): `data/recipes.csv` + `data/recipe_items.csv` (raw grams + cooked weight) → per 100 g cooked; diet class computed from ingredients (strictest wins); checks: validated ingredients only, energy/macros, dish band, cooked÷raw 0.5–3×, fibre unknown if >5 % of weight unmeasured; recipes stay "review" until `reviewed_by` is filled. First 3: idli 145 kcal/100 g, dosa 224, upma 138. Build: 95 ready, 76 review, 0 blocked, 22 gaps. 103 tests pass.
- [x] 4.4b 8 more recipes: rasam 30 kcal/100 g, kadhi 66, keema 149, kheer 168, khoa 339, milk barfi 351, besan ladoo 521, roasted papad 298. New `dish_soup` band (10–120); sweets band up to 560. Still gaps on purpose: jalebi, rasgulla (syrup/oil uptake can't be estimated without measured data), chivda (needs poha). Build: 95 ready, 84 review, 0 blocked, 14 gaps (11 raw ingredients + 3 dishes). 106 food-data tests pass.
- [x] 4.5a Loader `fooddata/load.py` (D-039): migration adds `foods.key` (unique) + `review_status`; upsert by key in one transaction, synonyms from local names, stale foods reported not deleted. Loaded 179 foods (95 ready, 84 review) + 280 synonyms; second run = 0 inserted, 179 updated. Old DB tests now give their test foods a key. 1388 offline + 162 DB tests pass.
- [x] 4.5b Household units (D-040): `data/food_units.csv` → `fooddata/units.py` (methods: usda portion checked against USDA `food_portion.csv`, volume = katori 150 ml / glass 250 ml × measured USDA density, recipe piece) → `data/food_units_validated.csv` → `food_units`. 96 units loaded (e.g. katori sambar 152.8 g, katori rice 100.2 g, roti 43 g, idli 40 g, tsp oil 4.5 g). 1407 offline + DB tests pass.
- [ ] Venkat confirms katori = 150 ml and glass = 250 ml (D-040)
- [ ] Units still missing (no citable weight): paratha, puri, samosa, gulab jamun, paneer, pakora, sweets → logged in grams for now
- [x] 4.6 Food search endpoint `GET /foods/search?q=&limit=` (login required, RLS, no LLM): `app/api/foods.py`, `app/db/foods.py` (SQL: name/local-name contains, or trigram similarity > 0.3, or word_similarity ≥ 0.5, measured on our data), `app/db/food_ranking.py` (pure ranking: real matches before look-alikes → cooked before raw staples → exact > whole word > prefix > word prefix > contains → verified first → shorter names). Returns macros per 100 g, local names, `verified`, household units. Bugs found by real searches and fixed with tests: long names hid misspellings ("toor dhal"); "dal" ranked dalda/dalimbe first. ~120 ms per search. 1423 offline + 12 search DB tests pass.
- [ ] Venkat checks the 11 recipes in `data/recipes.csv` and fills `reviewed_by` (or says what to change)
- [ ] 4.4 target was ~100–150 dishes: now 83 (72 from CoFID + 11 recipes). More recipes (regional dishes, e.g. pongal, poha once poha has data, pesarattu, avial, thepla) can be added any time by editing the two recipe CSVs
- [ ] 4.5 Load into Supabase (`foods`), synonyms (dahi = curd, chawal = rice…), household units (katori, piece, cup…) with checks
- [ ] 4.6 Food search endpoint (fuzzy, synonyms, diet filter) + tests
- [x] 4.7a Meal logging endpoints (no LLM): `POST /meals` (slot, optional date: today to 7 days back, 1–20 items of food_id + quantity + unit; client never sends nutrition), `GET /meals?day=` (meals + day totals), `DELETE /meals/{id}`. Maths in `app/calc/portions.py` (grams = quantity × unit grams; nutrition = grams × per-100 g / 100; unit must be `g` or one the food has). Stored values are a snapshot. RLS: other users can't see or delete (tested). End-to-end check: 2 roti + 1 katori dal = 301.7 kcal (matches hand calculation). 1445 offline + 179 DB tests pass.
- [x] 4.7b Meal logging screen `/log` (linked from Home): meal slot (default from India time of day), debounced food search (300 ms, ≥ 2 letters, "values being checked" for unverified foods), amount + unit (the food's units + grams), draft list, save, today's meals with per-meal and day totals, delete. No nutrition maths in the browser: it sends foods + amounts and shows the backend's numbers. `api.delete` handles 204. 64 frontend tests pass; lint clean; build OK.
- [x] 4.8 Public `/sources` page (linked from sign-in and Home): each source's credit, release, licence link (OGL v3.0 for CoFID, CC0 for USDA), food count, plus how our recipes are computed. Content generated by `fooddata.build` from `data/sources.json` (+ homepage, license_url) into `frontend/src/sources/credits.json`; a backend test fails if the committed file is out of date, and a build error if a food comes from an uncredited source. 1449 backend + 67 frontend tests pass.

**Phase 4 complete (2026-11-06).** 179 foods in Supabase (98 USDA, 70 CoFID, 11 computed recipes; 95 verified, 84 in review), 280 local names, 96 household units, 14 recorded gaps. Every value passed tested checks (energy, macros, ranges, diet class, cross-source, dish bands). Search with misspellings and Indian names; meal logging via form with nutrition computed in code; credits page. Open items for Venkat: permission emails (IFCT, INDB), katori/glass sizes (D-040), recipe sign-off.

## Phase 5 — Exercise library (D-041: curate ~100, cross-check against Free Exercise DB)

- [x] 5.1 Free Exercise DB (The Unlicense, 876 exercises) pinned to commit `f00c92c7dcf1` (2026-09-27) with SHA-256 in `data/sources.json`; downloader now also verifies JSON lists (`format: json`, `expect_keys`). `exercisedata/freedb.py` reader (their "expert" → our "advanced"; missing equipment stays unknown), `exercisedata/find.py` to look up ids. Not in the Docker image (dev tool). 1453 tests pass.
- [x] 5.2 `data/exercises.csv`: 102 exercises (gym + home + bodyweight) with our own 2-4 line cues and conservative injury tags; `exercisedata/{records,rules,checks,build}.py`. Errors (block): vocabulary, cue count/length, gym machines must be location `gym`, missing injury tags (by movement pattern and by name, e.g. jumping → knee+ankle), unknown Free Exercise DB id, duplicates. Warnings (review): difficulty/equipment/main muscle disagree with the cited dataset entry. Status stays `review` until `reviewed_by` is filled. Output: `data/exercises_validated.csv` + `data/reports/exercises_review.md` (36 not cross-checked, 5 disagreements, 1 library gap: no bodyweight-only biceps move). 1487 tests pass. **Venkat: read the injury tags in the report.**
- [x] 5.3 Migration `20261106140000_exercises_key_review.sql` (`key` unique, `review_status`, `source_ref`; table was empty) applied. `exercisedata/load.py`: upsert by key in one transaction, cues stored one per line, never deletes, reports stale rows. 102 exercises loaded (all `review` until signed off); second run: 0 inserted, 102 updated. Two older DB tests needed a `key` in their test exercise. 1493 offline + 181 DB tests pass.
- [x] 5.4 `app/calc/exercise_filter.py` (pure rules: injury tags hide an exercise, harder than the user's level is hidden, place must match, at home only owned equipment, a gym is assumed to have all of it; `why_hidden` gives the reason) + `GET /exercises/for-me[?setting=gym|home]` (reads onboarding answers under RLS; "both" defaults to gym; 409 if the training or health step is missing, because unknown injuries are never treated as none). No LLM. 1517 offline + 186 DB tests pass.
- [x] 5.5 Exercise library screen `/exercises` (linked from Home): gym/home toggle (asks the backend, so equipment and place rules stay in one place), "Showing N of 102 … left out because of your knee", muscle chips and name search (in the browser, no extra request), cards with level, muscles, equipment and a "How to do it" fold-out with our cues, a safety note while tags are unsigned, 409 → "finish onboarding" link. 71 frontend tests pass; lint clean; build OK.

**Phase 5 complete (2026-11-06).** 102 curated exercises in Supabase (all `review` until Venkat signs off the injury tags), a validator and review report, a keyed idempotent loader, a pure filter by injury/level/place/equipment, `GET /exercises/for-me`, and the library screen. Open for Venkat: read the injury tags in `data/reports/exercises_review.md` and fill `reviewed_by` when happy (no changes requested so far). Next: the design foundation step (D-042), then Phase 6.

## Design foundation (D-042/D-044, after Phase 5)

- [x] D.1 Design tokens (light + dark) in `index.css`, fonts (Bricolage Grotesque + Source Sans 3), every raw palette colour swapped for a token across all screens, `PageShell` and `ButtonLink` shared components (Home, Meal log, Exercise library use them), `theme.test.ts` (token parity + WCAG AA contrast in both themes). 75 frontend tests pass; lint clean; build OK. **Venkat: look at it in the browser, in light and in dark (Windows: Settings → Personalization → Colors).** Not done: donut colours in dark mode; moving sign-in/onboarding to `PageShell`; any illustrations or motion (Phase 9 polish).

## Phase 7 notes (requested by Venkat, 2026-11-05)

- The coach chat must let users discuss diet, exercises, and more, grounded in *their* profile, targets, and plans (not generic answers). Depends on Phases 4–6 (food DB, exercise library, plans).

## Added requirements (Venkat, 2026-11-06; D-042, brief section 16)

Planned, not started. Order: finish Phase 5, then:
- [x] 6.0 Onboarding additions: pace (slow/normal/fast) saved on the goal, cuisine (Indian only) saved on the profile; migration `20261106160000_pace_and_cuisine.sql` applied (defaults `normal`/`indian`, so existing rows keep their meaning); both validated by the API (unknown values → 422, missing → default) and added to the Goal and Food-preferences screens; frontend/backend option lists checked against each other by `options.test.ts`; gym/home/both + equipment were already asked in the Training step. **Pace is stored only: it changes no numbers yet.** 1521 offline + 188 DB + 78 frontend tests pass.
- [x] 6.1 Pace in the calorie target (D-045): `GOAL_ADJUSTMENT[goal][pace]` table in `app/calc/targets.py` (fat loss -10/-20/-25%, muscle gain +4/+8/+10%, weight gain +5/+10/+10%, recomp -5/-10/-15%, fitness 0), `effective_pace()` holds "fast" to "normal" for anyone with a health flag and says why, engine + onboarding completion pass the saved pace, pace stored in `inputs`. Clamps unchanged and still run last. Tests: hand-calculated values for 11 goal/pace cases, ordering, a sweep of 300 combinations against every safety limit, and a database run with all three paces. 1542 offline + 190 DB tests pass. Hand-checked by example: 80 kg man, TDEE 2759 → slow 2483, normal 2207, fast 2069 kcal.
- [ ] 6.x Workout split recommender (PPL, Arnold, upper/lower, full body, bro split ...) + routine by experience level
- [ ] 6.x Goal-date prediction (pure Python, within safety limits)
- [ ] 6.x/9.x Edit workout per weekday (API, then screen)
- [ ] 7.x NeMo Guardrails (D-043): input + output rails layered on top of the code guards; compatibility check first (Python 3.14, D-030, image size, Gemini)
- [ ] 6.x/9.x Profile & settings: `PATCH /profile` (same validation as onboarding, recalculates targets when numbers change) + settings screen. Prerequisite for the bot editing the profile (D-046)
- [ ] 7.x Soreness/injury agent, then meal swap agent (right after the planned specialists, D-047); later: workout logger, "what can I eat now?"
- [ ] 8.x Consistency nudges (D-047): rules in code (missed logs, missed workouts, no weigh-in), one a day, cooldowns, opt-out, in-app via the help bot widget; scheduled daily trigger; `nudges` table
- [ ] 7.x Help bot `propose_profile_change` tool: proposal + confirmation card, user approves (D-046)
- [ ] 7.x Floating help bot (app guide, intent `app_help`) in the app shell
- [ ] 8.x/9.x Statistics for workouts and diet
- [ ] 9.x UI design foundation + polish (a small design-tokens step before the Phase 6 screens)
- [ ] Later (ask first): more cuisines, each with its own licence-checked data

## Phases 5-11

Phase 5 in progress; 6-11 not started. See `docs/PROJECT_BRIEF.md` section 14.

## Mock data / placeholders (`# MOCK:`)

- `frontend/src/onboarding/privacyNotice.ts`: **DRAFT** privacy notice (`2026-11-draft`). Not a mock, but must be reviewed (and the version bumped) before any friend signs up (D-034).

## Eval results

None yet (evals start in Phase 7).

## Reminders for later

- Before any friend enters real health data: enable Gemini billing (paid tier).
- **Before 2026-12-01:** `gemini-2.5-flash` gets routed to `gemini-3.5-flash-lite`. Decide whether to switch `.env` to the stable models (D-015).
- Verify the Tele-MANAS helpline number (14416) before shipping the crisis message.
- Check each nutrition dataset's license before importing (Phase 4).
- Frontend JS bundle is ~501 kB (145 kB gzipped), just over Vite's 500 kB advice; mostly supabase-js. Add route-level code splitting (`React.lazy`) in Phase 9/10.
- **Later (Venkat, 2026-11-05):** add a `docker-compose.yml` that starts backend + frontend with one command (`docker compose up`), plus a "how to run locally" section for other developers (their own Supabase project, `.env` files, `scripts/migrate.py`). Fits with the README in Phase 11.
- **Before friends join (D-034):** review the draft privacy notice (`frontend/src/onboarding/privacyNotice.ts`) and bump its version; turn email confirmation on with a real email provider (D-031); build data export and account deletion, which the notice promises (Phase 10); move DB tests off the real project (D-026).
