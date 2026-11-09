"""The tool registry (Step 7.1, D-063). Every tool a specialist may call is registered here, once.

A tool is a typed function: Pydantic arguments in, a JSON-friendly dict out. Two scopes only:
- "read": looks something up (food search, a calculator).
- "propose": creates a PENDING proposal. No tool ever applies a change; only the user's approval does.
The harness gives each tool the run's `RunContext` (who the user is). The model can never set it:
a tool's argument model may not have a user field, and extra arguments are refused.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from app.agents.context import RunContext

Scope = Literal["read", "propose"]
FORBIDDEN_ARG_NAMES = frozenset({"user_id", "user", "uid", "owner_id"})


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    run: Callable[[RunContext, Any], dict[str, Any]]
    scope: Scope = "read"

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError(f"bad tool name: {self.name!r}")
        if self.scope not in ("read", "propose"):
            raise ValueError("a tool's scope is read or propose")
        if self.args_model.model_config.get("extra") != "forbid":
            raise ValueError(f"{self.name}: the argument model must set extra='forbid'")
        bad = FORBIDDEN_ARG_NAMES & set(self.args_model.model_fields)
        if bad:
            raise ValueError(f"{self.name}: the model may not supply {sorted(bad)}; the harness injects identity")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> frozenset[str]:
        return frozenset(self._tools)
