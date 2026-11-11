"""What GET /dashboard/today returns (Step 8.1, D-105). Everything is assembled by code from saved data: no model, no recalculation by the
client. For a user who must not see numbers (eating-disorder history) every calorie and macro number is left out HERE."""

from datetime import date

from pydantic import BaseModel


class Progress(BaseModel):
    eaten: float
    target: float
    percent: int          # whole percent of the target, computed by code (can be over 100)


class ProgressOut(BaseModel):
    kcal: Progress
    protein_g: Progress
    carbs_g: Progress
    fat_g: Progress


class LoggedMeal(BaseModel):
    slot: str
    foods: list[str]      # "Roti (2 piece)"


class PlannedItem(BaseModel):
    name: str
    text: str             # "1.5 katori (225 g)"
    kcal: float | None = None


class PlannedMeal(BaseModel):
    slot: str
    items: list[PlannedItem]


class PlanToday(BaseModel):
    meals: list[PlannedMeal]
    kcal: float | None = None      # the day's planned calories (None when numbers are hidden)


class WorkoutExercise(BaseModel):
    name: str
    sets: int
    reps: str             # "8-12"


class WorkoutToday(BaseModel):
    rest_day: bool
    focus: str | None = None
    minutes: int | None = None
    exercises: list[WorkoutExercise] = []


class TodayOut(BaseModel):
    date: date
    weekday: str
    numbers_hidden: bool
    progress: ProgressOut | None      # None when numbers are hidden, or there are no targets yet
    logged: list[LoggedMeal]
    meal_plan: PlanToday | None       # None = no approved meal plan (or no entry for today)
    workout: WorkoutToday | None      # None = no approved workout plan
