"""The chat endpoints (Step 7.11b, D-097). All the work is in workflows/chat_turn.py and the chat graph; this only maps errors."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from app.core.auth import CurrentUser, get_current_user
from app.db import chat_history as history
from app.db import admin_transaction, user_transaction
from app.llm.client import LLMBusy, LLMFailed
from app.schemas.chat import (ChatIn, ChatOut, ConversationDetailOut, ConversationListOut, ConversationOut, DecideIn, FeedbackIn, MessageOut)
from app.workflows import chat_turn

router = APIRouter(prefix="/chat", tags=["chat"])

NOT_FOUND = "We couldn't find that conversation."


def _run(call):
    try:
        return call()
    except LLMBusy as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from None
    except LLMFailed as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None
    except chat_turn.ChatLimitReached as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error), headers={"Retry-After": str(error.wait_seconds)}) from None
    except chat_turn.ConversationNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except chat_turn.NothingWaiting:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing is waiting for your answer in this chat.") from None


@router.post("", response_model=ChatOut)
def send(body: ChatIn, tasks: BackgroundTasks, user: CurrentUser = Depends(get_current_user)) -> ChatOut:
    """One user message in, one reply out. A guard can stop the message before any model runs; a plan change is only ever a
    proposal the user must approve (see `waiting_for` and the decide endpoint)."""
    out = _run(lambda: chat_turn.send_message(user.id, body.message, body.conversation_id))
    tasks.add_task(chat_turn.update_summary, user.id, UUID(out["conversation_id"]))   # after the reply is sent: the user never waits for it
    return ChatOut(**out)


@router.post("/{conversation_id}/decide", response_model=ChatOut)
def decide(conversation_id: UUID, body: DecideIn, user: CurrentUser = Depends(get_current_user)) -> ChatOut:
    """The user's yes or no on the proposal the chat is waiting on."""
    return ChatOut(**_run(lambda: chat_turn.answer_proposal(user.id, conversation_id, body.choice)))


@router.get("", response_model=ConversationListOut)
def conversations(user: CurrentUser = Depends(get_current_user)) -> ConversationListOut:
    with user_transaction(user.id) as conn:
        rows = history.list_conversations(conn)
    return ConversationListOut(conversations=[ConversationOut(id=i, title=t, updated_at=u.isoformat()) for i, t, u in rows])


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def conversation(conversation_id: UUID, user: CurrentUser = Depends(get_current_user)) -> ConversationDetailOut:
    with user_transaction(user.id) as conn:
        rows = history.messages_of(conn, conversation_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)         # someone else's chat looks exactly like no chat
    return ConversationDetailOut(id=conversation_id, messages=[MessageOut(id=i, role=r, content=c, blocked=b, feedback=f) for i, r, c, b, _, _, f in rows])


@router.put("/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(message_id: int, body: FeedbackIn, user: CurrentUser = Depends(get_current_user)) -> Response:
    """A thumbs up or down on one of your coach's answers (value null takes it back)."""
    with admin_transaction("chat: save a thumb") as conn:     # users cannot update chat rows (D-027); the query checks the owner
        found = history.set_feedback(conn, user.id, message_id, body.value)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that answer.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(conversation_id: UUID, user: CurrentUser = Depends(get_current_user)) -> Response:
    _run(lambda: chat_turn.delete_conversation(user.id, conversation_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
