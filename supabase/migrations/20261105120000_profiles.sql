-- Migration 1: shared updated_at trigger + profiles table with RLS.

-- Keeps updated_at current on every UPDATE. Reused by every table that has updated_at.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- One row per user. id is the Supabase Auth user id.
-- Most columns are nullable because onboarding fills them in step by step.
-- Weight lives in body_weight_entries and goals in goals (later migrations), not here.
create table public.profiles (
  id               uuid primary key references auth.users (id) on delete cascade,
  display_name     text check (char_length(display_name) <= 80),
  date_of_birth    date check (date_of_birth > date '1900-01-01'),  -- 18+ is checked by the API
  sex              text check (sex in ('female', 'male', 'other')),
  height_cm        numeric(5, 1) check (height_cm between 120 and 230),  -- D-019
  activity_level   text check (activity_level in ('sedentary', 'light', 'moderate', 'active', 'very_active')),
  experience_level text check (experience_level in ('beginner', 'intermediate', 'advanced')),
  workout_location text check (workout_location in ('gym', 'home', 'both')),
  equipment        text[] not null default '{}',
  days_per_week    smallint check (days_per_week between 1 and 7),
  diet_type        text check (diet_type in ('vegetarian', 'non_vegetarian', 'eggetarian', 'vegan')),
  disliked_foods   text[] not null default '{}',
  consent_at       timestamptz,  -- when the user agreed to health-data processing (DPDP)
  onboarded_at     timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  -- Nobody finishes onboarding without consenting first.
  constraint profiles_consent_before_onboarding check (onboarded_at is null or consent_at is not null)
);

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- Row Level Security: a signed-in user can only see and change their own row.
alter table public.profiles enable row level security;

create policy profiles_select_own on public.profiles
  for select to authenticated
  using ((select auth.uid()) = id);

create policy profiles_insert_own on public.profiles
  for insert to authenticated
  with check ((select auth.uid()) = id);

create policy profiles_update_own on public.profiles
  for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

-- No delete policy: account deletion goes through the backend (Phase 10),
-- and deleting the auth user removes this row via ON DELETE CASCADE.

-- Signed-out visitors (the "anon" role) get no access at all.
revoke all on public.profiles from anon;
