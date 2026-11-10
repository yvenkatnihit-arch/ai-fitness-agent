"""Scenarios for the meal plan eval (Step 7.7e, D-086): made-up users, never real data.

A body profile goes through the real engine for targets, so the calorie band, protein target and kidney cap are the app's own numbers.
The set includes the hard cases: a thin vegan pool, a 3,000 kcal day (5 meals and scaled portions), the kidney protein cap, and many
dislikes at once.
"""

from dataclasses import dataclass

from app.calc.engine import BodyProfile


@dataclass(frozen=True)
class MealScenario:
    name: str
    diet: str
    profile: BodyProfile
    dislikes: tuple[str, ...] = ()
    cuisines: tuple[str, ...] = ("indian",)


FAT_LOSS_F = BodyProfile(weight_kg=58, height_cm=162.5, age_years=31, sex="female", activity_level="light", goal="fat_loss",
                         screening_flags=frozenset(), pace="normal")
MUSCLE_M = BodyProfile(weight_kg=80, height_cm=178, age_years=27, sex="male", activity_level="moderate", goal="muscle_gain",
                       screening_flags=frozenset(), pace="normal")
MAINTAIN_O = BodyProfile(weight_kg=70, height_cm=170, age_years=40, sex="other", activity_level="sedentary", goal="general_fitness",
                         screening_flags=frozenset(), pace="normal")
KIDNEY_M = BodyProfile(weight_kg=82, height_cm=176, age_years=50, sex="male", activity_level="moderate", goal="fat_loss",
                       screening_flags=frozenset({"kidney"}), pace="normal")

SCENARIOS: list[MealScenario] = [
    MealScenario("vegetarian, fat loss, woman", "vegetarian", FAT_LOSS_F),
    MealScenario("vegan, fat loss, woman (thin pool)", "vegan", FAT_LOSS_F),
    MealScenario("vegetarian, muscle gain, man (about 3,000 kcal)", "vegetarian", MUSCLE_M),
    MealScenario("eggetarian, maintenance", "eggetarian", MAINTAIN_O),
    MealScenario("non-vegetarian, muscle gain, dislikes fish and paneer", "non_vegetarian", MUSCLE_M, ("fish", "paneer")),
    MealScenario("non-vegetarian, kidney flag (protein cap)", "non_vegetarian", KIDNEY_M),
    MealScenario("vegetarian, fat loss, dislikes paneer, soya, mushroom", "vegetarian", FAT_LOSS_F, ("paneer", "soya", "mushroom")),
    MealScenario("Mediterranean, vegetarian, fat loss, woman", "vegetarian", FAT_LOSS_F, (), ("mediterranean",)),
    MealScenario("Mediterranean, non-vegetarian, muscle gain, man", "non_vegetarian", MUSCLE_M, (), ("mediterranean",)),
]
