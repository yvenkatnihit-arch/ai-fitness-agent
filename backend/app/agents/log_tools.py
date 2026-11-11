"""The meal logging tool (Step 8.5, D-109). Scope PROPOSE: it saves a pending proposal and reports it; nothing is logged until the user approves.

The model supplies only food keys (from search_foods), an amount and a unit. Grams, calories and macros are worked out by code
(app.workflows.meal_log_proposal), and the user sees exactly what will be saved before anything is written."""

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
from app.schemas.meals import MAX_ITEMS_PER_MEAL, Slot
from app.workflows import meal_log_proposal as proposal


class LogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_key: str = Field(min_length=1, max_length=80, description="the `key` of a food returned by search_foods")
    # Found in a real run: the model sometimes writes "amount" for "quantity". Accepting it is harmless; the value is still validated.
    quantity: float = Field(gt=0, le=3000, validation_alias=AliasChoices("quantity", "amount"),
                            description="how many units as a number, e.g. 2 for 2 rotis, 150 for 150 g")
    unit: str = Field(min_length=1, max_length=20, description="'g' or one of the food's units returned by search_foods, e.g. piece, katori")


class LogMealArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: Slot = Field(description="which meal: breakfast, mid_morning, lunch, evening_snack, dinner or other")
    day: Literal["today", "yesterday"] = "today"
    items: list[LogItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)


def _propose(ctx: RunContext, args: LogMealArgs) -> dict[str, Any]:
    try:
        return proposal.propose(ctx.user_id, args.slot, args.day, [item.model_dump() for item in args.items])
    except proposal.MealLogError as error:
        return {"error": str(error)}


PROPOSE_MEAL_LOG = Tool(
    "propose_meal_log", "Prepare a meal log for the user to confirm. Nothing is saved until they approve it. Give the meal, the day and each food "
    "with an amount and a unit. Each item is an object with exactly food_key, quantity (a number) and unit.", LogMealArgs, _propose, scope="propose")
