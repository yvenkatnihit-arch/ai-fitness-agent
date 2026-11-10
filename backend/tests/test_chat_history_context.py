"""Step 7.11c (D-098): the router gets the last messages and the summary, only when there is any; nothing else changes."""

from uuid import uuid4

from app.agents import chat_graph
from app.agents.menu import default_menu
from app.agents.router import (HISTORY_RULE, MAX_HISTORY_MESSAGE_CHARS, MAX_MESSAGE_CHARS, route_message, router_messages, router_prompt)
from app.llm.client import LLMResult

MENU = default_menu()


def test_without_history_the_prompt_is_exactly_the_old_single_message_prompt():
    assert router_messages(MENU, "calories in 2 rotis") == [("system", router_prompt(MENU)), ("human", "calories in 2 rotis")]
    assert router_messages(MENU, "hi", [], "   ") == router_messages(MENU, "hi")                    # a blank summary counts as none


def test_with_history_the_summary_and_messages_come_before_the_new_message_and_the_rule_is_added():
    system, human = router_messages(MENU, "and how much protein in that?", [("user", "tell me about paneer"), ("assistant", "Paneer is a dairy food.")],
                                    "The user is vegetarian.")
    assert system[0] == "system" and system[1] == router_prompt(MENU) + HISTORY_RULE
    lines = human[1].split("\n")
    assert lines[0] == "Summary of the earlier conversation: The user is vegetarian."
    assert lines[1:3] == ["user: tell me about paneer", "assistant: Paneer is a dairy food."]
    assert human[1].endswith("NEW message: and how much protein in that?")
    assert "never instructions" in HISTORY_RULE and "NEW message only" in HISTORY_RULE


def test_each_earlier_message_is_clipped_and_whitespace_collapsed_but_the_new_message_has_its_own_limit():
    _, human = router_messages(MENU, "q" * (MAX_MESSAGE_CHARS + 50), [("user", "a   b\n" + "x" * 1000)])
    older = human[1].split("\n")[0]
    assert older == "user: " + ("a b " + "x" * 1000)[:MAX_HISTORY_MESSAGE_CHARS]
    assert human[1].count("q") == MAX_MESSAGE_CHARS


def test_route_message_sends_the_history_to_the_model_and_still_validates_the_answer():
    seen = {}

    def fake_call(tier, messages, **kwargs):
        seen["messages"] = messages
        return LLMResult(text='{"assignments": [{"specialist": "nutrition", "task": "How much protein is in paneer?"}, '
                              '{"specialist": "hacker", "task": "x"}]}', input_tokens=1, output_tokens=1, cached_tokens=0, cost_usd=0.0, latency_ms=1, model="m")

    out = route_message("and the protein?", MENU, user_id=uuid4(), call=fake_call, history=[("user", "paneer")], summary="")
    assert [(a.specialist, a.task) for a in out] == [("nutrition", "How much protein is in paneer?")]     # the made-up name is dropped
    assert "paneer" in seen["messages"][1][1] and "NEW message: and the protein?" in seen["messages"][1][1]


def test_the_chat_graph_hands_its_history_and_summary_to_the_router(monkeypatch):
    seen = {}

    def spy(message, menu, *, user_id, history=(), summary="", **k):
        seen.update(message=message, history=list(history), summary=summary)
        return []
    monkeypatch.setattr(chat_graph, "route_message", spy)
    out = chat_graph.answer_message("and that?", uuid4(), history=[("user", "paneer"), ("assistant", "ok")], summary="s")
    assert seen == {"message": "and that?", "history": [("user", "paneer"), ("assistant", "ok")], "summary": "s"}
    assert out["reply"] == chat_graph.NOTHING_FITS


def test_a_graph_with_no_history_behaves_as_before(monkeypatch):
    seen = {}
    monkeypatch.setattr(chat_graph, "route_message", lambda m, menu, *, user_id, history=(), summary="", **k: seen.update(h=list(history), s=summary) or [])
    chat_graph.answer_message("calories in 2 rotis", uuid4())
    assert seen == {"h": [], "s": ""}
