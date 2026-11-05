-- Migration 4: meal plans, workout plans, plan proposals.
--
-- These are "server-written" tables (D-027): signed-in users can READ their own rows,
-- but only the backend writes them (plan generation, applying an approved proposal),
-- so nothing reaches a plan without passing code-side safety validation.
--
-- Child tables carry user_id too, tied to the parent with a composite foreign key
-- (parent_id, user_id). That keeps every RLS policy a simple "user_id = me" check
-- while making it impossible for a child row to belong to a different user than its parent.

-- calculated_targets becomes server-written as well: targets must come from the calc engine.
drop policy calculated_targets_insert_own on public.calculated_targets;
revoke insert, update, delete, truncate on public.calculated_targets from authenticated;

-- ---------------------------------------------------------------------------
-- Meal plans
-- ---------------------------------------------------------------------------
create table public.meal_plans (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles (id) on delete cascade,
  week_start  date not null check (extract(isodow from week_start) = 1),  -- always a Monday
  status      text not null default 'pending' check (status in ('pending', 'active', 'archived', 'rejected')),
  version     integer not null default 1 check (version > 0),
  targets_id  uuid references public.calculated_targets (id) on delete set null,  -- targets it was built for
  approved_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint meal_plans_id_user unique (id, user_id),  -- target for the children's composite FK
  constraint meal_plans_unique_version unique (user_id, week_start, version),
  constraint meal_plans_active_was_approved check (status <> 'active' or approved_at is not null)
);

create unique index meal_plans_one_active_per_user on public.meal_plans (user_id) where status = 'active';

create trigger meal_plans_set_updated_at
  before update on public.meal_plans
  for each row execute function public.set_updated_at();

create table public.meal_plan_items (
  id             bigint generated always as identity primary key,
  meal_plan_id   uuid not null,
  user_id        uuid not null,
  day_of_week    smallint not null check (day_of_week between 1 and 7),  -- 1 = Monday
  slot           text not null check (slot in ('breakfast', 'mid_morning', 'lunch', 'evening_snack', 'dinner')),
  position       smallint not null default 1 check (position > 0),
  food_id        bigint not null references public.foods (id) on delete restrict,
  grams          numeric(6, 1) not null check (grams > 0 and grams <= 2000),
  household_unit text check (household_unit in
                   ('katori', 'piece', 'cup', 'glass', 'bowl', 'plate', 'slice', 'tbsp', 'tsp', 'handful')),
  household_qty  numeric(5, 2) check (household_qty > 0),
  -- Nutrition for this portion, computed by code when the plan is built (snapshot).
  kcal           numeric(6, 1) not null check (kcal >= 0),
  protein_g      numeric(6, 1) not null check (protein_g >= 0),
  carbs_g        numeric(6, 1) not null check (carbs_g >= 0),
  fat_g          numeric(6, 1) not null check (fat_g >= 0),
  created_at     timestamptz not null default now(),
  foreign key (meal_plan_id, user_id) references public.meal_plans (id, user_id) on delete cascade,
  constraint meal_plan_items_unit_and_qty_together check ((household_unit is null) = (household_qty is null))
);

create index meal_plan_items_plan on public.meal_plan_items (meal_plan_id, day_of_week, slot);

-- ---------------------------------------------------------------------------
-- Workout plans: plan -> days -> exercises
-- ---------------------------------------------------------------------------
create table public.workout_plans (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles (id) on delete cascade,
  week_start  date not null check (extract(isodow from week_start) = 1),
  status      text not null default 'pending' check (status in ('pending', 'active', 'archived', 'rejected')),
  version     integer not null default 1 check (version > 0),
  approved_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint workout_plans_id_user unique (id, user_id),
  constraint workout_plans_unique_version unique (user_id, week_start, version),
  constraint workout_plans_active_was_approved check (status <> 'active' or approved_at is not null)
);

create unique index workout_plans_one_active_per_user on public.workout_plans (user_id) where status = 'active';

create trigger workout_plans_set_updated_at
  before update on public.workout_plans
  for each row execute function public.set_updated_at();

create table public.workout_plan_days (
  id              uuid primary key default gen_random_uuid(),
  workout_plan_id uuid not null,
  user_id         uuid not null,
  day_of_week     smallint not null check (day_of_week between 1 and 7),
  focus           text check (char_length(focus) <= 60),  -- e.g. "Upper body", "Legs", "Rest"
  is_rest         boolean not null default false,
  created_at      timestamptz not null default now(),
  foreign key (workout_plan_id, user_id) references public.workout_plans (id, user_id) on delete cascade,
  constraint workout_plan_days_id_user unique (id, user_id),
  constraint workout_plan_days_one_per_day unique (workout_plan_id, day_of_week)
);

create table public.workout_plan_exercises (
  id               bigint generated always as identity primary key,
  plan_day_id      uuid not null,
  user_id          uuid not null,
  exercise_id      bigint not null references public.exercises (id) on delete restrict,
  position         smallint not null check (position > 0),
  sets             smallint not null check (sets between 1 and 10),
  reps_min         smallint not null check (reps_min between 1 and 50),
  reps_max         smallint not null check (reps_max between 1 and 100),
  rest_sec         smallint not null check (rest_sec between 0 and 600),
  target_load_note text check (char_length(target_load_note) <= 120),  -- e.g. "RPE 7", "bodyweight"
  created_at       timestamptz not null default now(),
  foreign key (plan_day_id, user_id) references public.workout_plan_days (id, user_id) on delete cascade,
  constraint workout_plan_exercises_rep_range check (reps_max >= reps_min),
  constraint workout_plan_exercises_unique_position unique (plan_day_id, position)
);

-- ---------------------------------------------------------------------------
-- plan_proposals: every change an agent or the check-in suggests. Nothing changes
-- a plan or profile until the user approves; the backend then validates and applies it.
-- ---------------------------------------------------------------------------
create table public.plan_proposals (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  type       text not null check (type in ('meal_change', 'workout_change', 'profile_change', 'weekly_adjustment')),
  source     text not null check (source in ('chat', 'checkin', 'onboarding', 'plan_generation')),
  summary    text not null check (char_length(summary) between 1 and 500),  -- shown on the card
  payload    jsonb not null,  -- the exact change; its shape depends on type (D-006)
  status     text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'expired')),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- A decision time exists exactly when the proposal is no longer pending.
  constraint plan_proposals_decided_when_not_pending check ((status = 'pending') = (decided_at is null))
);

create index plan_proposals_pending on public.plan_proposals (user_id, created_at desc) where status = 'pending';

create trigger plan_proposals_set_updated_at
  before update on public.plan_proposals
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: read own rows only. No write policies + no write privileges = backend-only writes.
-- ---------------------------------------------------------------------------
alter table public.meal_plans enable row level security;
alter table public.meal_plan_items enable row level security;
alter table public.workout_plans enable row level security;
alter table public.workout_plan_days enable row level security;
alter table public.workout_plan_exercises enable row level security;
alter table public.plan_proposals enable row level security;

create policy meal_plans_select_own on public.meal_plans
  for select to authenticated using ((select auth.uid()) = user_id);
create policy meal_plan_items_select_own on public.meal_plan_items
  for select to authenticated using ((select auth.uid()) = user_id);
create policy workout_plans_select_own on public.workout_plans
  for select to authenticated using ((select auth.uid()) = user_id);
create policy workout_plan_days_select_own on public.workout_plan_days
  for select to authenticated using ((select auth.uid()) = user_id);
create policy workout_plan_exercises_select_own on public.workout_plan_exercises
  for select to authenticated using ((select auth.uid()) = user_id);
create policy plan_proposals_select_own on public.plan_proposals
  for select to authenticated using ((select auth.uid()) = user_id);

revoke insert, update, delete, truncate on
  public.meal_plans, public.meal_plan_items, public.workout_plans,
  public.workout_plan_days, public.workout_plan_exercises, public.plan_proposals
  from authenticated;
revoke all on
  public.meal_plans, public.meal_plan_items, public.workout_plans,
  public.workout_plan_days, public.workout_plan_exercises, public.plan_proposals
  from anon;
