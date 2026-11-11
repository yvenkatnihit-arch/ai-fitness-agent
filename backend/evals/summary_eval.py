"""Evaluate the rolling summary with real model calls (Step 7.11d, D-099). Scores the model's RAW text, before the app's own checks.

Metrics: facts kept (how many of the lasting facts survive), invented-number rate (what the in-app check catches), instruction-copied
rate (an injected phrase carried into the summary), too-long rate, and how often the app's own check accepts the summary.
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass

from app.agents.composer import numbers_in
from app.agents.summarizer import MAX_SUMMARY_CHARS, SYSTEM, check_summary, summarizer_messages
from app.llm.client import LLMResult, call_llm, model_name
from evals import cache as cache_mod
from evals.summary_cases import CASES

MAX_CALLS = 30


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    kept: int
    facts: int
    invented: tuple[str, ...]
    copied: tuple[str, ...]
    traps: int
    accepted: bool             # the app's own check would save it
    tokens: int
    cost_usd: float
    latency_ms: int

    @property
    def passed(self) -> bool:
        return self.kept == self.facts and not self.invented and not self.copied and len(self.summary) <= MAX_SUMMARY_CHARS


def score(old: str, messages, facts, forbidden, text: str, tokens: int, cost: float, ms: int) -> SummaryResult:
    summary = " ".join(text.split())
    allowed = numbers_in(old).union(*(numbers_in(t) for _, t in messages))
    kept = sum(any(w.lower() in summary.lower() for w in group) for group in facts)
    copied = tuple(p for p in forbidden if p.lower() in summary.lower())
    return SummaryResult(summary, kept, len(facts), tuple(sorted(numbers_in(summary) - allowed)), copied, len(forbidden),
                         check_summary(summary, old, messages), tokens, cost, ms)


def run_summary_eval(call: Callable[..., LLMResult] = call_llm, *, use_cache: bool = True, max_calls: int = MAX_CALLS,
                     cases=CASES) -> list[SummaryResult]:
    cache = cache_mod.Cache("summary", use_cache)
    calls, out = 0, []
    for old, messages, facts, forbidden in cases:
        k = cache_mod.key(model_name("small"), SYSTEM, old, repr(messages))
        hit = cache.get(k)
        if hit is None:
            if calls >= max_calls:
                raise RuntimeError(f"eval budget reached: {max_calls} real calls in one run")
            r = call("small", summarizer_messages(old, messages), flow="eval", node="chat_summary", max_tokens=300, user_id=None,
                     temperature=0.0, thinking_budget=0)
            calls += 1
            hit = {"text": r.text.strip(), "tokens": r.input_tokens + r.output_tokens, "cost": r.cost_usd, "ms": r.latency_ms}
            cache.put(k, hit)
        out.append(score(old, messages, facts, forbidden, hit["text"], hit["tokens"], hit["cost"], hit["ms"]))
    cache.save()
    return out


def summarize(results: list[SummaryResult]) -> dict:
    n = len(results) or 1
    traps = [r for r in results if r.traps]
    facts = sum(r.facts for r in results)
    return {
        "cases": len(results),
        "pass_rate": sum(r.passed for r in results) / n,
        "facts_kept_rate": sum(r.kept for r in results) / facts if facts else 1.0,
        "invented_number_rate": sum(bool(r.invented) for r in results) / n,
        "instruction_copied_rate": sum(bool(r.copied) for r in traps) / len(traps) if traps else 0.0,
        "too_long_rate": sum(len(r.summary) > MAX_SUMMARY_CHARS for r in results) / n,
        "accepted_rate": sum(r.accepted for r in results) / n,
        "avg_tokens": statistics.mean(r.tokens for r in results) if results else 0,
        "total_cost_usd": sum(r.cost_usd for r in results),
        "median_latency_ms": statistics.median(r.latency_ms for r in results) if results else 0,
    }
