"""The menu of specialists the router may choose from (Step 7.3, D-075). Written and reviewed by us; the model never adds to it."""

from collections.abc import Callable
from dataclasses import dataclass

from app.agents.my_plan import MY_PLAN_SPEC, WHEN as MY_PLAN_WHEN, my_plan_registry
from app.agents.nutrition import NUTRITION_SPEC, nutrition_registry
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry


@dataclass(frozen=True)
class MenuEntry:
    spec: SpecialistSpec
    registry: Callable[[], ToolRegistry]
    when: str   # one line for the router: when to pick this specialist


Menu = dict[str, MenuEntry]


def default_menu() -> Menu:
    return {
        NUTRITION_SPEC.name: MenuEntry(
            NUTRITION_SPEC, nutrition_registry,
            "questions about a food or dish: calories, protein, carbs, fat, household portion weights"),
        MY_PLAN_SPEC.name: MenuEntry(MY_PLAN_SPEC, my_plan_registry, MY_PLAN_WHEN),
    }
