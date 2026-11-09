"""Evaluate the nutrition specialist with real Gemini calls and the real foods table (Step 7.7c, D-082).

All checks are programmatic: it searched first, every number in the answer comes from a tool result or the question (no
arithmetic, no invented values), an empty search is answered honestly, and the run stayed within its limits. The tool is wrapped so
its outputs are captured; the replies are cached (foods are static reference data).
"""

import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.agents.composer import numbers_in
from app.agents.context import RunContext
from app.agents.gemini_model import gemini_model
from app.agents.nutrition import NUTRITION_SPEC, nutrition_registry
from app.agents.runner import build_specialist
from app.agents.tools import Tool, ToolRegistry
from app.llm.client import LLMResult, call_llm, model_name
from evals import cache as cache_mod
from evals.nutrition_cases import CASES

MAX_CALLS = 60   # model calls (a case takes 2 to 3)
ABSENT_WORDS = ("not in our database", "isn't in our database", "is not in our database", "don't have", "do not have", "couldn't find", "could not find",
                "not found", "no information", "not available")


@dataclass(frozen=True)
class NutritionResult:
    question: str
    kind: str
    answer: str
    status: str
    searched_first: bool
    used_portion_tool: bool          # portion_nutrition ran successfully
    found_any: bool                  # did any search return foods
    ungrounded: tuple[str, ...]      # numbers in the answer that are in no tool output and not in the question
    admits_absence: bool
    steps: int
    tokens: int
    cost_usd: float

    @property
    def honest_when_absent(self) -> bool:
        return self.found_any or (self.admits_absence and not numbers_in(self.answer))

    @property
    def passed(self) -> bool:
        # An amount question about a food we have must be answered with the calculator's numbers, not by the model.
        amount_ok = self.kind != "amount" or not self.found_any or self.used_portion_tool
        return self.status == "ok" and self.searched_first and not self.ungrounded and self.honest_when_absent and amount_ok


def _wrapped_registry(outputs: list[dict]) -> ToolRegistry:
    """The specialist's real tools, but each records what it returned, so the answer can be checked against it."""
    registry = ToolRegistry()
    for tool in nutrition_registry().all():
        def run(ctx, args, _tool=tool):
            out = _tool.run(ctx, args)
            outputs.append(out)
            return out
        registry.register(Tool(tool.name, tool.description, tool.args_model, run, tool.scope))
    return registry


def run_one(question: str, kind: str, call) -> dict:
    outputs: list[dict] = []
    spent = {"tokens": 0, "cost": 0.0, "calls": 0}

    def counting_call(*a, **kw):
        r = call(*a, **kw)
        spent["tokens"] += r.input_tokens + r.output_tokens
        spent["cost"] += r.cost_usd
        spent["calls"] += 1
        return r
    registry = _wrapped_registry(outputs)
    brain = gemini_model(NUTRITION_SPEC, registry, user_id=None, flow="eval", call=counting_call)
    run = build_specialist(NUTRITION_SPEC, registry, brain).run(question, RunContext(uuid4()))   # random user: foods are readable by anyone signed in
    return {"answer": run.answer or "", "status": run.status, "steps": run.steps,
            "tools": [[t.name, t.outcome] for t in run.tools], "outputs": outputs, **spent}


def score(question: str, kind: str, rec: dict) -> NutritionResult:
    outputs = rec["outputs"]
    allowed = numbers_in(question).union(*(numbers_in(json.dumps(o)) for o in outputs)) if outputs else numbers_in(question)
    found = any(o.get("foods") for o in outputs)
    answer = rec["answer"]
    return NutritionResult(
        question, kind, answer, rec["status"], bool(rec["tools"]) and rec["tools"][0] == ["search_foods", "ok"],
        any(t == ["portion_nutrition", "ok"] for t in rec["tools"]), found, tuple(sorted(numbers_in(answer) - allowed)), any(w in answer.lower() for w in ABSENT_WORDS), rec["steps"], rec["tokens"], rec["cost"])


def run_nutrition_eval(call: Callable[..., LLMResult] = call_llm, *, use_cache: bool = True, max_calls: int = MAX_CALLS, cases=CASES) -> list[NutritionResult]:
    cache = cache_mod.Cache("nutrition", use_cache)
    used, out = 0, []
    for question, kind in cases:
        k = cache_mod.key(model_name("small"), NUTRITION_SPEC.system_prompt, question)
        rec = cache.get(k)
        if rec is None:
            if used >= max_calls:
                raise RuntimeError(f"eval budget reached: {max_calls} real model calls in one run")
            rec = run_one(question, kind, call)
            used += rec["calls"]
            cache.put(k, rec)
        out.append(score(question, kind, rec))
    cache.save()
    return out


def summarize(results: list[NutritionResult]) -> dict:
    n = len(results) or 1
    absent = [r for r in results if not r.found_any]
    return {
        "cases": len(results),
        "pass_rate": sum(r.passed for r in results) / n,
        "searched_first_rate": sum(r.searched_first for r in results) / n,
        "ungrounded_number_rate": sum(bool(r.ungrounded) for r in results) / n,
        "amount_used_tool_rate": sum(r.used_portion_tool for r in results if r.kind == "amount" and r.found_any) / max(1, sum(r.kind == "amount" and r.found_any for r in results)),
        "amount_calculated_rate": sum(bool(r.ungrounded) for r in results if r.kind == "amount") / max(1, sum(r.kind == "amount" for r in results)),
        "absent_cases": len(absent),
        "honest_when_absent_rate": sum(r.honest_when_absent for r in absent) / len(absent) if absent else 1.0,
        "failed_run_rate": sum(r.status != "ok" for r in results) / n,
        "avg_steps": statistics.mean(r.steps for r in results) if results else 0,
        "avg_tokens": statistics.mean(r.tokens for r in results) if results else 0,
        "total_cost_usd": sum(r.cost_usd for r in results),
    }
