"""Step 7.1: the tool registry and the specialist factory, with a scripted fake model (no LLM, no network)."""

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents.context import RunContext
from app.agents.runner import ToolCall, Turn, build_specialist
from app.agents.spec import SpecialistSpec
from app.agents.tools import Tool, ToolRegistry


class LookupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food: str


class LeakyArgs(BaseModel):          # no extra="forbid"
    food: str


class WithUserArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


seen: list[UUID] = []


def lookup(ctx: RunContext, args: LookupArgs) -> dict:
    seen.append(ctx.user_id)
    return {"food": args.food, "kcal": 100}


def boom(ctx: RunContext, args: LookupArgs) -> dict:
    raise RuntimeError("secret internal detail")


def make_registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(Tool("lookup_food", "Find a food", LookupArgs, lookup))
    r.register(Tool("propose_thing", "Create a pending proposal", LookupArgs, lookup, scope="propose"))
    r.register(Tool("broken", "Always fails", LookupArgs, boom))
    return r


def spec(**over) -> SpecialistSpec:
    base = dict(name="nutrition", system_prompt="You help with food.", tools=frozenset({"lookup_food", "broken"}))
    return SpecialistSpec(**{**base, **over})


def scripted(*turns: Turn):
    """A fake model that plays the given turns in order and records what it was shown."""
    shown: list[list] = []
    it = iter(turns)

    def model(messages):
        shown.append(messages)
        return next(it)
    model.shown = shown   # type: ignore[attr-defined]
    return model


CTX = RunContext(user_id=uuid4())


# ---------- registry ----------

def test_a_tool_cannot_be_registered_twice():
    r = make_registry()
    with pytest.raises(ValueError, match="already registered"):
        r.register(Tool("lookup_food", "x", LookupArgs, lookup))


def test_a_tool_must_refuse_unknown_arguments():
    with pytest.raises(ValueError, match="extra='forbid'"):
        Tool("t", "x", LeakyArgs, lookup)


def test_a_tool_may_not_let_the_model_supply_the_user():
    with pytest.raises(ValueError, match="identity"):
        Tool("t", "x", WithUserArgs, lookup)


def test_a_tool_scope_is_read_or_propose_only():
    with pytest.raises(ValueError, match="read or propose"):
        Tool("t", "x", LookupArgs, lookup, scope="apply")  # type: ignore[arg-type]


# ---------- spec checks ----------

@pytest.mark.parametrize("over", [
    {"tools": frozenset({"nope"})}, {"max_steps": 0}, {"max_steps": 11}, {"token_budget": 0},
    {"token_budget": 20_001}, {"max_tokens_per_call": 0}, {"timeout_s": 0}, {"system_prompt": "  "}, {"name": ""},
])
def test_a_bad_spec_is_refused_before_anything_runs(over):
    with pytest.raises(ValueError):
        build_specialist(spec(**over), make_registry(), scripted())


# ---------- the loop ----------

def test_a_plain_answer_needs_no_tools():
    s = build_specialist(spec(), make_registry(), scripted(Turn(final="Eat dal.", tokens=50)))
    r = s.run("What should I eat?", CTX)
    assert (r.status, r.answer, r.steps, r.tokens, r.tools) == ("ok", "Eat dal.", 1, 50, [])


def test_a_tool_result_is_shown_to_the_model_and_the_user_id_comes_from_the_harness():
    seen.clear()
    model = scripted(Turn(call=ToolCall("lookup_food", {"food": "paneer"}), tokens=40), Turn(final="Paneer is 265 kcal.", tokens=30))
    r = build_specialist(spec(), make_registry(), model).run("Calories in paneer?", CTX)
    assert r.answer == "Paneer is 265 kcal." and r.tokens == 70 and r.steps == 2
    assert seen == [CTX.user_id]
    assert [(t.name, t.outcome) for t in r.tools] == [("lookup_food", "ok")]
    assert model.shown[1][-1] == {"role": "tool", "name": "lookup_food", "content": {"food": "paneer", "kcal": 100}}


def test_a_tool_not_on_the_allowlist_is_refused_even_if_it_exists_in_the_registry():
    seen.clear()
    model = scripted(Turn(call=ToolCall("propose_thing", {"food": "x"})), Turn(final="Sorry."))
    r = build_specialist(spec(), make_registry(), model).run("do it", CTX)
    assert seen == []                                    # the tool never ran
    assert [(t.name, t.outcome) for t in r.tools] == [("propose_thing", "refused")]
    assert "may not use" in model.shown[1][-1]["content"]["error"]


def test_a_made_up_tool_is_refused():
    model = scripted(Turn(call=ToolCall("delete_everything", {})), Turn(final="ok"))
    r = build_specialist(spec(), make_registry(), model).run("x", CTX)
    assert [(t.name, t.outcome) for t in r.tools] == [("delete_everything", "refused")]


def test_the_model_cannot_pass_a_user_id_or_any_extra_field():
    seen.clear()
    other = str(uuid4())
    model = scripted(Turn(call=ToolCall("lookup_food", {"food": "dal", "user_id": other})), Turn(final="ok"))
    r = build_specialist(spec(), make_registry(), model).run("x", CTX)
    assert seen == [] and r.tools[0].outcome == "bad_args"


def test_missing_or_wrong_typed_arguments_are_bad_args_not_crashes():
    model = scripted(Turn(call=ToolCall("lookup_food", {"food": 5})), Turn(call=ToolCall("lookup_food", {})), Turn(final="ok"))
    r = build_specialist(spec(max_steps=5), make_registry(), model).run("x", CTX)
    assert [t.outcome for t in r.tools] == ["bad_args", "bad_args"] and r.answer == "ok"


def test_a_failing_tool_does_not_crash_the_run_or_leak_its_error():
    model = scripted(Turn(call=ToolCall("broken", {"food": "x"})), Turn(final="Could not look that up."))
    r = build_specialist(spec(), make_registry(), model).run("x", CTX)
    assert r.answer == "Could not look that up." and r.tools[0].outcome == "error"
    assert "secret internal detail" not in str(model.shown[1])
    assert r.tools[0].detail == "RuntimeError"


# ---------- limits ----------

def test_the_step_limit_stops_a_model_that_keeps_calling_tools():
    call = Turn(call=ToolCall("lookup_food", {"food": "a"}), tokens=1)
    r = build_specialist(spec(max_steps=3), make_registry(), scripted(call, call, call, call, call)).run("x", CTX)
    assert (r.status, r.steps, r.answer) == ("step_limit", 3, None) and len(r.tools) == 3


def test_the_token_budget_stops_the_run():
    big = Turn(call=ToolCall("lookup_food", {"food": "a"}), tokens=4_000)
    r = build_specialist(spec(token_budget=6_000), make_registry(), scripted(big, big, big)).run("x", CTX)
    assert r.status == "token_budget" and r.tokens == 8_000 and len(r.tools) == 1


def test_the_timeout_stops_the_run_before_the_next_model_call():
    now = iter([0.0, 1.0, 100.0])           # start, first check, second check (past the 30 s limit)
    model = scripted(Turn(call=ToolCall("lookup_food", {"food": "a"})), Turn(final="never"))
    r = build_specialist(spec(), make_registry(), model, clock=lambda: next(now)).run("x", CTX)
    assert r.status == "timeout" and r.steps == 1 and r.answer is None


def test_a_reply_with_neither_call_nor_answer_ends_the_run():
    r = build_specialist(spec(), make_registry(), scripted(Turn())).run("x", CTX)
    assert (r.status, r.answer) == ("ok", "")


# ---------- vanishing ----------

def test_two_spawns_share_nothing():
    reg = make_registry()
    first_model = scripted(Turn(call=ToolCall("lookup_food", {"food": "secret-from-user-1"})), Turn(final="done"))
    build_specialist(spec(), reg, first_model).run("task one", RunContext(uuid4()))
    second_model = scripted(Turn(final="hello"))
    r2 = build_specialist(spec(), reg, second_model).run("task two", RunContext(uuid4()))
    assert "secret-from-user-1" not in str(second_model.shown)
    assert r2.tools == [] and r2.steps == 1


def test_the_same_agent_run_twice_starts_clean():
    model = scripted(Turn(call=ToolCall("lookup_food", {"food": "a"})), Turn(final="one"), Turn(final="two"))
    agent = build_specialist(spec(), make_registry(), model)
    a, b = agent.run("first", CTX), agent.run("second", CTX)
    assert len(a.tools) == 1 and b.tools == [] and b.steps == 1
    assert [m["content"] for m in model.shown[2] if m["role"] == "user"] == ["second"]
