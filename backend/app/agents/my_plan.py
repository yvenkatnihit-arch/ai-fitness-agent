"""The "my plan" specialist (Step 7.12a, D-103): answers questions about the user's OWN targets, plans and today's log. Read-only."""

from app.agents.plan_tools import GET_MY_MEAL_PLAN_DAY, GET_MY_TARGETS, GET_MY_WORKOUT_DAY, GET_TODAY_LOGGED
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry

MY_PLAN_SPEC = SpecialistSpec(
    name="my_plan",
    system_prompt=(
        "You are the 'my plan' specialist of an Indian fitness coach app. You tell the user what THEIR OWN saved data says: their daily "
        "targets, their approved meal plan or workout plan for a day, and what they logged today. Call the matching tool and answer ONLY "
        "from what it returns. If a tool says there is no plan, targets or log yet, say so and point to the screen it names. Never invent "
        "or guess a number, meal or exercise, and never do arithmetic: quote the numbers exactly as returned. If a number is not in the "
        "tool result (some users must not see calorie or macro numbers), do not give one and do not estimate it. You cannot change "
        "anything: if the user wants a new or different plan, tell them to use the Meal plan or Workout plan screen. You do not give "
        "medical advice. Keep answers short: a few lines, with meals or exercises as a simple list."
    ),
    tools=frozenset({"get_my_targets", "get_my_meal_plan_day", "get_my_workout_day", "get_today_logged"}),
    tier="small",
    max_tokens_per_call=500,
    max_steps=5,            # up to a few tool calls (for example the meal plan and the workout for one day), then the answer
    token_budget=8_000,
    timeout_s=30.0,
)

WHEN = ("questions about the user's OWN saved data: their daily calorie and macro targets, what their meal plan or workout plan says "
        "for a day (today, tomorrow, a weekday), and what they have logged eating today. Only for READING saved data: not for changing, "
        "swapping, creating or logging anything")


def my_plan_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (GET_MY_TARGETS, GET_MY_MEAL_PLAN_DAY, GET_MY_WORKOUT_DAY, GET_TODAY_LOGGED):
        registry.register(tool)
    return registry
