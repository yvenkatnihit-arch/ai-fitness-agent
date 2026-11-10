"""Which foods may appear in a user's meal plan, and in which role of which meal (Step 6.7a, D-062). Plain code.

The model will only ever CHOOSE from these lists (it never invents a food), and the solver then sets the grams.
A meal is built from roles: lunch = a staple + a protein + a vegetable dish + a side; breakfast = a main
(+ an optional extra); snacks = one item. The roles keep a plan looking like real Indian meals.

Left out on purpose (for now): sweets and fried snacks (a "treat" rule can add them later), spices, oils and
sweeteners (not meals), and raw meat and fish (raw versus cooked weight is ambiguous; cooked dishes cover them).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

# DB slot names (meal_plan_items.slot). Normal days use four meals; big days (BIG_DAY_KCAL and up) add a mid-morning one,
# because no one fits 3,000 kcal into four meals (found on real data, D-065).
SLOTS = ("breakfast", "lunch", "evening_snack", "dinner")
ALL_SLOTS = ("breakfast", "mid_morning", "lunch", "evening_snack", "dinner")
BIG_DAY_KCAL = 2500
# Share of the day's calories each slot should carry (the solver aims for these).
SLOT_CALORIE_SHARE = {"breakfast": 0.25, "lunch": 0.35, "evening_snack": 0.10, "dinner": 0.30}
BIG_DAY_CALORIE_SHARE = {"breakfast": 0.22, "mid_morning": 0.10, "lunch": 0.30, "evening_snack": 0.08, "dinner": 0.30}


def slots_for(kcal: float) -> tuple[str, ...]:
    return ALL_SLOTS if kcal >= BIG_DAY_KCAL else SLOTS


def shares_for(slots: Sequence[str]) -> dict[str, float]:
    return dict(BIG_DAY_CALORIE_SHARE if "mid_morning" in slots else SLOT_CALORIE_SHARE)

# A diet type may eat these food diet classes (a food's class is the strictest diet that can eat it).
ALLOWED_DIET_CLASSES: dict[str, frozenset[str]] = {
    "vegan": frozenset({"vegan"}),
    "vegetarian": frozenset({"vegan", "vegetarian"}),
    "eggetarian": frozenset({"vegan", "vegetarian", "eggetarian"}),
    "non_vegetarian": frozenset({"vegan", "vegetarian", "eggetarian", "non_vegetarian"}),
}

# dish_side holds both protein-type sides and plain sides, so those roles list their foods by key.
PROTEIN_SIDE_KEYS = frozenset({"boiled_egg", "grilled_chicken", "chana_boiled", "moong_boiled", "rajma_boiled"})
PLAIN_SIDE_KEYS = frozenset({"raita", "boiled_potato"})


@dataclass(frozen=True)
class Role:
    name: str
    categories: frozenset[str] = frozenset()
    keys: frozenset[str] = frozenset()        # specific foods that also fit this role
    required: bool = True

    def fits(self, food: "PoolFood") -> bool:
        return food.key in self.keys or food.category in self.categories

STAPLE = Role("staple", frozenset({"dish_rice", "dish_bread"}))
PROTEIN = Role("protein", frozenset({"dish_dal", "dish_curry_meat"}), PROTEIN_SIDE_KEYS | {"paneer", "egg"})
VEGETABLE = Role("vegetable", frozenset({"dish_sabzi"}))
SIDE = Role("side", frozenset(), PLAIN_SIDE_KEYS | {"curd", "chaas"}, required=False)
BREAKFAST_MAIN = Role("main", frozenset({"dish_breakfast", "dish_bread"}), frozenset({"egg"}))
BREAKFAST_EXTRA = Role("extra", frozenset({"fruit"}), frozenset({"curd", "milk_whole", "milk_toned_low", "boiled_egg"}), required=False)
SNACK = Role("snack", frozenset({"fruit", "nut_seed"}), frozenset({"curd", "chaas", "chana_boiled", "moong_boiled", "boiled_egg"}))

SLOT_ROLES: dict[str, tuple[Role, ...]] = {
    "breakfast": (BREAKFAST_MAIN, BREAKFAST_EXTRA),
    "mid_morning": (SNACK,),
    "lunch": (STAPLE, PROTEIN, VEGETABLE, SIDE),
    "evening_snack": (SNACK,),
    "dinner": (STAPLE, PROTEIN, VEGETABLE, SIDE),
}

EXCLUDED_CATEGORIES = frozenset({"dish_sweet", "dish_snack", "spice", "sweetener", "fat_oil", "meat", "fish"})
MIN_OPTIONS_PER_ROLE = 3   # fewer than this and the plan will repeat a lot: reported, not hidden


@dataclass(frozen=True)
class PoolFood:
    id: int
    key: str
    name: str
    category: str
    diet_class: str
    kcal: float                          # per 100 g
    protein_g: float
    carbs_g: float
    fat_g: float
    review_status: str                   # "ready" or "review" (numbers not yet fully verified)
    synonyms: tuple[str, ...] = ()
    units: tuple[tuple[str, float], ...] = ()   # (household unit, grams), e.g. ("katori", 150.0)
    cuisines: tuple[str, ...] = ("indian",)     # the cuisines this food belongs to (D-088)


@dataclass(frozen=True)
class SlotPool:
    slot: str
    roles: dict[str, tuple[PoolFood, ...]]            # role name -> allowed foods, verified ones first
    required: tuple[str, ...]                          # roles the meal cannot do without
    thin: tuple[str, ...] = field(default_factory=tuple)   # roles with fewer than MIN_OPTIONS_PER_ROLE choices
    missing: tuple[str, ...] = field(default_factory=tuple)  # required roles with NO choice at all


def disliked(food: PoolFood, dislikes: Collection[str]) -> bool:
    """A dislike like 'karela' hides any food whose name or local names contain it (case-insensitive)."""
    wanted = [d.casefold().strip() for d in dislikes if d.strip()]
    names = [food.name.casefold(), *(s.casefold() for s in food.synonyms)]
    return any(w in n for w in wanted for n in names)


def allowed_foods(foods: Sequence[PoolFood], diet_type: str, dislikes: Collection[str],
                  cuisines: Collection[str] | None = None) -> list[PoolFood]:
    """`cuisines` None means every cuisine; otherwise a food must belong to at least one of the user's cuisines."""
    if diet_type not in ALLOWED_DIET_CLASSES:
        raise ValueError(f"diet_type must be one of {list(ALLOWED_DIET_CLASSES)}, got {diet_type!r}")
    ok = ALLOWED_DIET_CLASSES[diet_type]
    wanted = None if cuisines is None else set(cuisines)
    return [f for f in foods if f.diet_class in ok and f.category not in EXCLUDED_CATEGORIES and not disliked(f, dislikes)
            and (wanted is None or wanted & set(f.cuisines))]


def build_pool(foods: Sequence[PoolFood], diet_type: str, dislikes: Collection[str] = (),
               slots: Sequence[str] = SLOTS, cuisines: Collection[str] | None = None) -> dict[str, SlotPool]:
    """For each meal slot: the allowed foods per role. Stable order (verified first, then by name)."""
    usable = allowed_foods(foods, diet_type, dislikes, cuisines)
    pools: dict[str, SlotPool] = {}
    for slot in slots:
        roles: dict[str, tuple[PoolFood, ...]] = {}
        for role in SLOT_ROLES[slot]:
            fits = [f for f in usable if role.fits(f)]
            roles[role.name] = tuple(sorted(fits, key=lambda f: (f.review_status != "ready", f.name)))
        required = tuple(r.name for r in SLOT_ROLES[slot] if r.required)
        pools[slot] = SlotPool(
            slot=slot, roles=roles, required=required,
            thin=tuple(n for n, v in roles.items() if 0 < len(v) < MIN_OPTIONS_PER_ROLE),
            missing=tuple(n for n in required if not roles[n]),
        )
    return pools
