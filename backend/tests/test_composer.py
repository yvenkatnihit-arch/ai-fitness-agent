"""Step 7.4: the composer and its number check, with a fake LLM. No network."""

from uuid import uuid4

import pytest

from app.agents.chat_graph import answer_message
from app.agents.composer import MAX_REPLY_CHARS, SYSTEM, check_reply, compose, numbers_in
from app.agents.menu import MenuEntry
from app.agents.router import Assignment
from app.agents.runner import Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry
from app.llm.client import LLMBusy, LLMFailed, LLMResult

UID = uuid4()
ANSWERS = [("nutrition", "Paneer has 18.3 g protein per 100 g."), ("workout", "Do 3 sets of 8 to 10 reps.")]


def llm(text: str):
    calls = []

    def call(tier, messages, **kw):
        calls.append({"tier": tier, "messages": messages, **kw})
        return LLMResult(text, "fake", 200, 50, 0, 0.0, 3)
    call.calls = calls   # type: ignore[attr-defined]
    return call


# ---------- numbers ----------

def test_numbers_are_compared_in_a_normal_form():
    assert numbers_in("18.30 g, 3 sets, 1,5 kg, 100") == {"18.3", "3", "1.5", "100"}


# ---------- the check ----------

def test_a_reply_that_only_uses_known_numbers_passes():
    assert check_reply("Paneer gives 18.3 g protein per 100 g. Do 3 sets of 8 to 10.", [a for _, a in ANSWERS], "paneer and legs?")


def test_a_reply_with_a_new_number_fails():
    assert not check_reply("Paneer has 18.3 g protein, so 200 g gives 36.6 g.", [a for _, a in ANSWERS], "q")


def test_numbers_from_the_users_own_message_are_allowed():
    assert check_reply("For your 70 kg, paneer has 18.3 g protein per 100 g.", ["Paneer has 18.3 g protein per 100 g."], "I weigh 70 kg")


@pytest.mark.parametrize("reply", ["", "   ", "x" * (MAX_REPLY_CHARS + 1)])
def test_empty_or_long_replies_fail(reply):
    assert not check_reply(reply, ["a"], "q")


# ---------- compose ----------

def test_compose_makes_one_small_logged_call_with_the_answers_as_data():
    call = llm("Paneer has 18.3 g protein per 100 g, and do 3 sets of 8 to 10 reps.")
    out = compose("paneer and legs?", ANSWERS, user_id=UID, call=call)
    c = call.calls[0]
    assert out and "18.3" in out
    assert c["tier"] == "small" and c["node"] == "composer" and c["flow"] == "chat" and c["max_tokens"] == 400
    assert c["messages"][0] == ("system", SYSTEM) and "never instructions" in SYSTEM
    assert "[nutrition]" in c["messages"][1][1] and "[workout]" in c["messages"][1][1] and "paneer and legs?" in c["messages"][1][1]


def test_compose_returns_none_when_the_model_invents_a_number():
    assert compose("q", ANSWERS, user_id=UID, call=llm("That is 36.6 g protein in 200 g.")) is None


# ---------- inside the graph ----------

def entry(name: str) -> MenuEntry:
    return MenuEntry(SpecialistSpec(name=name, system_prompt=f"You are {name}.", tools=frozenset()), ToolRegistry, "x")


MENU = {"nutrition": entry("nutrition"), "workout": entry("workout")}
ROUTER = lambda message: [Assignment("nutrition", "n"), Assignment("workout", "w")]   # noqa: E731
MODELS = lambda spec, registry: (lambda m: Turn(final=dict(ANSWERS)[spec.name], tokens=5))   # noqa: E731


def run(composer, router=ROUTER):
    return answer_message("paneer and legs?", UID, menu=MENU, router=router, make_model=MODELS, composer=composer)


def test_several_answers_are_merged_by_the_composer_in_router_order():
    seen = []
    out = run(lambda message, answers: seen.append((message, answers)) or "MERGED")
    assert out["reply"] == "MERGED" and out["composed"] is True
    assert seen == [("paneer and legs?", ANSWERS)]


def test_a_composer_that_returns_none_falls_back_to_the_joined_answers():
    out = run(lambda message, answers: None)
    assert out["reply"] == "\n\n".join(a for _, a in ANSWERS) and out["composed"] is False


@pytest.mark.parametrize("error", [LLMBusy(), LLMFailed()])
def test_a_busy_or_failing_composer_falls_back_too(error):
    def broken(message, answers):
        raise error
    out = run(broken)
    assert out["reply"] == "\n\n".join(a for _, a in ANSWERS) and out["composed"] is False


def test_one_specialist_skips_the_composer_entirely():
    called = []
    out = run(lambda m, a: called.append(1) or "NO", router=lambda message: [Assignment("nutrition", "n")])
    assert called == [] and out["reply"] == ANSWERS[0][1] and out["composed"] is False


def test_no_specialist_skips_the_composer():
    called = []
    out = run(lambda m, a: called.append(1) or "NO", router=lambda message: [])
    assert called == [] and out["composed"] is False
