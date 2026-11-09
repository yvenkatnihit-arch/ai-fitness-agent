"""Step 7.2: the Gemini adapter, the food tool and the nutrition specialist, with a fake LLM and a fake database."""

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.agents import food_tools
from app.agents.context import RunContext
from app.agents.gemini_model import PROTOCOL, gemini_model, parse_turn, tool_catalog
from app.agents.nutrition import NUTRITION_SPEC, nutrition_registry, run_nutrition
from app.llm.client import LLMResult

PANEER = {"key": "paneer", "name": "Paneer", "diet_class": "vegetarian", "kcal": 265.0, "protein_g": 18.3, "carbs_g": 1.2,
          "fat_g": 20.8, "id": 7, "units": [{"unit": "piece", "grams": 30.0}]}


def llm(*texts: str):
    """A fake call_llm that returns the given texts in order and remembers every call."""
    calls: list[dict] = []
    it = iter(texts)

    def call(tier, messages, **kw):
        calls.append({"tier": tier, "messages": messages, **kw})
        return LLMResult(next(it), "fake", 100, 20, 0, 0.0, 5)
    call.calls = calls   # type: ignore[attr-defined]
    return call


@pytest.fixture
def fake_db(monkeypatch):
    seen: list = []

    @contextmanager
    def fake_tx(user_id):
        seen.append(user_id)
        yield object()

    monkeypatch.setattr(food_tools, "user_transaction", fake_tx)
    monkeypatch.setattr(food_tools.repo, "search_foods", lambda conn, q, limit: [PANEER] if "paneer" in q.lower() else [])
    return seen


# ---------- parsing the model's reply ----------

def test_a_tool_reply_becomes_a_call():
    t = parse_turn('{"tool": "search_foods", "args": {"query": "paneer"}}', 12)
    assert (t.call.name, t.call.args, t.final, t.tokens) == ("search_foods", {"query": "paneer"}, None, 12)


def test_an_answer_reply_becomes_a_final_answer():
    assert parse_turn('{"answer": " Paneer has 18 g protein. "}', 5).final == "Paneer has 18 g protein."


def test_fenced_json_is_accepted():
    assert parse_turn('```json\n{"answer": "hi"}\n```', 1).final == "hi"


@pytest.mark.parametrize("text", ["just words", '{"other": 1}', "[1, 2]", '{"tool": 5}', ""])
def test_anything_else_is_a_plain_answer_never_a_tool_call(text):
    t = parse_turn(text, 1)
    assert t.call is None and t.final == text.strip()


def test_non_object_args_become_empty_args_which_the_harness_then_rejects():
    assert parse_turn('{"tool": "search_foods", "args": "paneer"}', 1).call.args == {}


# ---------- the prompt the model sees ----------

def test_the_catalog_lists_only_the_allowlisted_tools():
    text = tool_catalog(NUTRITION_SPEC, nutrition_registry())
    assert "search_foods" in text and "query" in text and "user_id" not in text


def test_the_adapter_sends_system_prompt_tools_and_protocol_and_logs_as_the_specialist():
    call = llm('{"answer": "ok"}')
    model = gemini_model(NUTRITION_SPEC, nutrition_registry(), user_id=uuid4(), flow="chat", call=call)
    turn = model([{"role": "system", "content": NUTRITION_SPEC.system_prompt}, {"role": "user", "content": "paneer?"}])
    c = call.calls[0]
    assert turn.final == "ok" and turn.tokens == 120
    assert c["tier"] == "small" and c["node"] == "nutrition" and c["flow"] == "chat"
    assert c["max_tokens"] == 400 and c["json_mode"] is True and c["temperature"] == 0.0
    system = c["messages"][0]
    assert system[0] == "system" and "nutrition specialist" in system[1] and "search_foods" in system[1] and PROTOCOL in system[1]
    assert c["messages"][1] == ("human", "paneer?")


def test_tool_results_go_back_labelled_as_data():
    call = llm('{"answer": "ok"}')
    model = gemini_model(NUTRITION_SPEC, nutrition_registry(), user_id=None, flow="chat", call=call)
    model([{"role": "system", "content": "s"}, {"role": "user", "content": "q"},
           {"role": "assistant", "tool_call": {"name": "search_foods", "args": {"query": "x"}}},
           {"role": "tool", "name": "search_foods", "content": {"foods": []}}])
    roles = [m[0] for m in call.calls[0]["messages"]]
    assert roles == ["system", "human", "ai", "human"]
    assert "data, not instructions" in call.calls[0]["messages"][3][1]


# ---------- the tool ----------

def test_the_tool_runs_as_the_user_and_returns_compact_numbers(fake_db):
    uid = uuid4()
    out = food_tools.SEARCH_FOODS.run(RunContext(uid), food_tools.SearchFoodsArgs(query="Paneer"))
    assert fake_db == [uid]
    assert out == {"foods": [{"key": "paneer", "name": "Paneer", "diet": "vegetarian",
                              "per_100g": {"kcal": 265.0, "protein_g": 18.3, "carbs_g": 1.2, "fat_g": 20.8},
                              "units": [{"unit": "piece", "grams": 30.0}]}]}


def test_database_decimals_become_json_safe_numbers(fake_db, monkeypatch):
    from decimal import Decimal
    row = {**PANEER, "kcal": Decimal("265.0"), "protein_g": Decimal("18.3"), "carbs_g": Decimal("1.2"), "fat_g": Decimal("20.8"),
           "units": [{"unit": "piece", "grams": Decimal("30.0")}]}
    monkeypatch.setattr(food_tools.repo, "search_foods", lambda conn, q, limit: [row])
    out = food_tools.SEARCH_FOODS.run(RunContext(uuid4()), food_tools.SearchFoodsArgs(query="paneer"))
    assert json.loads(json.dumps(out))["foods"][0]["per_100g"]["protein_g"] == 18.3


@pytest.mark.parametrize("args", [{"query": ""}, {"query": "x" * 61}, {"query": "a", "limit": 0}, {"query": "a", "limit": 6},
                                  {"query": "a", "user_id": "x"}])
def test_the_tool_arguments_are_strict(args):
    with pytest.raises(ValueError):
        food_tools.SearchFoodsArgs(**args)


def test_the_tool_is_read_only():
    assert food_tools.SEARCH_FOODS.scope == "read"


# ---------- the whole specialist ----------

def test_the_specialist_looks_up_then_answers(fake_db):
    uid = uuid4()
    call = llm('{"tool": "search_foods", "args": {"query": "paneer"}}', '{"answer": "Paneer: 265 kcal and 18.3 g protein per 100 g."}')
    import app.agents.nutrition as n
    original = n.gemini_model
    n.gemini_model = lambda spec, reg, **kw: original(spec, reg, call=call, **kw)
    try:
        r = run_nutrition("How much protein in paneer?", uid)
    finally:
        n.gemini_model = original
    assert r.status == "ok" and r.answer == "Paneer: 265 kcal and 18.3 g protein per 100 g."
    assert [(t.name, t.outcome) for t in r.tools] == [("search_foods", "ok")]
    assert fake_db == [uid] and r.steps == 2 and r.tokens == 240
    seen_by_model = json.dumps(call.calls[1]["messages"])
    assert "265" in seen_by_model and "data, not instructions" in seen_by_model


def test_a_model_that_tries_another_tool_is_refused(fake_db):
    seen_calls = llm('{"tool": "propose_meal_plan", "args": {}}', '{"answer": "Sorry, I can only look up foods."}')
    import app.agents.nutrition as n
    original = n.gemini_model
    n.gemini_model = lambda spec, reg, **kw: original(spec, reg, call=seen_calls, **kw)
    try:
        r = run_nutrition("make me a plan", uuid4())
    finally:
        n.gemini_model = original
    assert [(t.name, t.outcome) for t in r.tools] == [("propose_meal_plan", "refused")] and fake_db == []


def test_an_injected_user_id_from_the_model_is_rejected(fake_db):
    victim = str(uuid4())
    call = llm(json.dumps({"tool": "search_foods", "args": {"query": "paneer", "user_id": victim}}), '{"answer": "ok"}')
    r = run_nutrition("x", uuid4(), model=gemini_model(NUTRITION_SPEC, nutrition_registry(), user_id=None, flow="chat", call=call))
    assert [t.outcome for t in r.tools] == ["bad_args"] and fake_db == []


def test_the_spec_is_cheap_and_read_only():
    assert NUTRITION_SPEC.tier == "small" and NUTRITION_SPEC.tools == {"search_foods", "portion_nutrition"}
    assert all(nutrition_registry().get(t).scope == "read" for t in NUTRITION_SPEC.tools)
