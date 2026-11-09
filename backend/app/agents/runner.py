"""The specialist factory and the harness loop (Step 7.1, D-063).

`build_specialist(spec, registry, model)` makes a fresh, stateless agent for ONE task. `Specialist.run` is the loop, and the
HARNESS (this file), not the model, enforces the rules: allowlist, strict argument checks, identity injection, and limits on
steps, tokens and time. The model is any callable that takes the messages so far and returns a `Turn`; a real Gemini adapter
comes in 7.2 and tests use a scripted fake. Everything the run held is dropped when `run` returns.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.agents.context import RunContext
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry

Status = Literal["ok", "step_limit", "token_budget", "timeout"]


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Turn:
    """One model reply: either a tool call or a final answer, plus the tokens that turn used."""
    call: ToolCall | None = None
    final: str | None = None
    tokens: int = 0


Model = Callable[[list[dict[str, Any]]], Turn]


@dataclass(frozen=True)
class ToolRecord:
    name: str
    outcome: Literal["ok", "refused", "bad_args", "error"]
    detail: str = ""


@dataclass
class RunResult:
    specialist: str
    status: Status
    answer: str | None
    steps: int
    tokens: int
    tools: list[ToolRecord] = field(default_factory=list)   # what the "How this was made" panel and agent_runs show


class Specialist:
    def __init__(self, spec: SpecialistSpec, registry: ToolRegistry, model: Model, clock: Callable[[], float]) -> None:
        self._spec, self._registry, self._model, self._clock = spec, registry, model, clock

    def run(self, task: str, ctx: RunContext) -> RunResult:
        spec = self._spec
        messages: list[dict[str, Any]] = [{"role": "system", "content": spec.system_prompt}, {"role": "user", "content": task}]
        result = RunResult(spec.name, "ok", None, 0, 0)
        deadline = self._clock() + spec.timeout_s
        for _ in range(spec.max_steps):
            if self._clock() > deadline:
                result.status = "timeout"
                return result
            turn = self._model(list(messages))
            result.steps += 1
            result.tokens += turn.tokens
            if result.tokens > spec.token_budget:
                result.status = "token_budget"
                return result
            if turn.final is not None:
                result.answer = turn.final
                return result
            if turn.call is None:   # neither a call nor an answer: treat as an empty answer rather than loop forever
                result.answer = ""
                return result
            observation = self._use_tool(turn.call, ctx, result)
            messages.append({"role": "assistant", "tool_call": {"name": turn.call.name, "args": turn.call.args}})
            messages.append({"role": "tool", "name": turn.call.name, "content": observation})
        result.status = "step_limit"
        return result

    def _use_tool(self, call: ToolCall, ctx: RunContext, result: RunResult) -> dict[str, Any]:
        def record(outcome: Literal["ok", "refused", "bad_args", "error"], detail: str = "") -> None:
            result.tools.append(ToolRecord(call.name, outcome, detail))

        tool = self._registry.get(call.name)
        if call.name not in self._spec.tools or tool is None:     # allowlist first, whatever the registry holds
            record("refused", "not on this specialist's allowlist")
            return {"error": f"You may not use {call.name}."}
        try:
            args = tool.args_model.model_validate(call.args)       # strict: unknown fields (user_id too) are errors
        except ValidationError as e:
            record("bad_args", f"{len(e.errors())} problem(s)")
            return {"error": "Those arguments are not valid.", "problems": [x["msg"] for x in e.errors()][:5]}
        try:
            output = tool.run(ctx, args)                           # identity comes from ctx, never from the model
        except Exception as e:  # noqa: BLE001 - a failing tool must not crash the run
            record("error", type(e).__name__)
            return {"error": "That tool failed."}
        record("ok")
        return output


def build_specialist(spec: SpecialistSpec, registry: ToolRegistry, model: Model,
                     clock: Callable[[], float] = time.monotonic) -> Specialist:
    """The factory: check the spec, return a fresh agent for one task. Nothing is shared between two builds."""
    spec.check(registry)
    return Specialist(spec, registry, model, clock)
