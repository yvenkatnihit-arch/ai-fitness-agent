"""Convert each source's carbohydrate to ours: AVAILABLE carbohydrate, AS WEIGHED (D-038).

USDA ("by difference", includes fibre):     available = carbs - fibre
CoFID ("available", monosaccharide equivalents, excludes fibre):
    exact:  starch/1.10 + oligosaccharides/1.10 + monosaccharides + disaccharides/1.05
    approx: starch/1.10 + total sugars/1.05            (when the sugar breakdown is unknown)
Why the divisors: on paper, CoFID counts starch as if split into glucose (+10 % weight from
added water) and disaccharides as if split (+5 %). Dividing gives back the real weight eaten.
"""

from dataclasses import dataclass
from typing import Literal

from fooddata.records import FoodRecord

STARCH_FACTOR = 1.10
OLIGO_FACTOR = 1.10
DISACCHARIDE_FACTOR = 1.05
ROUNDING_SLACK_G = 0.5  # sources round to 0.1 g; tiny negatives after subtracting are rounding

Quality = Literal["exact", "approximate"]


@dataclass(frozen=True)
class AvailableCarbs:
    grams: float | None   # None = can't be converted reliably (flagged, never guessed)
    quality: Quality | None
    note: str


def available_carbs(food: FoodRecord) -> AvailableCarbs:
    if food.carbs_g is None:
        return AvailableCarbs(None, None, "source has no carbohydrate value")
    if food.carb_basis == "by_difference":
        return _from_usda(food)
    return _from_cofid(food)


def _from_usda(food: FoodRecord) -> AvailableCarbs:
    if food.fiber_g is None:
        return AvailableCarbs(None, None, "fibre unknown, so can't subtract it from total carbohydrate")
    grams = food.carbs_g - food.fiber_g
    if grams < -ROUNDING_SLACK_G:
        return AvailableCarbs(None, None, f"fibre ({food.fiber_g} g) exceeds total carbohydrate ({food.carbs_g} g)")
    return AvailableCarbs(max(grams, 0.0), "exact", "total carbohydrate minus fibre")


def _from_cofid(food: FoodRecord) -> AvailableCarbs:
    parts = food.carb_parts
    if food.carbs_g == 0:
        return AvailableCarbs(0.0, "exact", "no carbohydrate")
    if parts and None not in (parts.starch_g, parts.mono_sugars_g, parts.di_sugars_g):
        grams = (parts.starch_g / STARCH_FACTOR + (parts.oligo_g or 0) / OLIGO_FACTOR
                 + parts.mono_sugars_g + parts.di_sugars_g / DISACCHARIDE_FACTOR)
        return AvailableCarbs(grams, "exact", "starch and sugars converted to weight as eaten")
    if parts and None not in (parts.starch_g, parts.total_sugars_g):
        grams = parts.starch_g / STARCH_FACTOR + parts.total_sugars_g / DISACCHARIDE_FACTOR
        return AvailableCarbs(grams, "approximate", "sugar breakdown unknown; sugars treated as disaccharides")
    return AvailableCarbs(None, None, "starch/sugar breakdown unknown, so can't convert to weight as eaten")
