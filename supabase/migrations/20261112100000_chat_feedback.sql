-- Step 8.15 (D-120): a thumbs up or down on a chat answer, so wrong answers can be found without reading every chat.
-- Server-written like the rest of chat history (D-027): users can read their own messages (RLS, already on), but cannot update them.
alter table public.chat_messages
  add column feedback text check (feedback in ('up', 'down'));
