-- Migration 3: shared reference tables (foods, food_synonyms, food_units, exercises).
-- Anyone signed in can READ them. Nobody can write from the app: only import scripts
-- using the admin connection (Phases 4-5). Data is loaded later; tables start empty.
-- IDs are small integers so the LLM can pick from lists cheaply (fewer tokens than UUIDs).

-- Fuzzy text matching ("dhal" finds "dal"). Supabase keeps extensions in their own schema.
create extension if not exists pg_trgm with schema extensions;

-- ---------------------------------------------------------------------------
-- foods: nutrition per 100 g. Every row records where its numbers came from.
-- ---------------------------------------------------------------------------
create table public.foods (
  id                 bigint generated always as identity primary key,
  name               text not null check (char_length(name) between 1 and 120),
  category           text,  -- e.g. cereal, pulse, dairy, curry; values set during Phase 4 import
  -- The most restrictive diet that can eat this food:
  --   vegan -> everyone; vegetarian (has dairy) -> veg, egg, non-veg;
  --   eggetarian (has egg) -> egg, non-veg; non_vegetarian -> non-veg only.
  diet_class         text not null check (diet_class in ('vegan', 'vegetarian', 'eggetarian', 'non_vegetarian')),
  is_dish            boolean not null default false,  -- cooked dish (dal tadka) vs ingredient (toor dal, raw)
  kcal_per_100g      numeric(6, 1) not null check (kcal_per_100g between 0 and 900),
  protein_g_per_100g numeric(5, 2) not null check (protein_g_per_100g between 0 and 100),
  carbs_g_per_100g   numeric(5, 2) not null check (carbs_g_per_100g between 0 and 100),
  fat_g_per_100g     numeric(5, 2) not null check (fat_g_per_100g between 0 and 100),
  fiber_g_per_100g   numeric(5, 2) check (fiber_g_per_100g between 0 and 100),
  source             text not null check (char_length(source) > 0),  -- e.g. IFCT2017, INDB, USDA_FDC
  source_ref         text,  -- the food's code or ID in that source
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  -- 100 g of food can't contain more than ~100 g of macros (small margin for rounding in sources).
  constraint foods_macros_fit_in_100g
    check (protein_g_per_100g + carbs_g_per_100g + fat_g_per_100g + coalesce(fiber_g_per_100g, 0) <= 105),
  constraint foods_unique_per_source unique (name, source)
);

create index foods_name_trgm on public.foods using gin (name extensions.gin_trgm_ops);
create index foods_diet_class on public.foods (diet_class);

create trigger foods_set_updated_at
  before update on public.foods
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- food_synonyms: other names people type (dahi = curd, chawal = rice).
-- ---------------------------------------------------------------------------
create table public.food_synonyms (
  id         bigint generated always as identity primary key,
  food_id    bigint not null references public.foods (id) on delete cascade,
  synonym    text not null check (char_length(synonym) between 1 and 120),
  created_at timestamptz not null default now()
);

create unique index food_synonyms_unique on public.food_synonyms (food_id, lower(synonym));
create index food_synonyms_trgm on public.food_synonyms using gin (synonym extensions.gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- food_units: household measures in grams for each food (1 katori dal = X g).
-- Count-based foods (roti, idli, egg) use 'piece'.
-- ---------------------------------------------------------------------------
create table public.food_units (
  food_id    bigint not null references public.foods (id) on delete cascade,
  unit       text not null
    check (unit in ('katori', 'piece', 'cup', 'glass', 'bowl', 'plate', 'slice', 'tbsp', 'tsp', 'handful')),
  grams      numeric(6, 1) not null check (grams > 0 and grams <= 2000),
  source     text not null check (char_length(source) > 0),  -- where this conversion came from
  created_at timestamptz not null default now(),
  primary key (food_id, unit)
);

-- ---------------------------------------------------------------------------
-- exercises: the curated library. Plans may only use exercises from this table.
-- ---------------------------------------------------------------------------
create table public.exercises (
  id                bigint generated always as identity primary key,
  name              text not null unique check (char_length(name) between 1 and 80),
  muscle_groups     text[] not null check (cardinality(muscle_groups) > 0),
  equipment         text[] not null default '{}',  -- empty = bodyweight only
  location          text not null check (location in ('gym', 'home', 'both')),
  difficulty        text not null check (difficulty in ('beginner', 'intermediate', 'advanced')),
  movement_pattern  text not null check (movement_pattern in (
                      'squat', 'hinge', 'lunge', 'push_horizontal', 'push_vertical',
                      'pull_horizontal', 'pull_vertical', 'carry', 'core', 'cardio', 'mobility')),
  form_cues         text not null check (char_length(form_cues) between 1 and 400),  -- 2-4 short lines
  -- Body areas this exercise can aggravate. Same tags as health_screening.injury_areas.
  contraindications text[] not null default '{}'
    check (contraindications <@ array['shoulder', 'knee', 'lower_back', 'neck', 'wrist', 'elbow', 'hip', 'ankle']),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index exercises_location on public.exercises (location);

create trigger exercises_set_updated_at
  before update on public.exercises
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: read-only for signed-in users, no access for signed-out visitors.
-- There are no insert/update/delete policies, so with RLS on nobody can write
-- through the app. The admin connection (import scripts) bypasses RLS.
-- ---------------------------------------------------------------------------
alter table public.foods enable row level security;
alter table public.food_synonyms enable row level security;
alter table public.food_units enable row level security;
alter table public.exercises enable row level security;

create policy foods_read on public.foods for select to authenticated using (true);
create policy food_synonyms_read on public.food_synonyms for select to authenticated using (true);
create policy food_units_read on public.food_units for select to authenticated using (true);
create policy exercises_read on public.exercises for select to authenticated using (true);

-- Belt and braces: also remove write privileges, so a missing policy isn't the only guard.
revoke insert, update, delete, truncate on public.foods, public.food_synonyms, public.food_units, public.exercises
  from authenticated;
revoke all on public.foods, public.food_synonyms, public.food_units, public.exercises from anon;
