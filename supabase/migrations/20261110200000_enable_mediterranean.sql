-- Step 7.10e (D-094): the Mediterranean cuisine goes live (Mediterranean and Middle Eastern foods).
-- Both check lists are widened together with Cuisine in app/core/vocabulary.py (a test compares all three). The foods themselves are loaded
-- afterwards by `fooddata.load`, which holds back any food whose cuisine the app has not enabled.

alter table public.foods drop constraint foods_cuisines_check;
alter table public.foods
  add constraint foods_cuisines_check
  check (cuisines <@ array['indian', 'mediterranean'] and cardinality(cuisines) >= 1);

alter table public.profiles drop constraint profiles_cuisines_check;
alter table public.profiles
  add constraint profiles_cuisines_check
  check (cuisines <@ array['indian', 'mediterranean'] and cardinality(cuisines) between 1 and 5);
