"""One shape for a food from any source: nutrition per 100 g (edible portion)."""

from dataclasses import dataclass
from typing import Literal

# How a source defines carbohydrate (it changes the energy formula, see checks.py):
#   "by_difference"  USDA: 100 - water - protein - fat - ash, so it INCLUDES fibre
#   "available"      CoFID: sugars + starch as monosaccharide equivalents, EXCLUDES fibre
# Our app stores available carbohydrate AS WEIGHED (D-038); fooddata/carbs.py converts.
CarbBasis = Literal["by_difference", "available"]


@dataclass(frozen=True)
class CarbParts:
    """CoFID's carbohydrate breakdown (monosaccharide equivalents), for the D-038 conversion.
    A field is None when the source didn't measure it."""

    starch_g: float | None = None
    oligo_g: float | None = None
    total_sugars_g: float | None = None
    mono_sugars_g: float | None = None   # glucose + fructose + galactose (None if any is unknown)
    di_sugars_g: float | None = None     # sucrose + maltose + lactose (None if any is unknown)


@dataclass(frozen=True)
class FoodRecord:
    source: str                 # key in data/sources.json, e.g. "usda_sr_legacy"
    source_id: str              # the food's id in that source (USDA fdc_id, CoFID food code)
    name: str
    category: str | None        # source's own food group, used by the diet-class checks
    kcal: float | None          # None = not measured (never silently 0)
    protein_g: float | None
    carbs_g: float | None       # in the SOURCE's definition (see carb_basis)
    fat_g: float | None
    fiber_g: float | None
    carb_basis: CarbBasis
    alcohol_g: float | None = None
    carb_parts: CarbParts | None = None
