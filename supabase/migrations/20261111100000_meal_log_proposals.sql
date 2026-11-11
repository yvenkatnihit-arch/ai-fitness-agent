-- Step 8.5 (D-109): logging a meal by chat is a PROPOSAL the user confirms. It needs its own proposal type.
alter table public.plan_proposals drop constraint plan_proposals_type_check;
alter table public.plan_proposals
  add constraint plan_proposals_type_check
  check (type in ('meal_change', 'workout_change', 'profile_change', 'weekly_adjustment', 'meal_log'));
