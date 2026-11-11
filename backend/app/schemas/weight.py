"""Weight log requests and responses (Step 8.6, D-112)."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class WeightIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight_kg: float = Field(ge=30, le=300)          # the same limits as the database (D-019)
    measured_on: date | None = None                  # default: today (India time)


class PointOut(BaseModel):
    date: date
    weight_kg: float


class WeightOut(BaseModel):
    numbers_hidden: bool                             # eating-disorder history: no weights are shown or kept track of on screen
    entries: list[PointOut]
    latest_kg: float | None = None
    latest_on: date | None = None
    start_weight_kg: float | None = None
    target_weight_kg: float | None = None
    change_since_start_kg: float | None = None
    kg_to_target: float | None = None
    percent_to_target: int | None = None
    weekly_change_kg: float | None = None
