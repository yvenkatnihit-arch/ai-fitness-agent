-- Step 4.5a (D-039): a stable key for each food, and whether a human has reviewed its values.
--
-- key: our own id from data/ingredients.csv or data/recipes.csv ("toor_dal", "idli").
--      The loader upserts by key, so re-running it updates rows in place and their ids
--      (which meal plans and logs point to) never change.
-- review_status: 'ready' = every check passed; 'review' = loaded, but a warning or a
--      close match still needs a human look (see data/reports/ingredients_review.md).
--
-- The table is empty at this point (checked before writing this migration), so NOT NULL is safe.

alter table public.foods
  add column key text not null check (key ~ '^[a-z0-9_]{1,60}$'),
  add column review_status text not null default 'review' check (review_status in ('ready', 'review'));

alter table public.foods add constraint foods_key_unique unique (key);
