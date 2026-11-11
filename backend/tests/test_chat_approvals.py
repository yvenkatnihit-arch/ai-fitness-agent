"""Step 7.5: pausing the chat for the user's decision on a proposal (LangGraph interrupt), with fakes. No LLM, no database."""

from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, ConfigDict

from app.agents import approvals
from app.agents.claims import PREPARED
from app.agents.chat_graph import answer_message, resume_chat
from app.agents.menu import MenuEntry
from app.agents.router import Assignment
from app.agents.runner import ToolCall, Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import Tool, ToolRegistry

UID = uuid4()
P1, P2 = str(uuid4()), str(uuid4())


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def propose_tool(name: str, proposal_id: str, scope="propose") -> Tool:
    return Tool(name, "Create a pending proposal", NoArgs, lambda ctx, args: {"proposal_id": proposal_id, "summary": f"Plan {proposal_id[:4]}"},
                scope=scope)  # type: ignore[arg-type]


def entry(name: str, *tools: Tool) -> MenuEntry:
    def registry() -> ToolRegistry:
        r = ToolRegistry()
        for t in tools:
            r.register(t)
        return r
    return MenuEntry(SpecialistSpec(name=name, system_prompt=f"You are {name}.", tools=frozenset(t.name for t in tools)), registry, "x")


def proposing_model(tool_name: str):
    turns = iter([Turn(call=ToolCall(tool_name, {}), tokens=1), Turn(final="I made a proposal.", tokens=1)])
    return lambda messages: next(turns)


class Recorder:
    """A fake `decide` that records what it was asked to apply."""
    def __init__(self):
        self.calls: list[tuple[UUID, UUID, str]] = []

    def __call__(self, user_id, proposal_id, choice):
        self.calls.append((user_id, proposal_id, choice))
        return f"{choice} done"


def setup(*tools: Tool, picks=1):
    menu = {"planner": entry("planner", *tools)}
    return dict(menu=menu, router=lambda m: [Assignment("planner", "make a plan")][:picks],
                make_model=lambda spec, reg: proposing_model(tools[0].name), composer=lambda m, a: None,
                checkpointer=InMemorySaver(), decide=Recorder())


# ---------- recording proposals in the harness ----------

def test_a_propose_tool_reports_its_proposal_on_the_run_record():
    kw = setup(propose_tool("propose_plan", P1))
    out = answer_message("plan please", UID, conversation_id="c1", **kw)
    rec = out["results"][0]["tools"][0]
    assert (rec.name, rec.outcome, rec.proposal_id, rec.proposal_summary) == ("propose_plan", "ok", P1, f"Plan {P1[:4]}")


def test_a_read_tool_that_returns_a_proposal_id_is_not_treated_as_a_proposal():
    kw = setup(propose_tool("lookup", P1, scope="read"))
    out = answer_message("x", UID, conversation_id="c1", **kw)
    assert out["results"][0]["tools"][0].proposal_id is None and out["waiting_for"] is None and kw["decide"].calls == []


def test_a_proposal_id_that_is_not_a_uuid_is_ignored():
    kw = setup(propose_tool("propose_plan", "not-a-uuid"))
    out = answer_message("x", UID, conversation_id="c1", **kw)
    assert out["waiting_for"] is None and kw["decide"].calls == []


# ---------- pause and resume ----------

def test_the_run_pauses_with_a_card_and_applies_nothing_until_the_user_answers():
    kw = setup(propose_tool("propose_plan", P1))
    out = answer_message("plan please", UID, conversation_id="c1", **kw)
    assert out["reply"] == PREPARED                                   # the words about a proposal come from code, not the model (D-109)
    assert out["waiting_for"] == {"kind": "approve_proposal", "proposal_id": P1, "summary": f"Plan {P1[:4]}"}
    assert kw["decide"].calls == [] and out["decisions"] == []


def test_approve_applies_that_one_proposal_for_that_user():
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    out = resume_chat(UID, "c1", "approve", **kw)
    assert kw["decide"].calls == [(UID, UUID(P1), "approve")]
    assert out["waiting_for"] is None and out["decisions"] == [{"proposal_id": P1, "choice": "approve", "message": "approve done"}]


def test_reject_is_passed_on_as_reject():
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    resume_chat(UID, "c1", "reject", **kw)
    assert kw["decide"].calls == [(UID, UUID(P1), "reject")]


@pytest.mark.parametrize("answer", ["yes", "APPROVE", "", None, 1, {"choice": "approve"}, "approve please"])
def test_any_other_answer_leaves_the_proposal_pending(answer):
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    out = resume_chat(UID, "c1", answer, **kw)
    assert kw["decide"].calls == [(UID, UUID(P1), "leave")] and out["decisions"][0]["choice"] == "leave"


def test_the_answer_cannot_choose_which_proposal_is_decided():
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    resume_chat(UID, "c1", {"choice": "approve", "proposal_id": P2}, **kw)
    assert all(call[1] == UUID(P1) for call in kw["decide"].calls)


def test_another_user_cannot_resume_my_conversation():
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    intruder = uuid4()
    with pytest.raises(Exception):   # nothing is paused on the intruder's thread, so there is nothing to resume
        resume_chat(intruder, "c1", "approve", **kw)
    assert kw["decide"].calls == []


def test_a_decision_is_applied_once_even_if_the_answer_is_sent_twice():
    kw = setup(propose_tool("propose_plan", P1))
    answer_message("plan please", UID, conversation_id="c1", **kw)
    resume_chat(UID, "c1", "approve", **kw)
    try:
        resume_chat(UID, "c1", "approve", **kw)   # nothing is waiting any more
    except Exception:
        pass
    assert kw["decide"].calls == [(UID, UUID(P1), "approve")]


# ---------- several proposals ----------

def test_two_proposals_are_asked_one_at_a_time_and_each_is_applied_once():
    t1, t2 = propose_tool("propose_a", P1), propose_tool("propose_b", P2)
    turns = iter([Turn(call=ToolCall("propose_a", {})), Turn(call=ToolCall("propose_b", {})), Turn(final="Two proposals.")])
    kw = setup(t1, t2)
    kw["make_model"] = lambda spec, reg: (lambda messages: next(turns))
    first = answer_message("plans", UID, conversation_id="c2", **kw)
    assert first["waiting_for"]["proposal_id"] == P1
    second = resume_chat(UID, "c2", "approve", **kw)
    assert second["waiting_for"]["proposal_id"] == P2 and kw["decide"].calls == [(UID, UUID(P1), "approve")]
    third = resume_chat(UID, "c2", "reject", **kw)
    assert third["waiting_for"] is None
    assert kw["decide"].calls == [(UID, UUID(P1), "approve"), (UID, UUID(P2), "reject")]
    assert [d["choice"] for d in third["decisions"]] == ["approve", "reject"]


# ---------- no checkpointer, no pause ----------

def test_without_a_checkpointer_nothing_pauses_and_the_proposal_stays_pending():
    kw = setup(propose_tool("propose_plan", P1))
    kw["checkpointer"] = None
    out = answer_message("plan please", UID, **kw)
    assert out["waiting_for"] is None and kw["decide"].calls == [] and out["reply"] == PREPARED


# ---------- the real decision helper ----------

@pytest.mark.parametrize("raised, text", [
    ("ProposalNotFound", "could not find"), ("ProposalNotPending", "already decided"),
])
def test_the_helper_turns_workflow_errors_into_friendly_messages(monkeypatch, raised, text):
    def boom(user_id, proposal_id):
        raise getattr(approvals.workflow, raised)
    monkeypatch.setattr(approvals.workflow, "approve", boom)
    assert text in approvals.decide_with_workflow(UID, uuid4(), "approve")


def test_the_helper_shows_a_cannot_be_applied_message_as_it_is(monkeypatch):
    def boom(user_id, proposal_id):
        raise approvals.workflow.ProposalCannotBeApplied("This plan did not pass our safety checks.")
    monkeypatch.setattr(approvals.workflow, "approve", boom)
    assert approvals.decide_with_workflow(UID, uuid4(), "approve") == "This plan did not pass our safety checks."


def test_the_helper_calls_the_real_workflow_functions(monkeypatch):
    calls = []
    monkeypatch.setattr(approvals.workflow, "approve", lambda u, p: calls.append(("approve", u, p)))
    monkeypatch.setattr(approvals.workflow, "reject", lambda u, p: calls.append(("reject", u, p)))
    pid = uuid4()
    assert "saved" in approvals.decide_with_workflow(UID, pid, "approve")
    assert "did not change" in approvals.decide_with_workflow(UID, pid, "reject")
    assert "waiting" in approvals.decide_with_workflow(UID, pid, "leave")
    assert calls == [("approve", UID, pid), ("reject", UID, pid)]
