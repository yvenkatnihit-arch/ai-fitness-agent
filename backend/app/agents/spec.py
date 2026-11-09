"""A specialist is a spec, not a process (Step 7.1, D-063). Written and reviewed by us; the model never writes one."""

from dataclasses import dataclass

from app.agents.tools import ToolRegistry
from app.llm.client import Tier

MAX_STEPS_CEILING = 10          # no spec may ask for more model turns than this
MAX_TOKENS_CEILING = 20_000     # total tokens one run may use, all turns together


@dataclass(frozen=True)
class SpecialistSpec:
    name: str
    system_prompt: str
    tools: frozenset[str]                # the allowlist: the ONLY tools this specialist may call
    tier: Tier = "small"                 # mid only for plan generation and adjustments (CLAUDE.md cost rules)
    max_tokens_per_call: int = 600
    max_steps: int = 4                   # model turns, including the final answer
    token_budget: int = 6_000
    timeout_s: float = 30.0

    def check(self, registry: ToolRegistry) -> None:
        """Refuse a bad spec before anything runs."""
        if not self.name or not self.system_prompt.strip():
            raise ValueError("a specialist needs a name and a system prompt")
        unknown = self.tools - registry.names()
        if unknown:
            raise ValueError(f"{self.name}: unknown tools {sorted(unknown)}")
        if not 1 <= self.max_steps <= MAX_STEPS_CEILING:
            raise ValueError(f"{self.name}: max_steps must be 1 to {MAX_STEPS_CEILING}")
        if not 0 < self.token_budget <= MAX_TOKENS_CEILING or self.max_tokens_per_call <= 0:
            raise ValueError(f"{self.name}: token limits must be positive and within {MAX_TOKENS_CEILING}")
        if self.timeout_s <= 0:
            raise ValueError(f"{self.name}: timeout must be positive")
