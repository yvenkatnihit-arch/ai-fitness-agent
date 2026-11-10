-- Step 7.10a (D-088): a user can choose SEVERAL cuisines, and every food belongs to one or more cuisines.
--
-- foods.cuisines: the cuisines a food belongs to (a shared ingredient such as olive oil or chickpeas can belong to several).
--   Every food loaded so far is Indian, so the default keeps them all valid. A new cuisine is added to the lists below only after its
--   foods are loaded (the same rule as before: no cuisine without validated, licence-checked food data).
-- profiles.cuisines: replaces profiles.cuisine (a single value). Existing rows keep their one cuisine, as a one-item list.

alter table public.foods
  add column cuisines text[] not null default array['indian']
  check (cuisines <@ array['indian'] and cardinality(cuisines) >= 1);

alter table public.profiles
  add column cuisines text[] not null default array['indian']
  check (cuisines <@ array['indian'] and cardinality(cuisines) between 1 and 5);

update public.profiles set cuisines = array[cuisine];

alter table public.profiles drop column cuisine;
