from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.db import foods as repo
from app.db import user_transaction
from app.schemas.foods import FoodOut, to_food_out

router = APIRouter(prefix="/foods", tags=["foods"])

MAX_RESULTS = 25


@router.get("/search", response_model=list[FoodOut])
def search(
    q: Annotated[str, Query(min_length=2, max_length=60, description="Food name or local name, e.g. chawal")],
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS)] = 10,
    user: CurrentUser = Depends(get_current_user),
) -> list[FoodOut]:
    """Search our food database by name or local name (no LLM: a database lookup, best match first)."""
    with user_transaction(user.id) as conn:
        rows = repo.search_foods(conn, q.strip(), limit)
    return [to_food_out(row) for row in rows]
