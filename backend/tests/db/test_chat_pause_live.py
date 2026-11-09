"""Step 7.5: a chat paused for approval survives a server restart (real Supabase checkpointer, fake model and fake decision)."""

import uuid

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents.checkpointer import checkpointer
from app.agents.chat_graph import answer_message, resume_chat
from app.agents.menu import MenuEntry
from app.agents.router import Assignment
from app.agents.runner import ToolCall, Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import Tool, ToolRegistry

pytestmark = pytest.mark.db


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def test_a_paused_conversation_resumes_on_a_new_connection_and_applies_once():
    user, pid, conversation = uuid.uuid4(), str(uuid.uuid4()), f"test-{uuid.uuid4()}"
    tool = Tool("propose_plan", "Create a pending proposal", NoArgs, lambda c, a: {"proposal_id": pid, "summary": "A plan"}, scope="propose")

    def registry() -> ToolRegistry:
        r = ToolRegistry()
        r.register(tool)
        return r

    menu = {"planner": MenuEntry(SpecialistSpec(name="planner", system_prompt="p", tools=frozenset({"propose_plan"})), registry, "x")}
    decided: list = []

    def kwargs(saver):
        turns = iter([Turn(call=ToolCall("propose_plan", {})), Turn(final="Proposal ready.")])
        return dict(menu=menu, router=lambda m: [Assignment("planner", "plan")], make_model=lambda s, r: (lambda m: next(turns)),
                    composer=lambda m, a: None, checkpointer=saver,
                    decide=lambda u, p, choice: decided.append((u, str(p), choice)) or "ok")

    try:
        with checkpointer() as saver:                          # first "server process"
            first = answer_message("plan please", user, conversation_id=conversation, **kwargs(saver))
        assert first["waiting_for"]["proposal_id"] == pid and decided == []

        with checkpointer() as saver:                          # a brand-new connection and graph, like after a restart
            second = resume_chat(user, conversation, "approve", **kwargs(saver))
        assert second["waiting_for"] is None and decided == [(user, pid, "approve")]
        assert second["decisions"][0]["choice"] == "approve"
    finally:
        with checkpointer() as saver:
            saver.delete_thread(f"{user}:{conversation}")
