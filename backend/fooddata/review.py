"""The result of reviewing one food (a source mapping or one of our recipes)."""

from dataclasses import dataclass, field

from fooddata.checks import Issue
from fooddata.records import FoodRecord

STATUSES = ("ready", "review", "blocked", "gap")


@dataclass
class Reviewed:
    row: dict
    status: str = "ready"
    food: FoodRecord | None = None
    carbs_g: float | None = None
    carbs_quality: str | None = None
    issues: list[Issue] = field(default_factory=list)

    def add(self, *issues: Issue) -> None:
        self.issues.extend(issues)
