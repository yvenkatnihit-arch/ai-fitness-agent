"""Evaluate the router with real model calls (Step 7.7b, D-081). Costs a fraction of a cent; cached; capped.

The router's RAW reply is scored, not the validated one, because `parse_assignments` would hide the model's mistakes (bad JSON,
names that are not on the menu, duplicates). Metrics: exact-match accuracy, nutrition recall, off-topic specificity, raw failure
rates, tokens, cost and latency.
"""

import hashlib
import json
import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.agents.menu import default_menu
from app.agents.router import parse_assignments, router_messages, router_prompt
from app.llm.client import LLMResult, call_llm, model_name
from evals.router_cases import CASES
from evals.router_followups import FOLLOWUPS

CACHE = Path(__file__).with_name("cache") / "router.json"
MAX_CALLS = 80   # a hard cap on real calls in one run


@dataclass(frozen=True)
class RouterResult:
    message: str
    expected: tuple[str, ...]
    got: tuple[str, ...]            # after validation (what the app would do)
    tags: tuple[str, ...]
    valid_json: bool
    off_menu: tuple[str, ...]       # names the model made up (raw)
    duplicates: bool
    tokens: int
    cost_usd: float
    latency_ms: int

    @property
    def passed(self) -> bool:
        if "borderline" in self.tags:
            return self.got in (self.expected, ())
        return self.got == self.expected


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")


def raw_checks(text: str, menu_names: set[str]) -> tuple[bool, tuple[str, ...], bool]:
    """(valid JSON in our shape, names not on the menu, the same name twice)."""
    try:
        data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()))
        items = data["assignments"]
        names = [i["specialist"] for i in items]
    except (ValueError, KeyError, TypeError):
        return False, (), False
    names = [n for n in names if isinstance(n, str)]
    return True, tuple(sorted({n for n in names if n not in menu_names})), len(names) != len(set(names))


def run_router_eval(call: Callable[..., LLMResult] = call_llm, *, use_cache: bool = True, max_calls: int = MAX_CALLS,
                    cases=CASES) -> list[RouterResult]:
    menu = default_menu()
    system = router_prompt(menu)
    cache = _load_cache() if use_cache else {}
    calls, out = 0, []
    for message, expected, tags in cases:
        key = hashlib.sha256(f"{model_name('small')}|{system}|{message}".encode()).hexdigest()
        hit = cache.get(key)
        if hit is None:
            if calls >= max_calls:
                raise RuntimeError(f"eval budget reached: {max_calls} real calls in one run")
            r = call("small", [("system", system), ("human", message)], flow="eval", node="router", max_tokens=200, user_id=None,
                     temperature=0.0, json_mode=True)
            calls += 1
            hit = {"text": r.text, "tokens": r.input_tokens + r.output_tokens, "cost": r.cost_usd, "ms": r.latency_ms}
            cache[key] = hit
        valid, off_menu, dup = raw_checks(hit["text"], set(menu))
        got = tuple(a.specialist for a in parse_assignments(hit["text"], menu))
        out.append(RouterResult(message, expected, got, tags, valid, off_menu, dup, hit["tokens"], hit["cost"], hit["ms"]))
    if use_cache:
        _save_cache(cache)
    return out


def summarize(results: list[RouterResult]) -> dict:
    scored = [r for r in results if "borderline" not in r.tags]
    food = [r for r in scored if r.expected]
    other = [r for r in scored if not r.expected]
    rate = lambda rs, f: sum(f(r) for r in rs) / len(rs) if rs else 1.0   # noqa: E731
    return {
        "cases": len(results), "scored": len(scored), "borderline": len(results) - len(scored),
        "exact_accuracy": rate(scored, lambda r: r.passed),
        "nutrition_recall": rate(food, lambda r: r.passed),
        "off_topic_specificity": rate(other, lambda r: r.passed),
        "borderline_acceptable": rate([r for r in results if "borderline" in r.tags], lambda r: r.passed),
        "invalid_json_rate": rate(results, lambda r: not r.valid_json),
        "off_menu_rate": rate(results, lambda r: bool(r.off_menu)),
        "duplicate_rate": rate(results, lambda r: r.duplicates),
        "avg_tokens": statistics.mean(r.tokens for r in results) if results else 0,
        "total_cost_usd": sum(r.cost_usd for r in results),
        "median_latency_ms": statistics.median(r.latency_ms for r in results) if results else 0,
    }


@dataclass(frozen=True)
class FollowupResult:
    message: str
    expected: tuple[str, ...]
    got: tuple[str, ...]
    tags: tuple[str, ...]
    task: str                  # the task the router wrote for the first assignment ("" when none)
    resolved: bool             # the task names what the follow-up referred to (borderline cases: always True)
    tokens: int
    cost_usd: float
    latency_ms: int

    @property
    def route_ok(self) -> bool:
        return self.got in (self.expected, ()) if "borderline" in self.tags else self.got == self.expected


def run_followup_eval(call: Callable[..., LLMResult] = call_llm, *, use_cache: bool = True, max_calls: int = MAX_CALLS,
                      cases=FOLLOWUPS) -> list[FollowupResult]:
    menu = default_menu()
    cache = _load_cache() if use_cache else {}
    calls, out = 0, []
    for summary, history, message, expected, tags, mentions in cases:
        messages = router_messages(menu, message, history, summary)      # exactly what the app sends
        key = hashlib.sha256(f"{model_name('small')}|{json.dumps(messages)}".encode()).hexdigest()
        hit = cache.get(key)
        if hit is None:
            if calls >= max_calls:
                raise RuntimeError(f"eval budget reached: {max_calls} real calls in one run")
            r = call("small", messages, flow="eval", node="router", max_tokens=200, user_id=None, temperature=0.0, json_mode=True)
            calls += 1
            hit = {"text": r.text, "tokens": r.input_tokens + r.output_tokens, "cost": r.cost_usd, "ms": r.latency_ms}
            cache[key] = hit
        assignments = parse_assignments(hit["text"], menu)
        task = assignments[0].task if assignments else ""
        resolved = "borderline" in tags or not mentions or any(w in task.lower() for w in mentions)
        out.append(FollowupResult(message, expected, tuple(a.specialist for a in assignments), tags, task, resolved,
                                  hit["tokens"], hit["cost"], hit["ms"]))
    if use_cache:
        _save_cache(cache)
    return out


def summarize_followups(results: list[FollowupResult]) -> dict:
    scored = [r for r in results if "borderline" not in r.tags]
    rate = lambda rs, f: sum(f(r) for r in rs) / len(rs) if rs else 1.0   # noqa: E731
    return {
        "followup_cases": len(results),
        "followup_route_accuracy": rate(scored, lambda r: r.route_ok),
        "followup_resolved_rate": rate([r for r in scored if r.expected], lambda r: r.resolved),
        "followup_borderline_ok": rate([r for r in results if "borderline" in r.tags], lambda r: r.route_ok),
        "followup_cost_usd": sum(r.cost_usd for r in results),
    }
