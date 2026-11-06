"""Meal logging from the form (no LLM: grams and nutrition are computed in code from our food data)."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.calc.portions import Nutrition, PortionError, grams_for, nutrition_for, total
from app.core.auth import CurrentUser, get_current_user
from app.core.time import india_today
from app.db import meals as repo
from app.db import user_transaction
from app.schemas.meals import LOG_BACKFILL_DAYS, DayOut, MealIn, MealOut, NutritionOut

router = APIRouter(prefix="/meals", tags=["meals"])


def check_log_date(day: date, today: date) -> None:
    if day > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You can't log meals for a future date.")
    if day < today - timedelta(days=LOG_BACKFILL_DAYS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"You can log meals for today and the last {LOG_BACKFILL_DAYS} days.")


def _nutrition(d: dict) -> Nutrition:
    return Nutrition(d["kcal"], d["protein_g"], d["carbs_g"], d["fat_g"])


def to_meal_out(meal: dict) -> MealOut:
    return MealOut(**meal, totals=NutritionOut(**total([_nutrition(i) for i in meal["items"]]).__dict__))


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
def log_meal(body: MealIn, user: CurrentUser = Depends(get_current_user)) -> MealOut:
    """Save one meal. The client sends foods and amounts only; the backend computes grams and nutrition."""
    day = body.logged_on or india_today()
    check_log_date(day, india_today())
    with user_transaction(user.id) as conn:
        foods = repo.foods_for_logging(conn, sorted({i.food_id for i in body.items}))
        new_items = []
        for number, item in enumerate(body.items, start=1):
            food = foods.get(item.food_id)
            if food is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Item {number}: food not found.")
            try:
                grams = grams_for(item.quantity, item.unit, food.unit_grams)
            except PortionError as error:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Item {number} ({food.name}): {error}.")
            new_items.append(repo.NewItem(food.id, item.quantity, item.unit, grams, nutrition_for(grams, food.per_100g)))
        meal_id = repo.insert_meal(conn, day, body.slot, "form", new_items)
        meal = next(m for m in repo.meals_on(conn, day) if m["id"] == meal_id)
    return to_meal_out(meal)


@router.get("", response_model=DayOut)
def day_log(day: date | None = None, user: CurrentUser = Depends(get_current_user)) -> DayOut:
    """One day's meals and totals (default: today, India time). Totals are summed in code."""
    day = day or india_today()
    with user_transaction(user.id) as conn:
        meals = [to_meal_out(m) for m in repo.meals_on(conn, day)]
    day_total = total([Nutrition(**m.totals.model_dump()) for m in meals])
    return DayOut(logged_on=day, meals=meals, totals=NutritionOut(**day_total.__dict__))


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(meal_id: UUID, user: CurrentUser = Depends(get_current_user)) -> Response:
    with user_transaction(user.id) as conn:
        deleted = repo.delete_meal(conn, meal_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meal not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
