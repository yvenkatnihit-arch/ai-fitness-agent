"""Food tools for specialists (Step 7.2). Read-only; run as the user under RLS; numbers come from the database, never the model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
from app.calc.portions import PortionError, grams_for, nutrition_for
from app.db import foods as repo
from app.db.transactions import user_transaction


class SearchFoodsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=60, description="food name or local name, e.g. paneer, toor dal")
    limit: int = Field(default=3, ge=1, le=5)


def _search(ctx: RunContext, args: SearchFoodsArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        rows = repo.search_foods(conn, args.query.strip(), args.limit)
    return {"foods": [{
        "key": r["key"], "name": r["name"], "diet": r["diet_class"], "per_100g": {
            # the database returns Decimal, which cannot go to the model as JSON
            "kcal": float(r["kcal"]), "protein_g": float(r["protein_g"]), "carbs_g": float(r["carbs_g"]), "fat_g": float(r["fat_g"])},
        "units": [{"unit": u["unit"], "grams": float(u["grams"])} for u in r["units"]],
    } for r in rows]}


class PortionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_key: str = Field(min_length=1, max_length=80, description="the `key` of a food returned by search_foods")
    quantity: float = Field(gt=0, le=3000, description="how many units, e.g. 150 for 150 g, or 3 for 3 pieces")
    unit: str = Field(default="g", min_length=1, max_length=20, description="'g' or one of the food's units returned by search_foods, e.g. piece, katori")


def _portion(ctx: RunContext, args: PortionArgs) -> dict[str, Any]:
    """Grams and nutrition for an amount. Pure code (app.calc.portions): the model never multiplies."""
    with user_transaction(ctx.user_id) as conn:
        food = repo.get_food_for_portion(conn, args.food_key)
    if food is None:
        return {"error": "Unknown food key. Use a key returned by search_foods."}
    try:
        grams = grams_for(args.quantity, args.unit, food.unit_grams)
    except PortionError as e:
        return {"error": str(e), "available_units": ["g", *sorted(food.unit_grams)]}
    n = nutrition_for(grams, food.per_100g)
    return {"food": food.name, "amount": f"{args.quantity:g} {args.unit}", "grams": grams,
            "kcal": n.kcal, "protein_g": n.protein_g, "carbs_g": n.carbs_g, "fat_g": n.fat_g}


PORTION_NUTRITION = Tool(
    "portion_nutrition", "Calculate the grams, calories and macros for an AMOUNT of one food (for example 150 g, or 3 pieces). "
    "Use it for any question about a quantity; never calculate yourself.", PortionArgs, _portion, scope="read")

SEARCH_FOODS = Tool(
    "search_foods", "Look up foods in our database by name. Returns calories and macros per 100 g and household units (grams each).",
    SearchFoodsArgs, _search, scope="read")
