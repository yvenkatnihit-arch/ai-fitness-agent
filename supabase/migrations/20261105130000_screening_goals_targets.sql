-- Migration 2: health_screening, goals, calculated_targets (all with RLS).

-- ---------------------------------------------------------------------------
-- health_screening: one row per user. Only the flags the safety rules need
-- (brief section 7: "store only the minimum"). No free-text medical notes.
-- Flag names match SCREENING_FLAGS in backend/app/safety/safety_config.py.
-- ---------------------------------------------------------------------------
create table public.health_screening (
  user_id                   uuid primary key references public.profiles (id) on delete cascade,
  pregnant_or_breastfeeding boolean not null default false,
  diabetes                  boolean not null default false,
  heart_or_bp               boolean not null default false,
  kidney                    boolean not null default false,
  recent_surgery_or_injury  boolean not null default false,
  eating_disorder_history   boolean not null default false,
  -- Body areas to protect in workouts. Same tags as exercise contraindications (Phase 5).
  injury_areas text[] not null default '{}'
    check (injury_areas <@ array['shoulder', 'knee', 'lower_back', 'neck', 'wrist', 'elbow', 'hip', 'ankle']),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger health_screening_set_updated_at
  before update on public.health_screening
  for each row execute function public.set_updated_at();

alter table public.health_screening enable row level security;

create policy health_screening_select_own on public.health_screening
  for select to authenticated using ((select auth.uid()) = user_id);
create policy health_screening_insert_own on public.health_screening
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy health_screening_update_own on public.health_screening
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

revoke all on public.health_screening from anon;

-- ---------------------------------------------------------------------------
-- goals: a user can have many goals over time, but only one active at once.
-- ---------------------------------------------------------------------------
create table public.goals (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles (id) on delete cascade,
  goal_type        text not null
    check (goal_type in ('fat_loss', 'muscle_gain', 'weight_gain', 'recomp', 'general_fitness')),
  start_weight_kg  numeric(5, 2) not null check (start_weight_kg between 30 and 300),  -- D-019
  target_weight_kg numeric(5, 2) check (target_weight_kg between 30 and 300),
  started_on       date not null default current_date,
  active           boolean not null default true,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- At most one active goal per user, enforced by the database itself.
create unique index goals_one_active_per_user on public.goals (user_id) where active;
create index goals_user_id on public.goals (user_id);

create trigger goals_set_updated_at
  before update on public.goals
  for each row execute function public.set_updated_at();

alter table public.goals enable row level security;

create policy goals_select_own on public.goals
  for select to authenticated using ((select auth.uid()) = user_id);
create policy goals_insert_own on public.goals
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy goals_update_own on public.goals
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

revoke all on public.goals from anon;

-- ---------------------------------------------------------------------------
-- calculated_targets: append-only history of the calculation engine's output
-- (backend/app/calc/engine.py). A recalculation adds a row; rows are never edited.
-- ---------------------------------------------------------------------------
create table public.calculated_targets (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles (id) on delete cascade,
  goal_id             uuid references public.goals (id) on delete set null,
  bmr_kcal            numeric(6, 1) not null check (bmr_kcal > 0),
  tdee_kcal           numeric(6, 1) not null check (tdee_kcal > 0),
  goal_target_kcal    numeric(6, 1) not null check (goal_target_kcal > 0),
  -- Last line of defence: never store a target below the lowest calorie floor.
  calorie_target_kcal numeric(6, 1) not null check (calorie_target_kcal between 1200 and 6000),
  protein_g           numeric(6, 1) not null check (protein_g >= 0),
  fat_g               numeric(6, 1) not null check (fat_g >= 0),
  carbs_g             numeric(6, 1) not null check (carbs_g >= 0),
  reasons             text[] not null default '{}',  -- e.g. {screening_deficit_cap}
  doctor_note         boolean not null default false,
  focus_on_habits     boolean not null default false,
  inputs              jsonb not null default '{}',   -- weight, activity level etc. used, for history
  effective_from      timestamptz not null default now(),
  created_at          timestamptz not null default now()
);

-- "Current targets" = newest row for the user.
create index calculated_targets_user_latest on public.calculated_targets (user_id, effective_from desc);

alter table public.calculated_targets enable row level security;

-- Read and add only. No update or delete policy: history can't be rewritten.
create policy calculated_targets_select_own on public.calculated_targets
  for select to authenticated using ((select auth.uid()) = user_id);
create policy calculated_targets_insert_own on public.calculated_targets
  for insert to authenticated with check ((select auth.uid()) = user_id);

revoke all on public.calculated_targets from anon;
