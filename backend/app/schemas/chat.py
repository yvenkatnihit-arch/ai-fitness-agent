"""Chat requests and responses (Step 7.11b, D-097)."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.workflows.chat_turn import MAX_MESSAGE_CHARS


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(max_length=MAX_MESSAGE_CHARS)
    conversation_id: UUID | None = None   # none = start a new conversation

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Type a message first.")
        return value


class DecideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choice: Literal["approve", "reject"]


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Literal["up", "down"] | None      # none = take the thumb back


class ProposalCard(BaseModel):
    kind: str
    proposal_id: str
    summary: str


class ChatOut(BaseModel):
    conversation_id: UUID
    reply: str
    blocked: str | None = None             # a guard stopped or replaced this turn (the category, never the text)
    waiting_for: ProposalCard | None = None  # a proposal the user must approve or reject
    decisions: list[dict[str, str]] = []
    meta: dict[str, Any] = {}              # what ran, for the "How this was made" panel
    message_id: int | None = None          # the saved reply, so a thumb can be attached to it


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    blocked: str | None = None
    feedback: Literal["up", "down"] | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
    updated_at: str


class ConversationListOut(BaseModel):
    conversations: list[ConversationOut]


class ConversationDetailOut(BaseModel):
    id: UUID
    messages: list[MessageOut]
