"""Food tools for specialists (Step 7.2). Read-only; run as the user under RLS; numbers come from the database, never the model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
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


SEARCH_FOODS = Tool(
    "search_foods", "Look up foods in our database by name. Returns calories and macros per 100 g and household units (grams each).",
    SearchFoodsArgs, _search, scope="read")
