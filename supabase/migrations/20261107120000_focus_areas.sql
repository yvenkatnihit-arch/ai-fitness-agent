-- Step 6.6g (D-060): up to two muscles the user wants to bring up. Empty = no focus.
-- Same list as backend FocusArea (app/core/vocabulary.py).
alter table public.profiles
  add column focus_areas text[] not null default '{}'
    check (cardinality(focus_areas) <= 2
           and focus_areas <@ array['chest', 'back', 'shoulders', 'biceps', 'triceps',
                                    'quads', 'hamstrings', 'glutes', 'calves', 'abs']);
