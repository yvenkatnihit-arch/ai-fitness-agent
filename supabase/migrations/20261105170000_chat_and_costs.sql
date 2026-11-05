-- Migration 6: conversations, messages, summaries, agent_runs, usage_counters, daily cost view.
--
-- Chat tables are SERVER-WRITTEN (D-027): the chat graph writes them; users read their own.
-- agent_runs is BACKEND-ONLY: no user policy at all (cost/token data is for the admin).

-- ---------------------------------------------------------------------------
-- conversations
-- ---------------------------------------------------------------------------
create table public.conversations (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles (id) on delete cascade,
  title        text check (char_length(title) <= 120),
  -- Set by the input guard after crisis language: coaching pauses until this time (brief section 7).
  paused_until timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint conversations_id_user unique (id, user_id)
);

create index conversations_user_recent on public.conversations (user_id, updated_at desc);

create trigger conversations_set_updated_at
  before update on public.conversations
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- messages: full history is kept (chat screen, data export). The LLM only ever gets
-- the last 6 plus the rolling summary (D-018). Ordered by id.
-- ---------------------------------------------------------------------------
create table public.messages (
  id              bigint generated always as identity primary key,
  conversation_id uuid not null,
  user_id         uuid not null,
  role            text not null check (role in ('user', 'assistant', 'safety')),  -- safety = fixed guard reply
  content         text not null check (char_length(content) between 1 and 8000),
  intents         text[] not null default '{}',  -- router output, for evals and debugging
  metadata        jsonb not null default '{}',
  created_at      timestamptz not null default now(),
  foreign key (conversation_id, user_id) references public.conversations (id, user_id) on delete cascade
);

-- "Last 6 messages of this conversation" and "messages since the last summary".
create index messages_conversation_latest on public.messages (conversation_id, id desc);

-- ---------------------------------------------------------------------------
-- conversation_summaries: one rolling summary per conversation (D-018).
-- ---------------------------------------------------------------------------
create table public.conversation_summaries (
  conversation_id         uuid primary key,
  user_id                 uuid not null,
  summary                 text not null check (char_length(summary) <= 4000),
  covers_up_to_message_id bigint not null,  -- the next summary starts after this message
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  foreign key (conversation_id, user_id) references public.conversations (id, user_id) on delete cascade
);

create trigger conversation_summaries_set_updated_at
  before update on public.conversation_summaries
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- agent_runs: one row per LLM call. Tokens, cost, latency (CLAUDE.md cost rules).
-- If an account is deleted, its rows keep the numbers but lose the link to the person.
-- ---------------------------------------------------------------------------
create table public.agent_runs (
  id               bigint generated always as identity primary key,
  user_id          uuid references public.profiles (id) on delete set null,
  conversation_id  uuid references public.conversations (id) on delete set null,
  flow             text not null check (flow in ('chat', 'plan_generation', 'checkin', 'summary')),
  node             text not null check (char_length(node) between 1 and 60),  -- router, nutrition, composer...
  model            text not null check (char_length(model) between 1 and 80),
  input_tokens     integer not null default 0 check (input_tokens >= 0),
  output_tokens    integer not null default 0 check (output_tokens >= 0),
  cached_tokens    integer not null default 0 check (cached_tokens >= 0),
  cost_usd         numeric(10, 6) not null default 0 check (cost_usd >= 0),  -- estimate, computed in code
  latency_ms       integer not null check (latency_ms >= 0),
  status           text not null check (status in ('ok', 'error', 'rate_limited', 'blocked')),
  error_code       text check (char_length(error_code) <= 80),
  langsmith_run_id text check (char_length(langsmith_run_id) <= 80),
  created_at       timestamptz not null default now()
);

create index agent_runs_created on public.agent_runs (created_at desc);
create index agent_runs_user_created on public.agent_runs (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- usage_counters: messages per user per day (default limit 50, brief section 8).
-- "day" is the India calendar date, set by the backend.
-- ---------------------------------------------------------------------------
create table public.usage_counters (
  user_id       uuid not null references public.profiles (id) on delete cascade,
  day           date not null,
  message_count integer not null default 0 check (message_count >= 0),
  updated_at    timestamptz not null default now(),
  primary key (user_id, day)
);

create trigger usage_counters_set_updated_at
  before update on public.usage_counters
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.conversation_summaries enable row level security;
alter table public.agent_runs enable row level security;
alter table public.usage_counters enable row level security;

create policy conversations_select_own on public.conversations
  for select to authenticated using ((select auth.uid()) = user_id);
create policy messages_select_own on public.messages
  for select to authenticated using ((select auth.uid()) = user_id);
create policy conversation_summaries_select_own on public.conversation_summaries
  for select to authenticated using ((select auth.uid()) = user_id);
create policy usage_counters_select_own on public.usage_counters
  for select to authenticated using ((select auth.uid()) = user_id);
-- agent_runs: RLS on with no policy = no rows for anyone except the admin connection.

revoke insert, update, delete, truncate on
  public.conversations, public.messages, public.conversation_summaries, public.usage_counters
  from authenticated;
revoke all on public.agent_runs from authenticated;
revoke all on
  public.conversations, public.messages, public.conversation_summaries,
  public.agent_runs, public.usage_counters
  from anon;

-- ---------------------------------------------------------------------------
-- daily_llm_cost: the admin's cost view (D-013). Days are India calendar days.
-- security_invoker = true: the view runs with the CALLER's permissions, so it can't be
-- used to get around agent_runs being admin-only.
-- ---------------------------------------------------------------------------
create view public.daily_llm_cost
with (security_invoker = true)
as
select
  (created_at at time zone 'Asia/Kolkata')::date                   as day,
  model,
  count(*)                                                          as runs,
  count(*) filter (where status <> 'ok')                            as failed_runs,
  sum(input_tokens)                                                 as input_tokens,
  sum(output_tokens)                                                as output_tokens,
  sum(cached_tokens)                                                as cached_tokens,
  sum(cost_usd)                                                     as cost_usd,
  round(avg(latency_ms))::integer                                   as avg_latency_ms,
  percentile_cont(0.95) within group (order by latency_ms)::integer as p95_latency_ms
from public.agent_runs
group by 1, 2;

revoke all on public.daily_llm_cost from anon, authenticated;
