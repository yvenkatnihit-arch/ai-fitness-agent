-- Step 7.7b (D-081): evals make real model calls, and their cost must be logged like every other call, but separate from user flows.
alter table public.agent_runs drop constraint agent_runs_flow_check;
alter table public.agent_runs add constraint agent_runs_flow_check
  check (flow in ('chat', 'plan_generation', 'checkin', 'summary', 'eval'));
