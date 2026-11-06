"""Meal logging requests and responses. Nutrition is always computed by the backend, never sent by the client."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Slot = Literal["breakfast", "mid_morning", "lunch", "evening_snack", "dinner", "other"]
Unit = Literal["g", "katori", "piece", "cup", "glass", "bowl", "plate", "slice", "tbsp", "tsp", "handful"]

MAX_ITEMS_PER_MEAL = 20
LOG_BACKFILL_DAYS = 7  # you can log today and up to a week back


class MealItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_id: int = Field(gt=0)
    quantity: float = Field(gt=0, le=3000)  # 3000 only makes sense for grams; units are capped by grams
    unit: Unit


class MealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. a client-sent "kcal" is refused, not ignored
    slot: Slot
    logged_on: date | None = None  # default: today (India time)
    items: list[MealItemIn] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)


class NutritionOut(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MealItemOut(NutritionOut):
    id: int
    food_id: int
    food_name: str
    quantity: float
    unit: str
    grams: float


class MealOut(BaseModel):
    id: UUID
    logged_on: date
    slot: str
    source: str
    items: list[MealItemOut]
    totals: NutritionOut


class DayOut(BaseModel):
    logged_on: date
    meals: list[MealOut]
    totals: NutritionOut
