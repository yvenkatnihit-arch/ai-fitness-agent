-- Step 5.3 (D-041, same idea as D-039 for foods): a stable key for each exercise, whether a human has
-- signed it off, and where it was cross-checked.
--
-- key: our own id from data/exercises.csv ("goblet_squat"). The loader upserts by key, so re-running it
--      updates rows in place and their ids (which workout plans and logs point to) never change.
-- review_status: 'ready' = checks passed and a human signed off the injury tags;
--      'review' = loaded, but a warning or the sign-off is still open (data/reports/exercises_review.md).
-- source_ref: the Free Exercise DB id it was cross-checked against, or null when it has no equivalent.
--
-- The table is empty at this point (checked before writing this migration), so NOT NULL is safe.

alter table public.exercises
  add column key text not null check (key ~ '^[a-z][a-z0-9_]{1,59}$'),
  add column review_status text not null default 'review' check (review_status in ('ready', 'review')),
  add column source_ref text check (source_ref is null or char_length(source_ref) between 1 and 80);

alter table public.exercises add constraint exercises_key_unique unique (key);
