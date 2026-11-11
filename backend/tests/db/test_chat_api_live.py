"""Step 7.11b (D-097): the chat endpoints against the real database and the real checkpointer, with a fake router and fake models
(no Gemini calls, no cost). The guards, the saved history, ownership, the pause for approval and the answer are all real."""

import functools
import uuid

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents.menu import MenuEntry
from app.agents.router import Assignment
from app.agents.runner import ToolCall, Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import Tool, ToolRegistry
from app.db import admin_transaction
from app.llm.client import LLMBusy
from app.workflows import chat_turn
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


PROPOSAL = str(uuid.uuid4())
DECIDED: list = []


def graph_kwargs(propose: bool):
    """A fresh fake graph setup: the router picks one specialist; it either answers at once or proposes a plan first."""
    tool = Tool("propose_plan", "Create a pending proposal", NoArgs, lambda c, a: {"proposal_id": PROPOSAL, "summary": "A new plan"},
                scope="propose")

    def registry() -> ToolRegistry:
        r = ToolRegistry()
        r.register(tool)
        return r

    menu = {"planner": MenuEntry(SpecialistSpec(name="planner", system_prompt="p", tools=frozenset({"propose_plan"})), registry, "x")}
    turns = iter([Turn(call=ToolCall("propose_plan", {})), Turn(final="Proposal ready.")] if propose else [Turn(final="Paneer has 18 g of protein per 100 g.")])
    return dict(menu=menu, router=lambda m: [Assignment("planner", "answer")], make_model=lambda s, r: (lambda m: next(turns)),
                composer=lambda m, a: None, decide=lambda u, p, choice: DECIDED.append((str(u), str(p), choice)) or f"Decided: {choice}.")


@pytest.fixture
def fake_graph(monkeypatch):
    """The endpoint calls the real workflow; only the model-side pieces of the graph are swapped. `mode["propose"]` picks the script."""
    mode = {"propose": False, "own_router": False}      # own_router: drop the fake router so a test can spy on route_message itself
    DECIDED.clear()

    def kwargs():
        base = graph_kwargs(mode["propose"])
        if mode["own_router"]:
            base.pop("router")
        return base
    for name in ("answer_message", "resume_chat", "waiting_card"):
        real = getattr(chat_turn, name)
        monkeypatch.setattr(chat_turn, name, lambda *a, _real=real, **k: _real(*a, **{**kwargs(), **k}))
    return mode


def rows(sql, *args):
    with admin_transaction("test: read chat") as conn:
        return conn.execute(sql, args).fetchall()


def test_a_message_gets_a_reply_and_both_sides_are_saved(client, users, fake_graph):
    onboard(client)
    response = client.post("/chat", json={"message": "How much protein is in paneer?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reply"] == "Paneer has 18 g of protein per 100 g." and body["waiting_for"] is None and body["blocked"] is None
    assert body["meta"]["specialists"][0]["name"] == "planner" and body["meta"]["composed"] is False
    saved = rows("select role, content from public.chat_messages where conversation_id = %s order by id", body["conversation_id"])
    assert saved == [("user", "How much protein is in paneer?"), ("assistant", "Paneer has 18 g of protein per 100 g.")]


def test_a_second_message_joins_the_same_conversation_and_the_list_and_detail_show_it(client, users, fake_graph):
    onboard(client)
    first = client.post("/chat", json={"message": "hello there"}).json()
    fake_graph["propose"] = False
    second = client.post("/chat", json={"message": "and one more", "conversation_id": first["conversation_id"]}).json()
    assert second["conversation_id"] == first["conversation_id"]
    listing = client.get("/chat").json()["conversations"]
    assert [c["id"] for c in listing] == [first["conversation_id"]] and listing[0]["title"] == "hello there"
    detail = client.get(f"/chat/{first['conversation_id']}").json()
    assert [(m["role"], m["content"]) for m in detail["messages"]][::2] == [("user", "hello there"), ("user", "and one more")]
    assert len(detail["messages"]) == 4


def test_the_input_guard_stops_a_harmful_message_before_any_model_and_says_so(client, users, fake_graph, monkeypatch):
    onboard(client)
    monkeypatch.setattr("app.agents.router.route_message", lambda *a, **k: pytest.fail("a model ran for a blocked message"))
    body = client.post("/chat", json={"message": "I want to kill myself"}).json()
    assert body["blocked"] and body["meta"]["specialists"] == []
    saved = rows("select role, blocked from public.chat_messages where conversation_id = %s order by id", body["conversation_id"])
    assert saved == [("user", body["blocked"]), ("assistant", body["blocked"])]               # both sides carry the category


def test_a_blank_or_overlong_message_or_extra_field_is_refused_and_nothing_is_saved(client, users, fake_graph):
    onboard(client)
    for bad in ({"message": "   "}, {"message": "x" * 1001}, {"message": "hi", "role": "assistant"}, {}):
        assert client.post("/chat", json=bad).status_code == 422
    assert client.get("/chat").json() == {"conversations": []}


def test_a_proposal_pauses_the_chat_and_approving_applies_it_once(client, users, fake_graph):
    onboard(client)
    fake_graph["propose"] = True
    first = client.post("/chat", json={"message": "make me a plan"}).json()
    assert first["waiting_for"] == {"kind": "approve_proposal", "proposal_id": PROPOSAL, "summary": "A new plan"}
    assert DECIDED == []                                                                   # nothing applied without the user's answer
    answer = client.post(f"/chat/{first['conversation_id']}/decide", json={"choice": "approve"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["reply"] == "Decided: approve." and answer.json()["waiting_for"] is None
    assert DECIDED == [(str(users[0]), PROPOSAL, "approve")]                                # the id came from the saved state
    again = client.post(f"/chat/{first['conversation_id']}/decide", json={"choice": "approve"})
    assert again.status_code == 409 and len(DECIDED) == 1                                   # a second answer applies nothing
    last = rows("select content from public.chat_messages where conversation_id = %s order by id desc limit 1", first["conversation_id"])
    assert last == [("Decided: approve.",)]


def test_a_decision_needs_a_valid_choice_and_a_proposal_that_is_waiting(client, users, fake_graph):
    onboard(client)
    cid = client.post("/chat", json={"message": "hello"}).json()["conversation_id"]
    assert client.post(f"/chat/{cid}/decide", json={"choice": "maybe"}).status_code == 422
    assert client.post(f"/chat/{cid}/decide", json={"choice": "approve"}).status_code == 409   # nothing is waiting
    assert client.post(f"/chat/{cid}/decide", json={"choice": "approve", "proposal_id": PROPOSAL}).status_code == 422   # no id from the client
    assert DECIDED == []


def test_nobody_can_read_write_answer_or_delete_someone_elses_chat(client, users, fake_graph):
    onboard(client)
    fake_graph["propose"] = True
    mine = client.post("/chat", json={"message": "private plan please"}).json()
    client.session.user_id = users[1]
    onboard(client)
    cid = mine["conversation_id"]
    assert client.get(f"/chat/{cid}").status_code == 404
    assert client.get("/chat").json() == {"conversations": []}
    assert client.post("/chat", json={"message": "hi", "conversation_id": cid}).status_code == 404
    assert client.post(f"/chat/{cid}/decide", json={"choice": "approve"}).status_code == 404
    assert client.delete(f"/chat/{cid}").status_code == 404
    assert DECIDED == []
    client.session.user_id = users[0]
    assert client.get(f"/chat/{cid}").status_code == 200                                    # the owner still has it, untouched
    assert client.delete(f"/chat/{cid}").status_code == 204 and client.get(f"/chat/{cid}").status_code == 404


def test_a_busy_model_gives_a_friendly_503_and_the_user_message_is_kept(client, users, fake_graph, monkeypatch):
    onboard(client)

    def busy(*a, **k):
        raise LLMBusy()
    monkeypatch.setattr(chat_turn, "answer_message", busy)
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 503 and response.json()["detail"]
    assert [r[0] for r in rows("select role from public.chat_messages where user_id = %s", users[0])] == ["user"]


def test_the_chat_needs_a_signed_in_user(users):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:                                                      # no dependency override: a real, missing token
        assert anonymous.post("/chat", json={"message": "hi"}).status_code in (401, 403)
        assert anonymous.get("/chat").status_code in (401, 403)
        assert anonymous.post(f"/chat/{uuid.uuid4()}/decide", json={"choice": "approve"}).status_code in (401, 403)


def test_the_second_message_reaches_the_router_with_the_first_exchange_but_not_with_itself(client, users, fake_graph, monkeypatch):
    onboard(client)
    seen = []

    def spy(message, menu, *, user_id, history=(), summary="", **k):
        seen.append((message, list(history), summary))
        return []
    monkeypatch.setattr("app.agents.chat_graph.route_message", spy)
    fake_graph["own_router"] = True
    first = client.post("/chat", json={"message": "tell me about paneer"}).json()
    client.post("/chat", json={"message": "and the protein in that?", "conversation_id": first["conversation_id"]})
    assert seen[0] == ("tell me about paneer", [], "")                                          # a new chat has no context
    message, history, _ = seen[1]
    assert message == "and the protein in that?"
    assert [h[1] for h in history] == ["tell me about paneer", chat_turn_nothing_fits()]       # the first exchange, not the new message


def chat_turn_nothing_fits():
    from app.agents.chat_graph import NOTHING_FITS
    return NOTHING_FITS


def test_a_blocked_turn_is_not_sent_to_the_router_as_context_later(client, users, fake_graph, monkeypatch):
    onboard(client)
    seen = []
    fake_graph["own_router"] = True
    first = client.post("/chat", json={"message": "I want to kill myself"}).json()
    assert first["blocked"]
    monkeypatch.setattr("app.agents.chat_graph.route_message",
                        lambda message, menu, *, user_id, history=(), summary="", **k: seen.append(list(history)) or [])
    second = client.post("/chat", json={"message": "how much protein is in paneer?", "conversation_id": first["conversation_id"]})
    assert second.status_code == 200 and second.json()["blocked"] is None, second.text
    assert seen == [[]]                                                                           # neither side of the blocked turn came back


def test_each_message_starts_clean_after_a_blocked_turn_and_after_a_paused_turn(client, users, fake_graph):
    """Regression (found in 7.11c): a LangGraph thread keeps its state, so one thread per conversation replayed the last turn."""
    onboard(client)
    cid = client.post("/chat", json={"message": "I want to kill myself"}).json()["conversation_id"]
    second = client.post("/chat", json={"message": "how much protein is in paneer?", "conversation_id": cid}).json()
    assert second["blocked"] is None and second["reply"] == "Paneer has 18 g of protein per 100 g."
    assert len(second["meta"]["specialists"]) == 1                                         # nothing piled up from earlier turns
    fake_graph["propose"] = True
    paused = client.post("/chat", json={"message": "make me a plan", "conversation_id": cid}).json()
    assert paused["waiting_for"]
    fake_graph["propose"] = False
    after = client.post("/chat", json={"message": "never mind, what about tofu?", "conversation_id": cid}).json()
    assert after["waiting_for"] is None and after["reply"] == "Paneer has 18 g of protein per 100 g."
    assert client.post(f"/chat/{cid}/decide", json={"choice": "approve"}).status_code == 409   # the paused turn is no longer the latest
    assert DECIDED == []                                                                      # a proposal nobody answered is never applied


def test_deleting_a_chat_also_deletes_its_saved_graph_states(client, users, fake_graph):
    onboard(client)
    cid = client.post("/chat", json={"message": "hello"}).json()["conversation_id"]
    client.post("/chat", json={"message": "hello again", "conversation_id": cid})
    count = lambda: rows("select count(*) from langgraph.checkpoints where thread_id like %s", f"{users[0]}:{cid}:%")[0][0]
    assert count() > 0
    assert client.delete(f"/chat/{cid}").status_code == 204
    assert count() == 0


# ---------- the rolling summary (7.11d, D-099) ----------

@pytest.fixture
def summary_model(monkeypatch):
    """Replace only the summarizer's model call. `calls` records what it was asked to fold; `answer` is what it replies."""
    state = {"calls": [], "answer": "Vegetarian, asked about paneer.", "boom": False}

    def fake(old, messages, *, user_id):
        state["calls"].append((old, list(messages)))
        if state["boom"]:
            raise RuntimeError("model down")
        return state["answer"]
    monkeypatch.setattr(chat_turn, "summarize", fake)
    return state


def say(client, cid, n):
    for i in range(n):
        cid = client.post("/chat", json={"message": f"question {i}", "conversation_id": cid} if cid else {"message": f"question {i}"}).json()["conversation_id"]
    return cid


def summary_of(cid):
    return rows("select summary, summarized_through from public.chat_conversations where id = %s", cid)[0]


def test_the_summary_is_written_after_enough_messages_leave_the_window(client, users, fake_graph, summary_model):
    onboard(client)
    cid = say(client, None, 3)                                    # 6 messages: all inside the window, nothing to fold
    assert summary_model["calls"] == [] and summary_of(cid) == ("", 0)
    cid = say(client, cid, 2)                                     # 10 messages: the first 4 have left the window and are folded
    assert len(summary_model["calls"]) == 1
    old, folded = summary_model["calls"][0]
    assert old == "" and [t for _, t in folded][::2] == ["question 0", "question 1"] and len(folded) == 4
    summary, through = summary_of(cid)
    first_four = [r[0] for r in rows("select id from public.chat_messages where conversation_id = %s order by id limit 4", cid)]
    assert summary == "Vegetarian, asked about paneer." and through == first_four[-1]


def test_the_next_summary_builds_on_the_old_one_and_the_router_receives_it(client, users, fake_graph, summary_model, monkeypatch):
    onboard(client)
    cid = say(client, None, 5)
    summary_model["answer"] = "Vegetarian, asked about paneer and rotis."
    seen = []
    monkeypatch.setattr("app.agents.chat_graph.route_message",
                        lambda message, menu, *, user_id, history=(), summary="", **k: seen.append(summary) or [])
    fake_graph["own_router"] = True
    say(client, cid, 2)                                           # these two turns reach the router with the saved summary
    assert seen[0] == "Vegetarian, asked about paneer."
    assert summary_model["calls"][-1][0] == "Vegetarian, asked about paneer."                     # the next fold starts from the old summary


def test_a_failing_or_rejected_summary_keeps_the_old_one_and_never_breaks_the_chat(client, users, fake_graph, summary_model):
    onboard(client)
    cid = say(client, None, 5)
    before = summary_of(cid)
    summary_model["boom"] = True
    reply = client.post("/chat", json={"message": "still works", "conversation_id": cid})
    assert reply.status_code == 200 and summary_of(cid) == before                                 # the error was swallowed
    summary_model["boom"], summary_model["answer"] = False, None                                  # the checks said no
    assert client.post("/chat", json={"message": "and again", "conversation_id": cid}).status_code == 200
    assert summary_of(cid) == before


def test_blocked_messages_are_never_folded_into_the_summary(client, users, fake_graph, summary_model):
    onboard(client)
    cid = client.post("/chat", json={"message": "I want to kill myself"}).json()["conversation_id"]
    say(client, cid, 5)
    folded = [t for _, ms in summary_model["calls"] for _, t in ms]
    joined = " ".join(folded).lower()
    assert folded and "kill myself" not in joined and "tele-manas" not in joined                  # neither the message nor the crisis reply
