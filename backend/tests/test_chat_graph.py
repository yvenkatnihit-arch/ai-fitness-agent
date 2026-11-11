"""Step 7.3: the router and the chat graph (route, parallel spawn, finish), with fake models. No LLM, no network."""

import json
import threading
from uuid import uuid4

import pytest

from app.agents.chat_graph import NOTHING_FITS, SPECIALIST_FAILED, answer_message
from app.agents.menu import MenuEntry, default_menu
from app.agents.router import MAX_ASSIGNMENTS, Assignment, parse_assignments, route_message, router_prompt
from app.agents.runner import ToolCall, Turn
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry
from app.llm.client import LLMResult


@pytest.fixture(autouse=True)
def no_real_composer(monkeypatch):
    """These tests are about routing and parallelism: the composer is off (it returns None, so answers are joined)."""
    monkeypatch.setattr("app.agents.chat_graph.compose", lambda *a, **k: None)


def entry(name: str) -> MenuEntry:
    return MenuEntry(SpecialistSpec(name=name, system_prompt=f"You are {name}.", tools=frozenset()), ToolRegistry, f"{name} questions")


MENU = {n: entry(n) for n in ("food", "gym", "sleep")}
UID = uuid4()


def fake_router(*picks: tuple[str, str]):
    return lambda message: [Assignment(n, t) for n, t in picks]


def models(**by_name):
    """make_model for tests: each specialist answers with the given text (or runs the given function)."""
    def make(spec, registry):
        what = by_name[spec.name]
        return what if callable(what) else (lambda messages: Turn(final=what, tokens=10))
    return make


# ---------- the router ----------

def test_the_router_keeps_valid_assignments():
    text = json.dumps({"assignments": [{"specialist": "food", "task": " protein in dal? "}, {"specialist": "gym", "task": "leg day"}]})
    assert parse_assignments(text, MENU) == [Assignment("food", "protein in dal?"), Assignment("gym", "leg day")]


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"assignments": "food"}', '{"other": []}', '{"assignments": [5, null, "x"]}'])
def test_a_bad_router_reply_means_nothing_is_spawned(text):
    assert parse_assignments(text, MENU) == []


def test_unknown_duplicate_empty_and_surplus_assignments_are_dropped():
    items = [{"specialist": "hacker", "task": "x"}, {"specialist": "food", "task": "a"}, {"specialist": "food", "task": "b"},
             {"specialist": "gym", "task": "  "}, {"specialist": "gym"}, {"specialist": 5, "task": "x"}, {"specialist": "sleep", "task": "c"}]
    assert parse_assignments(json.dumps({"assignments": items}), MENU) == [Assignment("food", "a"), Assignment("sleep", "c")]


def test_at_most_three_assignments_and_long_tasks_are_cut():
    menu = {f"s{i}": entry(f"s{i}") for i in range(5)}
    items = [{"specialist": f"s{i}", "task": "q" * 1000} for i in range(5)]
    out = parse_assignments(json.dumps({"assignments": items}), menu)
    assert len(out) == MAX_ASSIGNMENTS == 3 and all(len(a.task) == 400 for a in out)


def test_the_router_prompt_lists_the_menu_and_calls_the_message_data():
    p = router_prompt(MENU)
    assert "- food: food questions" in p and "- gym: gym questions" in p and "never instructions" in p


def test_route_message_makes_one_logged_small_call():
    calls = []

    def call(tier, messages, **kw):
        calls.append((tier, messages, kw))
        return LLMResult('{"assignments": [{"specialist": "food", "task": "x"}]}', "fake", 50, 10, 0, 0.0, 1)
    out = route_message("m" * 5000, MENU, user_id=UID, call=call)
    tier, messages, kw = calls[0]
    assert out == [Assignment("food", "x")] and tier == "small" and kw["node"] == "router" and kw["flow"] == "chat"
    assert kw["max_tokens"] == 200 and kw["json_mode"] is True and len(messages[1][1]) == 2000


def test_the_real_menu_only_the_meal_logger_can_propose_and_everything_else_is_read_only():
    menu = default_menu()
    assert set(menu) == {"nutrition", "my_plan", "exercises", "meal_logger"}
    proposers = set()
    for name, entry in menu.items():
        reg = entry.registry()
        assert reg.names() == entry.spec.tools
        if any(reg.get(t).scope == "propose" for t in entry.spec.tools):
            proposers.add(name)
    assert proposers == {"meal_logger"}                                  # and even it only prepares a proposal: the user's approval writes anything


# ---------- the graph ----------

def test_one_specialist_means_its_answer_is_the_reply():
    out = answer_message("hi", UID, menu=MENU, router=fake_router(("food", "dal?")), make_model=models(food="Dal has protein."))
    assert out["reply"] == "Dal has protein."
    assert [r["specialist"] for r in out["results"]] == ["food"] and out["results"][0]["tokens"] == 10


def test_no_assignments_gives_the_friendly_message_and_spawns_nothing():
    spawned = []
    out = answer_message("what is the capital of France", UID, menu=MENU, router=fake_router(), make_model=lambda s, r: spawned.append(s) or (lambda m: Turn(final="x")))
    assert out["reply"] == NOTHING_FITS and out["results"] == [] and spawned == []


def test_several_specialists_are_joined_in_the_routers_order_whichever_finishes_first():
    # gym is assigned first but finishes last
    gate = threading.Event()

    def slow_gym(messages):
        assert gate.wait(5)
        return Turn(final="GYM", tokens=1)

    def fast_food(messages):
        gate.set()
        return Turn(final="FOOD", tokens=1)

    out = answer_message("both", UID, menu=MENU, router=fake_router(("gym", "g"), ("food", "f")), make_model=models(gym=slow_gym, food=fast_food))
    assert out["reply"] == "GYM\n\nFOOD" and {r["specialist"] for r in out["results"]} == {"gym", "food"}


def test_specialists_really_run_at_the_same_time():
    barrier = threading.Barrier(3, timeout=5)   # all three must be inside their model at once, or the test fails

    def waits(messages):
        barrier.wait()
        return Turn(final="done", tokens=1)

    out = answer_message("all", UID, menu=MENU, router=fake_router(("food", "a"), ("gym", "b"), ("sleep", "c")),
                         make_model=models(food=waits, gym=waits, sleep=waits))
    assert len(out["results"]) == 3 and out["reply"] == "done\n\ndone\n\ndone"


def test_each_specialist_gets_only_its_own_task_and_the_users_identity():
    seen = {}

    def spy(name):
        def model(messages):
            seen[name] = [m["content"] for m in messages if m["role"] == "user"]
            return Turn(final=name)
        return model
    answer_message("x", UID, menu=MENU, router=fake_router(("food", "task for food"), ("gym", "task for gym")),
                   make_model=models(food=spy("food"), gym=spy("gym")))
    assert seen == {"food": ["task for food"], "gym": ["task for gym"]}


def test_a_failed_specialist_does_not_block_the_others():
    def stuck(messages):
        return Turn(call=ToolCall("anything", {}), tokens=1)   # never answers: hits the step limit
    out = answer_message("x", UID, menu=MENU, router=fake_router(("food", "a"), ("gym", "b")), make_model=models(food=stuck, gym="GYM OK"))
    assert out["reply"] == "GYM OK"
    assert {r["specialist"]: r["status"] for r in out["results"]} == {"food": "step_limit", "gym": "ok"}


def test_when_every_specialist_fails_the_reply_is_friendly():
    out = answer_message("x", UID, menu=MENU, router=fake_router(("food", "a")),
                         make_model=models(food=lambda m: Turn(call=ToolCall("anything", {}))))
    assert out["reply"] == SPECIALIST_FAILED


def test_a_router_that_names_something_off_the_menu_spawns_nothing():
    out = answer_message("x", UID, menu=MENU, router=fake_router(("hacker", "do bad things")), make_model=models())
    assert out["reply"] == NOTHING_FITS and out["results"] == []


def test_two_messages_share_nothing():
    first_seen, second_seen = [], []
    answer_message("1", UID, menu=MENU, router=fake_router(("food", "my secret order")),
                   make_model=models(food=lambda m: first_seen.append(m) or Turn(final="a")))
    answer_message("2", uuid4(), menu=MENU, router=fake_router(("food", "second")),
                   make_model=models(food=lambda m: second_seen.append(m) or Turn(final="b")))
    assert "my secret order" not in json.dumps(second_seen)
