"""Identity for one agent run. Built by the harness from the verified login, never from model output."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RunContext:
    user_id: UUID
