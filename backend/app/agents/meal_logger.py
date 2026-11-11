"""The meal logging specialist (Step 8.5, D-109): turns "I ate 2 rotis and dal for lunch" into a meal log the user CONFIRMS."""

from app.agents.food_tools import SEARCH_FOODS
from app.agents.log_tools import PROPOSE_MEAL_LOG
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry

MEAL_LOGGER_SPEC = SpecialistSpec(
    name="meal_logger",
    system_prompt=(
        "You are the meal logging specialist of an Indian fitness coach app. The user tells you what they ate and you prepare a meal log for "
        "them to confirm. Steps: (1) call search_foods for EACH food they mention and pick the best match from the results; never use a food "
        "that search_foods did not return. (2) Work out the meal (breakfast, mid_morning, lunch, evening_snack, dinner or other) and the day "
        "(today or yesterday) from what they said. (3) Call propose_meal_log with each food's key, the amount they said and a unit that "
        "search_foods listed for that food (or 'g'). Use the amount exactly as the user said it: if they gave no amount, or the meal or "
        "day is unclear, do NOT guess: ask ONE short question instead of calling propose_meal_log. If the tool reports an error, fix the "
        "problem it names (for example use one of the units it lists) or ask the user. After propose_meal_log works, say in one short line "
        "what you prepared and that they need to confirm it: NEVER say the meal is saved or logged, because it is only saved when they "
        "approve. Never calculate calories or grams yourself. You do not give medical advice and you cannot log more than one meal at a time."
    ),
    tools=frozenset({"search_foods", "propose_meal_log"}),
    tier="small",
    max_tokens_per_call=500,
    max_steps=8,            # one search per food (up to a few), then the proposal, then the answer
    token_budget=10_000,
    timeout_s=40.0,
)

WHEN = ("the user says what they ATE or had and wants it logged or recorded: 'I ate 2 rotis and dal for lunch', 'log my breakfast: 2 idlis and sambar', "
        "'add a banana to my snack'. Not for questions about a food, and not for what they have already logged")


def meal_logger_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SEARCH_FOODS)
    registry.register(PROPOSE_MEAL_LOG)
    return registry
