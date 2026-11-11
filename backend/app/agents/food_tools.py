"""Food tools for specialists (Step 7.2). Read-only; run as the user under RLS; numbers come from the database, never the model."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
from app.calc.food_rank import Kind, SortBy, rank_foods, ranking_pool
from app.calc.meal_pool import ALLOWED_DIET_CLASSES
from app.calc.portions import PortionError, grams_for, nutrition_for
from app.db import foods as repo
from app.db import meal_foods
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


class FindFoodsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sort_by: SortBy = Field(description="most_protein, least_calories, or most_protein_per_calorie")
    kind: Kind = Field(default="any", description="dishes (cooked dishes), ingredients (plain foods), snacks (fruit, nuts, dairy, eggs, snack dishes) or any")
    diet: Literal["vegan", "vegetarian", "eggetarian", "non_vegetarian"] | None = Field(
        default=None, description="show foods for this diet instead of the user's own (only when the user asks about another diet)")
    min_protein_g: float | None = Field(default=None, ge=0, le=100, description="only foods with at least this much protein per 100 g")
    max_kcal: float | None = Field(default=None, ge=0, le=900, description="only foods with at most this many calories per 100 g")
    limit: int = Field(default=5, ge=1, le=8)


def _find(ctx: RunContext, args: FindFoodsArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        foods = meal_foods.list_pool_foods(conn)
        profile = meal_foods.read_meal_profile(conn)
    diet = args.diet or (profile.diet_type if profile else None)
    if diet not in ALLOWED_DIET_CLASSES:
        return {"error": "We do not know this user's diet yet. Ask which diet they follow (vegan, vegetarian, eggetarian or non-vegetarian)."}
    own = profile is not None and args.diet in (None, profile.diet_type)
    pool = ranking_pool(foods, diet, profile.dislikes if profile else (), profile.cuisines if own else None)   # a "what about vegan" question is not narrowed by cuisine
    ranked = rank_foods(pool, args.sort_by, args.kind, args.min_protein_g, args.max_kcal, args.limit)
    note = ("Raw or dry ingredients (flours, dals, nuts, seeds) show more protein and calories per 100 g than cooked dishes, because cooking adds water. "
            "Compare like with like, and say when a value is for a dry ingredient.")
    return {"diet": diet, "values_are": "per 100 g", **({"note": note} if args.kind in ("any", "ingredients", "snacks") else {}), "foods": [{
        "key": f.key, "name": f.name, "kcal": f.kcal, "protein_g": f.protein_g, "carbs_g": f.carbs_g, "fat_g": f.fat_g,
        "units": [{"unit": u, "grams": g} for u, g in f.units], "verified": f.review_status == "ready"} for f in ranked]}


FIND_FOODS = Tool(
    "find_foods", "List foods ranked by protein, calories or protein per calorie, for the user's diet (or another diet they ask about). Values are per 100 g. "
    "Use it for questions like which foods are high in protein or low in calories.", FindFoodsArgs, _find, scope="read")
