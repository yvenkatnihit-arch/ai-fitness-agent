"""The menu of specialists the router may choose from (Step 7.3, D-075). Written and reviewed by us; the model never adds to it."""

from collections.abc import Callable
from dataclasses import dataclass

from app.agents.exercise_coach import EXERCISE_SPEC, WHEN as EXERCISE_WHEN, exercise_registry
from app.agents.meal_logger import MEAL_LOGGER_SPEC, WHEN as MEAL_LOGGER_WHEN, meal_logger_registry
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
            "questions about a food or dish: calories, protein, carbs, fat, household portion weights; and suggestions or rankings of foods by "
            "a nutrient (high-protein foods, low-calorie options, vegetarian protein sources)"),
        MY_PLAN_SPEC.name: MenuEntry(MY_PLAN_SPEC, my_plan_registry, MY_PLAN_WHEN),
        EXERCISE_SPEC.name: MenuEntry(EXERCISE_SPEC, exercise_registry, EXERCISE_WHEN),
        MEAL_LOGGER_SPEC.name: MenuEntry(MEAL_LOGGER_SPEC, meal_logger_registry, MEAL_LOGGER_WHEN),
    }
