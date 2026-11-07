-- Step 6.6f (D-057): how long a training session can last, in minutes.
-- null = not answered (accounts made before this question); plan generation then assumes 60.
alter table public.profiles
  add column session_minutes smallint check (session_minutes is null or session_minutes in (30, 45, 60, 90));
