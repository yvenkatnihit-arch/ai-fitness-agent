"""The nutrition specialist (Step 7.2, D-074): answers food questions from our foods table only."""

from uuid import UUID

from app.agents.context import RunContext
from app.agents.food_tools import SEARCH_FOODS
from app.agents.gemini_model import gemini_model
from app.agents.runner import Model, RunResult, build_specialist
from app.agents.spec import SpecialistSpec
from app.agents.tools import ToolRegistry

NUTRITION_SPEC = SpecialistSpec(
    name="nutrition",
    system_prompt=(
        "You are the nutrition specialist of an Indian fitness coach app. You answer questions about foods and dishes. "
        "ALWAYS call search_foods first and answer ONLY from what it returns; if it finds nothing, say the food is not in "
        "our database yet. Never invent a food or a number, and never do arithmetic: if the user asks about an amount, give "
        "the per-100 g values and the household unit weights as returned and let the app calculate. Keep answers to "
        "two or three short sentences. You do not give medical advice."
    ),
    tools=frozenset({"search_foods"}),
    tier="small",
    max_tokens_per_call=400,
    max_steps=3,
    token_budget=4_000,
    timeout_s=30.0,
)


def nutrition_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SEARCH_FOODS)
    return registry


def run_nutrition(question: str, user_id: UUID, *, model: Model | None = None) -> RunResult:
    """Spawn a nutrition specialist for this one question; it is discarded when this returns."""
    registry = nutrition_registry()
    brain = model or gemini_model(NUTRITION_SPEC, registry, user_id=user_id, flow="chat")
    return build_specialist(NUTRITION_SPEC, registry, brain).run(question, RunContext(user_id))
