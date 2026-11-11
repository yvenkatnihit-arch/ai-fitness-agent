"""One chat turn from the API's point of view (Step 7.11b, D-097): save the user's message, run the chat graph, save the reply.

The graph (D-075) does the thinking: input guard, router, specialists, composer, output guard, pause for approval. This module only
adds what an endpoint needs around it: conversation ownership, writing BOTH sides of the chat (chat_history), and turning the
graph's result into plain JSON-friendly data. `graph_kwargs` is for tests (fake router and models); production passes nothing.

History (7.11c): the last 6 messages and the rolling summary go to the ROUTER only, which rewrites each task so it stands on its own
('and in that?' becomes a full question); the specialists never see the history. Messages a guard stopped are never sent as context.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.agents.approvals import APPROVE, REJECT
from app.agents.chat_graph import answer_message, resume_chat, waiting_card
from app.agents.checkpointer import checkpointer
from app.agents.summarizer import summarize
from app.core import chat_limits
from app.db import admin_transaction
from app.db import chat_history as history

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000
SUMMARY_BATCH = 4      # fold older messages into the summary only when this many are waiting (one model call per 2 turns, not per turn)
CHOICES = (APPROVE, REJECT)


def thread_for(conversation_id: UUID, turn_id: int) -> str:
    """The LangGraph thread of ONE turn. A thread keeps its state between runs, so a thread per conversation would carry the last
    turn's reply, blocked mark and results into the next message (found by a live test). One thread per turn (the id of its user
    message) starts every message clean, and a paused turn is simply the latest one."""
    return f"{conversation_id}:{turn_id}"


class ConversationNotFound(Exception):
    pass


class ChatLimitReached(Exception):
    def __init__(self, wait_seconds: int) -> None:
        super().__init__(chat_limits.friendly_message(wait_seconds))
        self.wait_seconds = wait_seconds


class NothingWaiting(Exception):
    """The user answered a question that is not being asked (already answered, or never asked)."""


def _meta(result: dict[str, Any]) -> dict[str, Any]:
    """What ran, for the 'How this was made' panel: names and counts only, never the model's text."""
    return {
        "specialists": [{"name": r["specialist"], "status": r["status"], "steps": r["steps"], "tokens": r["tokens"],
                         "tools": [t.name for t in r["tools"]]} for r in result["results"]],
        "composed": result["composed"],
    }


def _out(conversation_id: UUID, result: dict[str, Any], reply: str) -> dict[str, Any]:
    return {"conversation_id": str(conversation_id), "reply": reply, "blocked": result.get("blocked"),
            "waiting_for": result["waiting_for"], "decisions": result["decisions"], "meta": _meta(result)}


def send_message(user_id: UUID, message: str, conversation_id: UUID | None = None, **graph_kwargs: Any) -> dict[str, Any]:
    with admin_transaction("chat: check the limit") as conn:
        times = history.user_message_times(conn, user_id, chat_limits.LOOKBACK_SECONDS)
    wait = chat_limits.seconds_to_wait(times, datetime.now(timezone.utc))
    if wait is not None:
        raise ChatLimitReached(wait)                              # before anything is saved or any model runs
    with admin_transaction("chat: save the user's message") as conn:
        if conversation_id is None:
            conversation_id = history.create_conversation(conn, user_id, message)
        elif not history.owns(conn, user_id, conversation_id):
            raise ConversationNotFound
        recent = history.recent_messages(conn, user_id, conversation_id)        # read BEFORE saving this message: it is not "earlier"
        summary, _ = history.read_summary(conn, user_id, conversation_id)
        user_message_id = history.add_message(conn, user_id, conversation_id, "user", message)
    with checkpointer() as saver:
        result = answer_message(message, user_id, conversation_id=thread_for(conversation_id, user_message_id), checkpointer=saver, history=recent,
                                summary=summary, **graph_kwargs)
    out = _out(conversation_id, result, result["reply"])
    with admin_transaction("chat: save the reply") as conn:
        if result.get("blocked"):
            history.mark_blocked(conn, user_id, user_message_id, result["blocked"])   # both sides of a blocked turn stay out of context
        history.add_message(conn, user_id, conversation_id, "assistant", result["reply"], blocked=result.get("blocked"),
                            meta={**out["meta"], "waiting_for": result["waiting_for"]})
    return out


def answer_proposal(user_id: UUID, conversation_id: UUID, choice: str, **graph_kwargs: Any) -> dict[str, Any]:
    """The user's yes or no on the proposal card the chat is waiting on. The proposal id comes from the saved graph state, never
    from the request, and the change is applied by the same re-checking workflow as the plan screen (D-077)."""
    if choice not in CHOICES:
        raise ValueError(f"choice must be one of {CHOICES}")
    with admin_transaction("chat: check the conversation") as conn:
        if not history.owns(conn, user_id, conversation_id):
            raise ConversationNotFound
        turns = history.user_message_ids(conn, user_id, conversation_id)
    if not turns:
        raise NothingWaiting
    thread = thread_for(conversation_id, turns[-1])                      # only the latest turn can be waiting for an answer
    with checkpointer() as saver:
        if waiting_card(user_id, thread, checkpointer=saver, **graph_kwargs) is None:
            raise NothingWaiting
        result = resume_chat(user_id, thread, choice, checkpointer=saver, **graph_kwargs)
    reply = " ".join(d["message"] for d in result["decisions"]) or result["reply"]
    out = _out(conversation_id, result, reply)
    with admin_transaction("chat: save the outcome") as conn:
        history.add_message(conn, user_id, conversation_id, "assistant", reply,
                            meta={"decisions": result["decisions"], "waiting_for": result["waiting_for"]})
    return out


def delete_conversation(user_id: UUID, conversation_id: UUID) -> None:
    """Delete a chat AND its saved graph states (they hold the message text too). Raises ConversationNotFound if it is not theirs."""
    with admin_transaction("chat: list the turns to delete") as conn:
        if not history.owns(conn, user_id, conversation_id):
            raise ConversationNotFound
        turns = history.user_message_ids(conn, user_id, conversation_id)
    with checkpointer() as saver:
        for turn in turns:
            saver.delete_thread(f"{user_id}:{thread_for(conversation_id, turn)}")
    with admin_transaction("chat: delete the conversation") as conn:
        conn.execute("delete from public.chat_conversations where id = %s and user_id = %s", (conversation_id, user_id))


def update_summary(user_id: UUID, conversation_id: UUID, **summarize_kwargs: Any) -> bool:
    """Fold the messages that left the 6-message window into the rolling summary (D-099). Best effort: it runs AFTER the reply is
    sent, so it must never raise. Returns True when a new summary was saved. A failed or rejected summary keeps the old one."""
    try:
        with admin_transaction("chat: read what to summarize") as conn:
            waiting = history.unsummarized_before_window(conn, user_id, conversation_id)
            if len(waiting) < SUMMARY_BATCH:
                return False
            old, _ = history.read_summary(conn, user_id, conversation_id)
        new = summarize(old, [(role, text) for _, role, text in waiting], user_id=user_id, **summarize_kwargs)
        if new is None:
            logger.warning("chat summary rejected by its checks; keeping the old one")
            return False
        with admin_transaction("chat: save the summary") as conn:
            history.save_summary(conn, user_id, conversation_id, new, waiting[-1][0])
        return True
    except Exception:   # noqa: BLE001 - background work after the response: log and carry on
        logger.exception("chat summary failed; keeping the old one")
        return False
