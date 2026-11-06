-- Step 6.0 (D-042): two more onboarding answers.
--
-- goals.pace: how fast the user wants to go. It only chooses a point INSIDE the safety limits
--   (max deficit/surplus, max weekly loss in safety_config.py); it can never go beyond them.
--   'normal' is the default so every existing goal keeps its current meaning.
-- profiles.cuisine: which cuisine the meal plans come from. Only 'indian' has validated food
--   data today; adding a cuisine later means loading its foods first, then widening this list.

alter table public.goals
  add column pace text not null default 'normal' check (pace in ('slow', 'normal', 'fast'));

alter table public.profiles
  add column cuisine text not null default 'indian' check (cuisine in ('indian'));
