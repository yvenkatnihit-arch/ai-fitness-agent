"""Validation checks for food records. Each returns a list of Issues (empty = passed).

severity "error"   -> the row must not be imported as is
severity "warning" -> import is possible, but a human should look (it goes in the review report)
"""

import re
from dataclasses import dataclass
from typing import Literal

from fooddata.records import FoodRecord

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    check: str
    severity: Severity
    message: str


MACROS = ("protein_g", "carbs_g", "fat_g")


def check_required(food: FoodRecord) -> list[Issue]:
    """Energy and the three macros must be known: the app can't log a food without them."""
    missing = [f for f in ("kcal", *MACROS) if getattr(food, f) is None]
    return [Issue("required", "error", f"missing {', '.join(missing)}")] if missing else []


def check_ranges(food: FoodRecord) -> list[Issue]:
    """Per 100 g: nothing negative, grams <= 100, energy <= 902 kcal (pure fat is ~900)."""
    issues = []
    for field in ("kcal", *MACROS, "fiber_g", "alcohol_g"):
        value = getattr(food, field)
        if value is None:
            continue
        if value < 0:
            issues.append(Issue("ranges", "error", f"{field} is negative ({value})"))
        limit = 902 if field == "kcal" else 100
        if value > limit:
            issues.append(Issue("ranges", "error", f"{field} {value} is above {limit} per 100 g"))
    return issues


def check_macro_mass(food: FoodRecord) -> list[Issue]:
    """Protein + carbs + fat (+ fibre when carbs exclude it) can't exceed ~100 g in 100 g of food.
    Small margin for rounding and for CoFID carbs being in monosaccharide equivalents."""
    if any(getattr(food, f) is None for f in MACROS):
        return []
    total = food.protein_g + food.carbs_g + food.fat_g
    if food.carb_basis == "available" and food.fiber_g:
        total += food.fiber_g
    return [Issue("macro_mass", "error", f"macros add up to {total:.1f} g per 100 g")] if total > 105 else []


# kcal per gram, by how the source defines carbohydrate.
ENERGY_FACTORS = {
    "by_difference": {"protein_g": 4, "carbs_g": 4, "fat_g": 9},   # carbs include fibre -> 4 is an upper bound
    "available": {"protein_g": 4, "carbs_g": 3.75, "fat_g": 9},    # UK: monosaccharide equivalents
}
ALCOHOL_KCAL_PER_G = 7


def expected_kcal(food: FoodRecord) -> float:
    factors = ENERGY_FACTORS[food.carb_basis]
    return sum(getattr(food, f) * k for f, k in factors.items()) + (food.alcohol_g or 0) * ALCOHOL_KCAL_PER_G


def check_energy(food: FoodRecord, tolerance: float = 0.15, floor_kcal: float = 20) -> list[Issue]:
    """Stated energy should match the general formula within max(15 %, 20 kcal).
    A big gap usually means a data or unit error. Sources use food-specific factors, so a
    small gap is normal; this only catches large ones."""
    if food.kcal is None or any(getattr(food, f) is None for f in MACROS):
        return []
    expected = expected_kcal(food)
    gap = abs(food.kcal - expected)
    if gap > max(floor_kcal, tolerance * max(food.kcal, expected)):
        return [Issue("energy", "warning", f"stated {food.kcal:.0f} kcal vs {expected:.0f} from macros")]
    return []


# Diet rules: words in the source's category or the food's name that rule out a diet class.
NON_VEG = re.compile(r"\b(beef|pork|lamb|mutton|veal|chicken|turkey|duck|poultry|fish|finfish|shellfish|"
                     r"prawn|shrimp|crab|mackerel|salmon|tuna|sardine|meat|bacon|ham|sausage|gelatin)\b", re.I)
EGG = re.compile(r"\begg(s)?\b", re.I)
DAIRY = re.compile(r"\b(milk|cheese|butter|ghee|yogurt|yoghurt|curd|paneer|cream|whey|dairy|khoa|khoya)\b", re.I)
PLANT_MILK = re.compile(r"\b(soy|soya|almond|oat|coconut|rice|cashew)\s+(milk|cream|yogurt|yoghurt|butter|paneer)\b|"
                        r"\b(peanut|nut|cocoa|apple|shea)\s+butter\b", re.I)
# Plant foods whose names contain an animal word ("coconut meat" is the white flesh of a coconut).
PLANT_PHRASES = re.compile(r"\b(coconut|nut)\s+meat\b|\bexpressed from grated meat\b|\beggplant\b|"
                           r"\bghee made from vegetable oil\b|"
                           r"\bvegetable ghee\b|\bvanaspati\b|\bdalda\b", re.I)
# CoFID names eggs by the bird that laid them: "Eggs, chicken, whole, boiled" is a hen's egg, not chicken meat.
EGG_OF_BIRD = re.compile(r"\beggs?,?\s+(chicken|duck|hen|quail|turkey)\b", re.I)
DIET_ORDER = ["vegan", "vegetarian", "eggetarian", "non_vegetarian"]  # each allows what's before it


def check_diet_class(name: str, category: str | None, diet_class: str) -> list[Issue]:
    """The diet class we assign must be strict enough for what the food contains.
    Getting this wrong would put meat in a vegetarian's plan, so violations are errors.

    Meat/fish words are checked in the name AND the source category ("Poultry Products").
    Egg/dairy words are checked in the NAME only: USDA's category "Dairy and Egg Products"
    covers milk and eggs together, so it can't tell curd from egg.
    """
    plain_name = EGG_OF_BIRD.sub("egg", PLANT_PHRASES.sub(" ", name))
    needed = "vegan"
    if DAIRY.search(plain_name) and not PLANT_MILK.search(plain_name):
        needed = "vegetarian"
    if EGG.search(plain_name) and not re.search(r"\begg\s*(plant|less|-?free)\b", plain_name, re.I):
        needed = "eggetarian"
    if NON_VEG.search(f"{plain_name} | {category or ''}"):
        needed = "non_vegetarian"
    if DIET_ORDER.index(diet_class) < DIET_ORDER.index(needed):
        return [Issue("diet_class", "error", f"labelled {diet_class!r} but looks {needed!r}: {name}")]
    return []


# Expected energy per 100 g of a COOKED dish, by our dish category. A value outside the range
# usually means the wrong item was mapped (e.g. raw dal flour instead of cooked dal).
DISH_KCAL_RANGES: dict[str, tuple[int, int]] = {
    "dish_rice": (90, 260),        # boiled rice ~130, pulao/biryani up to ~220
    "dish_dal": (40, 220),         # sambar ~50, plain boiled dal ~100, rich dal ~200
    "dish_sabzi": (40, 250),       # dry or gravy vegetable dishes
    "dish_curry_meat": (90, 300),  # chicken/mutton/fish/egg curries
    "dish_bread": (150, 420),      # stuffed paratha ~170, roti ~200-300, puri up to ~400
    "dish_snack": (150, 520),      # samosa, pakora, namkeen
    "dish_breakfast": (40, 300),   # porridge ~70, omelette ~190
    "dish_side": (40, 220),        # raita, boiled potato, grilled chicken
    "dish_sweet": (150, 480),      # halwa, gulab jamun, kulfi
}


def check_dish_plausibility(category: str, kcal: float | None) -> list[Issue]:
    """Cooked dishes only: is the energy per 100 g in the usual range for this kind of dish?"""
    if category not in DISH_KCAL_RANGES or kcal is None:
        return []
    low, high = DISH_KCAL_RANGES[category]
    if not low <= kcal <= high:
        return [Issue("dish_range", "warning", f"{kcal:.0f} kcal is outside the usual {low}-{high} kcal for {category}")]
    return []


def check_food(food: FoodRecord) -> list[Issue]:
    return [*check_required(food), *check_ranges(food), *check_macro_mass(food), *check_energy(food)]


def normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def find_duplicates(foods: list[FoodRecord]) -> dict[str, list[FoodRecord]]:
    """Same normalised name more than once within one source."""
    groups: dict[str, list[FoodRecord]] = {}
    for food in foods:
        groups.setdefault(f"{food.source}:{normalise_name(food.name)}", []).append(food)
    return {key: group for key, group in groups.items() if len(group) > 1}


def compare_sources(a: FoodRecord, b: FoodRecord, tolerance: float = 0.25) -> list[Issue]:
    """When two sources describe the same food, energy should broadly agree (within 25 %)."""
    if a.kcal is None or b.kcal is None:
        return []
    high, low = max(a.kcal, b.kcal), min(a.kcal, b.kcal)
    if high > 0 and (high - low) / high > tolerance and high - low > 20:
        return [Issue("cross_source", "warning", f"{a.source} {a.kcal:.0f} kcal vs {b.source} {b.kcal:.0f} kcal")]
    return []
