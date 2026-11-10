-- Step 7.11a (D-096): our own chat history, so the screen can list past chats and the model gets only the last 6 messages plus a
-- rolling summary (never the full history, CLAUDE.md cost rule). Server-written (D-027): the backend writes both the user's
-- message and the assistant's reply, so a user can never forge an assistant message. Users may read and delete their own chats.
-- LangGraph's checkpointer (langgraph schema) is still used, only to pause a run while a proposal waits for approval.

create table public.chat_conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  title      text check (char_length(title) <= 80),                 -- first words of the first message, for the list
  summary    text not null default '' check (char_length(summary) <= 2000),   -- the rolling summary of older messages
  summarized_through bigint not null default 0,                      -- the highest chat_messages.id already folded into the summary
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chat_conversations_id_user unique (id, user_id)
);

create index chat_conversations_user on public.chat_conversations (user_id, updated_at desc);

create trigger chat_conversations_set_updated_at
  before update on public.chat_conversations
  for each row execute function public.set_updated_at();

create table public.chat_messages (
  id              bigint generated always as identity primary key,
  conversation_id uuid not null,
  user_id         uuid not null,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null check (char_length(content) between 1 and 4000),
  blocked         text check (char_length(blocked) <= 40),           -- guard category when a guard stopped or replaced this turn
  meta            jsonb,                                              -- what ran (specialists, tools), for the "How this was made" panel
  created_at      timestamptz not null default now(),
  foreign key (conversation_id, user_id) references public.chat_conversations (id, user_id) on delete cascade
);

create index chat_messages_conversation on public.chat_messages (conversation_id, id desc);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

create policy chat_conversations_select_own on public.chat_conversations
  for select to authenticated using ((select auth.uid()) = user_id);
create policy chat_conversations_delete_own on public.chat_conversations
  for delete to authenticated using ((select auth.uid()) = user_id);
create policy chat_messages_select_own on public.chat_messages
  for select to authenticated using ((select auth.uid()) = user_id);
create policy chat_messages_delete_own on public.chat_messages
  for delete to authenticated using ((select auth.uid()) = user_id);

revoke insert, update, truncate on public.chat_conversations, public.chat_messages from authenticated;
revoke all on public.chat_conversations, public.chat_messages from anon;
