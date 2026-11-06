-- Step 6.3 (D-048): the workout split the user picked, e.g. 'upper_lower_4'.
--
-- Only the SHAPE is checked here. Which keys exist (and whether a split fits the user's training days)
-- is decided in code (app/calc/splits.py), because the list of splits will grow and change.
-- null = the user has not chosen yet.

alter table public.profiles
  add column split_key text check (split_key is null or split_key ~ '^[a-z0-9_]{3,40}$');
