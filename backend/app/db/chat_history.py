"""Chat history (Step 7.11a, D-096). Writes use the admin connection (the backend writes BOTH sides of a chat, so a user can never
forge an assistant message), and every write is scoped by user_id here AND by a composite foreign key in the database. Reads for the
screen use the user's own connection (RLS). The model is only ever sent `recent_messages` (the last 6) plus the rolling summary."""

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

HISTORY_LIMIT = 6          # messages sent to the model, besides the rolling summary (CLAUDE.md)
MAX_CONTENT = 4000         # the table's check; a longer text is cut, never refused (replies are already limited by max_tokens)
TITLE_CHARS = 60


def _clip(text: str) -> str:
    return text[:MAX_CONTENT]


def create_conversation(conn: Connection, user_id: UUID, first_message: str) -> UUID:
    title = " ".join(first_message.split())[:TITLE_CHARS] or None
    return conn.execute("insert into public.chat_conversations (user_id, title) values (%s, %s) returning id",
                        (user_id, title)).fetchone()[0]


def owns(conn: Connection, user_id: UUID, conversation_id: UUID) -> bool:
    return conn.execute("select 1 from public.chat_conversations where id = %s and user_id = %s",
                        (conversation_id, user_id)).fetchone() is not None


def add_message(conn: Connection, user_id: UUID, conversation_id: UUID, role: str, content: str, *,
                blocked: str | None = None, meta: dict | None = None) -> int:
    """Save one message. Raises LookupError when the conversation is not this user's (nothing is written)."""
    if not owns(conn, user_id, conversation_id):
        raise LookupError("conversation not found")
    row = conn.execute(
        """insert into public.chat_messages (conversation_id, user_id, role, content, blocked, meta)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (conversation_id, user_id, role, _clip(content), blocked, Jsonb(meta) if meta is not None else None)).fetchone()
    conn.execute("update public.chat_conversations set updated_at = now() where id = %s", (conversation_id,))
    return row[0]


def mark_blocked(conn: Connection, user_id: UUID, message_id: int, category: str) -> None:
    """Remember that a guard stopped this message, so it is never shown to a model as context later."""
    conn.execute("update public.chat_messages set blocked = %s where id = %s and user_id = %s", (category[:40], message_id, user_id))


def user_message_times(conn: Connection, user_id: UUID, within_seconds: int) -> list:
    """When this user sent messages in the last `within_seconds`, across ALL their chats (the rate limit counts the person, not the chat)."""
    return [r[0] for r in conn.execute(
        """select created_at from public.chat_messages where user_id = %s and role = 'user'
           and created_at > now() - make_interval(secs => %s) order by created_at desc limit 1000""", (user_id, within_seconds)).fetchall()]


def user_message_ids(conn: Connection, user_id: UUID, conversation_id: UUID) -> list[int]:
    """Every user message id in the conversation, oldest first. Each one is the id of a TURN (see chat_turn.thread_for)."""
    return [r[0] for r in conn.execute(
        "select id from public.chat_messages where conversation_id = %s and user_id = %s and role = 'user' order by id",
        (conversation_id, user_id)).fetchall()]


def recent_messages(conn: Connection, user_id: UUID, conversation_id: UUID, limit: int = HISTORY_LIMIT) -> list[tuple[str, str]]:
    """The last `limit` messages as (role, content), oldest first: what the model is shown. Messages a guard stopped or replaced
    are left out, so a blocked (possibly hostile) text never comes back as context."""
    rows = conn.execute(
        """select role, content from public.chat_messages where conversation_id = %s and user_id = %s and blocked is null
           order by id desc limit %s""", (conversation_id, user_id, limit)).fetchall()
    return [(r, c) for r, c in reversed(rows)]


def read_summary(conn: Connection, user_id: UUID, conversation_id: UUID) -> tuple[str, int]:
    """(rolling summary, highest message id already folded into it)."""
    row = conn.execute("select summary, summarized_through from public.chat_conversations where id = %s and user_id = %s",
                       (conversation_id, user_id)).fetchone()
    if row is None:
        raise LookupError("conversation not found")
    return row[0], row[1]


def save_summary(conn: Connection, user_id: UUID, conversation_id: UUID, summary: str, through_message_id: int) -> None:
    done = conn.execute(
        "update public.chat_conversations set summary = %s, summarized_through = %s where id = %s and user_id = %s",
        (summary[:2000], through_message_id, conversation_id, user_id)).rowcount
    if not done:
        raise LookupError("conversation not found")


def unsummarized_before_window(conn: Connection, user_id: UUID, conversation_id: UUID, limit: int = HISTORY_LIMIT
                               ) -> list[tuple[int, str, str]]:
    """Messages that fell out of the last-`limit` window and are not in the summary yet: (id, role, content), oldest first.
    These are what the next summary must absorb. Blocked messages are skipped, exactly as `recent_messages` skips them."""
    _, through = read_summary(conn, user_id, conversation_id)
    rows = conn.execute(
        """select id, role, content from public.chat_messages
           where conversation_id = %s and user_id = %s and id > %s and blocked is null
             and id not in (select id from public.chat_messages where conversation_id = %s and user_id = %s and blocked is null
                            order by id desc limit %s)
           order by id""", (conversation_id, user_id, through, conversation_id, user_id, limit)).fetchall()
    return list(rows)


# ---- reads for the screen: run these with user_transaction (RLS) ----

def list_conversations(conn: Connection, limit: int = 30) -> list[tuple]:
    return conn.execute("select id, title, updated_at from public.chat_conversations order by updated_at desc limit %s",
                        (limit,)).fetchall()


def messages_of(conn: Connection, conversation_id: UUID, limit: int = 200) -> list[tuple]:
    rows = conn.execute(
        """select id, role, content, blocked, meta, created_at, feedback from public.chat_messages where conversation_id = %s
           order by id desc limit %s""", (conversation_id, limit)).fetchall()
    return list(reversed(rows))


def set_feedback(conn: Connection, user_id: UUID, message_id: int, value: str | None) -> bool:
    """Thumbs up/down on one of THIS user's assistant messages (None clears it). False when there is no such message."""
    return conn.execute("update public.chat_messages set feedback = %s where id = %s and user_id = %s and role = 'assistant'",
                        (value, message_id, user_id)).rowcount > 0


def delete_conversation(conn: Connection, conversation_id: UUID) -> bool:
    return conn.execute("delete from public.chat_conversations where id = %s", (conversation_id,)).rowcount > 0
