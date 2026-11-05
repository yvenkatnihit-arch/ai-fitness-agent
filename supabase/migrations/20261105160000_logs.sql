-- Migration 5: meal logs, workout logs, body weight, weekly check-ins.
--
-- Logs are USER-WRITTEN (D-028): the user's own records, reachable only through our
-- backend, which acts as the user (D-025) and computes nutrition in code before inserting.
-- Users may also delete their own log entries (fixing mistakes).
-- weekly_checkins is SERVER-WRITTEN (D-027): code decides adjustments, users only read.
--
-- logged_on is the user's local calendar date (set by the backend), so "today's totals"
-- don't depend on server time zones.

-- ---------------------------------------------------------------------------
-- Meal logs: one row per eating occasion, items per food.
-- ---------------------------------------------------------------------------
create table public.meal_logs (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  logged_on  date not null,
  slot       text not null
    check (slot in ('breakfast', 'mid_morning', 'lunch', 'evening_snack', 'dinner', 'other')),
  raw_text   text check (char_length(raw_text) <= 1000),  -- what the user typed in chat, if any
  source     text not null check (source in ('chat', 'form')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meal_logs_id_user unique (id, user_id)
);

create index meal_logs_user_day on public.meal_logs (user_id, logged_on desc);

create trigger meal_logs_set_updated_at
  before update on public.meal_logs
  for each row execute function public.set_updated_at();

create table public.meal_log_items (
  id               bigint generated always as identity primary key,
  meal_log_id      uuid not null,
  user_id          uuid not null,
  food_id          bigint not null references public.foods (id) on delete restrict,
  quantity         numeric(6, 2) not null check (quantity > 0),
  unit             text not null check (unit in
                     ('g', 'katori', 'piece', 'cup', 'glass', 'bowl', 'plate', 'slice', 'tbsp', 'tsp', 'handful')),
  grams            numeric(6, 1) not null check (grams > 0 and grams <= 3000),
  -- Snapshot computed by code from foods at logging time; later food fixes don't rewrite history.
  kcal             numeric(6, 1) not null check (kcal >= 0),
  protein_g        numeric(6, 1) not null check (protein_g >= 0),
  carbs_g          numeric(6, 1) not null check (carbs_g >= 0),
  fat_g            numeric(6, 1) not null check (fat_g >= 0),
  match_confidence numeric(3, 2) check (match_confidence between 0 and 1),  -- how sure the food match was
  created_at       timestamptz not null default now(),
  foreign key (meal_log_id, user_id) references public.meal_logs (id, user_id) on delete cascade
);

create index meal_log_items_log on public.meal_log_items (meal_log_id);

-- ---------------------------------------------------------------------------
-- Workout logs: one row per session, sets per exercise.
-- ---------------------------------------------------------------------------
create table public.workout_logs (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles (id) on delete cascade,
  logged_on    date not null,
  plan_day_id  uuid,  -- the planned day this session followed, if any
  duration_min smallint check (duration_min between 1 and 600),
  notes        text check (char_length(notes) <= 1000),
  source       text not null check (source in ('chat', 'form')),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint workout_logs_id_user unique (id, user_id),
  -- If the plan is deleted, keep the log and just forget the link (Postgres 15+ column list).
  foreign key (plan_day_id, user_id)
    references public.workout_plan_days (id, user_id) on delete set null (plan_day_id)
);

create index workout_logs_user_day on public.workout_logs (user_id, logged_on desc);

create trigger workout_logs_set_updated_at
  before update on public.workout_logs
  for each row execute function public.set_updated_at();

create table public.workout_log_sets (
  id             bigint generated always as identity primary key,
  workout_log_id uuid not null,
  user_id        uuid not null,
  exercise_id    bigint not null references public.exercises (id) on delete restrict,
  set_number     smallint not null check (set_number between 1 and 20),
  reps           smallint not null check (reps between 0 and 100),
  weight_kg      numeric(5, 1) check (weight_kg between 0 and 500),  -- null = bodyweight
  rpe            numeric(3, 1) check (rpe between 1 and 10),         -- effort, 10 = max
  created_at     timestamptz not null default now(),
  foreign key (workout_log_id, user_id) references public.workout_logs (id, user_id) on delete cascade,
  constraint workout_log_sets_unique unique (workout_log_id, exercise_id, set_number)
);

-- ---------------------------------------------------------------------------
-- Body weight: at most one entry per day (a second weigh-in replaces the first).
-- ---------------------------------------------------------------------------
create table public.body_weight_entries (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references public.profiles (id) on delete cascade,
  measured_on date not null,
  weight_kg   numeric(5, 2) not null check (weight_kg between 30 and 300),  -- D-019
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint body_weight_one_per_day unique (user_id, measured_on)
);

create trigger body_weight_entries_set_updated_at
  before update on public.body_weight_entries
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Weekly check-ins: what code concluded about the week (brief section 4.4).
-- ---------------------------------------------------------------------------
create table public.weekly_checkins (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles (id) on delete cascade,
  week_start          date not null check (extract(isodow from week_start) = 1),
  weigh_in_count      smallint not null check (weigh_in_count between 0 and 7),
  avg_weight_kg       numeric(5, 2) check (avg_weight_kg between 30 and 300),  -- 7-day average
  nutrition_adherence numeric(4, 3) check (nutrition_adherence between 0 and 1),
  workout_adherence   numeric(4, 3) check (workout_adherence between 0 and 1),
  decision            text not null check (decision in ('adjust', 'hold', 'need_data')),
  proposal_id         uuid references public.plan_proposals (id) on delete set null,
  summary             text check (char_length(summary) <= 1000),  -- short friendly text (small model)
  created_at          timestamptz not null default now(),
  constraint weekly_checkins_one_per_week unique (user_id, week_start),
  -- Fewer than 4 weigh-ins: never adjust (MIN_WEIGH_INS_FOR_CHECKIN in safety_config.py).
  constraint weekly_checkins_enough_data check (weigh_in_count >= 4 or decision = 'need_data')
);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.meal_logs enable row level security;
alter table public.meal_log_items enable row level security;
alter table public.workout_logs enable row level security;
alter table public.workout_log_sets enable row level security;
alter table public.body_weight_entries enable row level security;
alter table public.weekly_checkins enable row level security;

-- User-written logs: full access to own rows.
create policy meal_logs_own on public.meal_logs for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy meal_log_items_own on public.meal_log_items for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy workout_logs_own on public.workout_logs for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy workout_log_sets_own on public.workout_log_sets for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy body_weight_entries_own on public.body_weight_entries for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Server-written check-ins: read own only.
create policy weekly_checkins_select_own on public.weekly_checkins
  for select to authenticated using ((select auth.uid()) = user_id);
revoke insert, update, delete, truncate on public.weekly_checkins from authenticated;

revoke all on
  public.meal_logs, public.meal_log_items, public.workout_logs,
  public.workout_log_sets, public.body_weight_entries, public.weekly_checkins
  from anon;
