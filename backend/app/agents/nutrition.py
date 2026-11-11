"""The nutrition specialist (Step 7.2, D-074): answers food questions from our foods table only."""

from uuid import UUID

from app.agents.context import RunContext
from app.agents.food_tools import FIND_FOODS, PORTION_NUTRITION, SEARCH_FOODS
from app.agents.gemini_model import gemini_model
from app.agents.runner import Model, RunResult, build_specialist
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry

NUTRITION_SPEC = SpecialistSpec(
    name="nutrition",
    system_prompt=(
        "You are the nutrition specialist of an Indian fitness coach app. You answer questions about foods and dishes. "
        "ALWAYS call search_foods first and answer ONLY from what it returns; if it finds nothing, say the food is not in "
        "our database yet. Never invent a food or a number, and never do arithmetic: do NOT scale, multiply, add or divide anything. "
        "For a plain question quote the per-100 g values and unit weights exactly as search_foods returned them. For ANY question "
        "about an amount (150 g, 3 rotis, a katori, a glass) call portion_nutrition with the food's key, the quantity and the unit "
        "('g' or a unit from search_foods) and quote its numbers exactly; if it reports an error, use the units it lists, or say what "
        "is missing. For a question that asks for foods ranked or suggested by a nutrient (which foods are high in protein, low calorie "
        "options, vegetarian protein sources), call find_foods and list what it returns in the SAME order with its numbers exactly; its "
        "values are per 100 g, so say so, and never re-sort, add or invent foods. For snack questions use kind=snacks; for a food group (fruits, vegetables, dairy, nuts_seeds, pulses, grains, beverages, supplements, desserts) use that kind; for ready-to-eat dishes "
        "use kind=dishes; if the result has a note about dry ingredients, mention it in a few words. Keep answers to two or three short sentences "
        "(a short list for rankings). You do not give medical advice."
    ),
    tools=frozenset({"search_foods", "portion_nutrition", "find_foods"}),
    tier="small",
    max_tokens_per_call=400,
    max_steps=5,            # search, then one portion calculation per food asked about (or one ranking), then the answer
    token_budget=6_000,
    timeout_s=30.0,
)


def nutrition_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SEARCH_FOODS)
    registry.register(PORTION_NUTRITION)
    registry.register(FIND_FOODS)
    return registry


def run_nutrition(question: str, user_id: UUID, *, model: Model | None = None) -> RunResult:
    """Spawn a nutrition specialist for this one question; it is discarded when this returns."""
    registry = nutrition_registry()
    brain = model or gemini_model(NUTRITION_SPEC, registry, user_id=user_id, flow="chat")
    return build_specialist(NUTRITION_SPEC, registry, brain).run(question, RunContext(user_id))
