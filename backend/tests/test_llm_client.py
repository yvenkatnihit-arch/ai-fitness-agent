"""LLM client: retries, friendly errors, logging and cost. A fake model stands in for Gemini (offline, free)."""

import pytest
from langchain_core.messages import AIMessage

from app.llm import client
from app.llm.client import LLMBusy, LLMFailed, call_llm, is_rate_limit
from app.llm.pricing import estimate_cost_usd


class FakeModel:
    """Plays back a list of replies; an Exception in the list is raised instead of returned."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def reply(text="hello", i=100, o=20, cached=0):
    return AIMessage(content=text, usage_metadata={
        "input_tokens": i, "output_tokens": o, "total_tokens": i + o, "input_token_details": {"cache_read": cached},
    })


@pytest.fixture
def runs(monkeypatch):
    logged = []
    monkeypatch.setattr(client, "record_run", lambda **kw: logged.append(kw))
    return logged


@pytest.fixture(autouse=True)
def fixed_models(monkeypatch):
    monkeypatch.setattr(client, "model_name", lambda tier: "gemini-2.5-flash")


def call(model, waits=None, **kw):
    return call_llm("small", ["hi"], flow="chat", node="t", max_tokens=100, model=model,
                    sleep=(waits.append if waits is not None else lambda s: None), **kw)


def test_good_call_returns_text_tokens_cost_and_logs_one_ok_run(runs):
    r = call(FakeModel(reply("  ready \n", i=1000, o=200)))
    assert r.text == "ready"
    assert (r.input_tokens, r.output_tokens) == (1000, 200)
    assert r.cost_usd == pytest.approx(0.0008)   # 1000*0.30/1e6 + 200*2.50/1e6 = 0.0003 + 0.0005
    assert len(runs) == 1 and runs[0]["status"] == "ok" and runs[0]["flow"] == "chat" and runs[0]["node"] == "t"


def test_content_given_as_parts_is_joined(runs):
    m = FakeModel(AIMessage(content=[{"type": "text", "text": "a"}, "b"]))
    assert call(m).text == "ab"


def test_rate_limit_is_retried_then_succeeds(runs):
    waits = []
    m = FakeModel(RuntimeError("429 RESOURCE_EXHAUSTED"), RuntimeError("503 overloaded"), reply())
    assert call(m, waits).text == "hello"
    assert m.calls == 3 and len(waits) == 2
    assert 1.0 <= waits[0] <= 1.5 and 3.0 <= waits[1] <= 3.5   # backoff grows
    assert [r["status"] for r in runs] == ["ok"]   # only the final outcome is logged


def test_rate_limit_that_never_clears_gives_a_friendly_error_and_is_logged(runs):
    m = FakeModel(*[RuntimeError("429 quota exceeded")] * 4)
    with pytest.raises(LLMBusy) as e:
        call(m)
    assert "try again in a minute" in str(e.value) and "429" not in str(e.value)
    assert m.calls == 4   # first try + 3 retries
    assert [r["status"] for r in runs] == ["rate_limited"]


def test_other_errors_are_not_retried_and_hide_the_details(runs):
    m = FakeModel(ValueError("bad api key AIzaSECRET"))
    with pytest.raises(LLMFailed) as e:
        call(m)
    assert "AIzaSECRET" not in str(e.value)
    assert m.calls == 1 and runs[0]["status"] == "error" and runs[0]["error_code"] == "ValueError"


def test_max_tokens_is_required_to_be_positive():
    with pytest.raises(ValueError):
        call_llm("small", ["hi"], flow="chat", node="t", max_tokens=0, model=FakeModel())


def test_cost_cached_tokens_are_cheaper_and_unknown_models_cost_the_most():
    full = estimate_cost_usd("gemini-2.5-flash", 1_000_000, 0)
    cached = estimate_cost_usd("gemini-2.5-flash", 1_000_000, 0, cached_tokens=1_000_000)
    assert full == pytest.approx(0.30) and cached == pytest.approx(0.03)
    assert estimate_cost_usd("gemini-future", 0, 1_000_000) == pytest.approx(2.50)   # worst known price
    assert estimate_cost_usd("gemini-2.5-flash", 100, 0, cached_tokens=999) == pytest.approx(100 * 0.03 / 1e6)  # clamped


@pytest.mark.parametrize("text,expected", [
    ("429 Too Many Requests", True), ("RESOURCE_EXHAUSTED", True), ("503 Service Unavailable", True),
    ("400 invalid argument", False), ("API key not valid", False),
])
def test_rate_limit_detection(text, expected):
    assert is_rate_limit(RuntimeError(text)) is expected
