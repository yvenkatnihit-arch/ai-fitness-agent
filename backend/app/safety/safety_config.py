"""Every safety limit in one place (brief section 7, decisions D-009 and D-010).

Rules:
- These are plain constants. They are NOT read from .env and NOT changeable by the LLM.
- Calculation code imports from here; it never hardcodes its own limits.
- Changing a value here is a product decision: log it in docs/DECISIONS.md.
"""

from types import MappingProxyType
from typing import Final, Literal

Sex = Literal["female", "male", "other"]

# --- Who can use the app ---
MIN_AGE_YEARS: Final = 18

# --- Plausible body inputs (D-019) ---
# Values outside these ranges are almost certainly typos (e.g. 1.7 for height in metres)
# and would produce nonsense targets, so calculations reject them.
MAX_AGE_YEARS: Final = 100
MIN_WEIGHT_KG: Final = 30.0
MAX_WEIGHT_KG: Final = 300.0
MIN_HEIGHT_CM: Final = 120.0
MAX_HEIGHT_CM: Final = 230.0

# --- Calorie targets ---
# Daily floor. "other" uses the higher floor (D-009).
_CALORIE_FLOOR_KCAL: Final[dict[Sex, int]] = {"female": 1200, "male": 1500, "other": 1500}
# Read-only view, so no code can change a floor at runtime.
CALORIE_FLOOR_KCAL: Final = MappingProxyType(_CALORIE_FLOOR_KCAL)

# Deficit can be at most 25% of TDEE.
MAX_DEFICIT_FRACTION: Final = 0.25
# Surplus can be at most 10% of TDEE (D-010).
MAX_SURPLUS_FRACTION: Final = 0.10
# Planned weight loss can be at most ~1% of body weight per week.
MAX_WEEKLY_LOSS_FRACTION: Final = 0.01
# Energy in 1 kg of body fat, used to turn the weekly loss cap into a daily kcal cap (D-022).
KCAL_PER_KG_FAT: Final = 7700

# --- Health screening (brief section 7) ---
SCREENING_FLAGS: Final = (
    "pregnant_or_breastfeeding",
    "diabetes",
    "heart_or_bp",
    "kidney",
    "recent_surgery_or_injury",
    "eating_disorder_history",
)
# Any flag set -> deficit capped at a mild level (D-016).
FLAGGED_MAX_DEFICIT_FRACTION: Final = 0.10
# Eating disorder history -> no deficit at all; focus on balanced meals and habits.
EATING_DISORDER_MAX_DEFICIT_FRACTION: Final = 0.0
# Kidney flag -> protein capped at the general adult recommendation (D-023).
KIDNEY_MAX_PROTEIN_G_PER_KG: Final = 0.8

# --- Macros (D-023) ---
# Protein never more than 35% of calories (stops huge targets for very heavy users).
MAX_PROTEIN_KCAL_FRACTION: Final = 0.35
# Fat at least 25% of calories (hormones, absorbing vitamins A, D, E, K).
MIN_FAT_KCAL_FRACTION: Final = 0.25

# --- Training volume (D-060) ---
# The most hard sets one muscle may get in a week. Focus areas can add sets only up to this; the model can't raise it.
MAX_WEEKLY_SETS_PER_MUSCLE: Final = 20

# --- Weekly check-in (brief section 4.4) ---
# Fewer weigh-ins than this in a week -> ask the user to log more, don't adjust.
MIN_WEIGH_INS_FOR_CHECKIN: Final = 4
# Size of one calorie adjustment.
MIN_ADJUSTMENT_KCAL: Final = 100
MAX_ADJUSTMENT_KCAL: Final = 200


def calorie_floor(sex: Sex) -> int:
    """Minimum daily calorie target for this sex."""
    return CALORIE_FLOOR_KCAL[sex]


def check_screening_flags(flags: set[str]) -> None:
    """Raise ValueError for any flag name we don't know (a typo must never be ignored)."""
    unknown = flags - set(SCREENING_FLAGS)
    if unknown:
        raise ValueError(f"Unknown screening flags: {sorted(unknown)}")


def max_deficit_fraction(flags: set[str]) -> float:
    """Largest allowed deficit (as a fraction of TDEE) given the user's screening flags."""
    check_screening_flags(flags)
    if "eating_disorder_history" in flags:
        return EATING_DISORDER_MAX_DEFICIT_FRACTION
    if flags:
        return FLAGGED_MAX_DEFICIT_FRACTION
    return MAX_DEFICIT_FRACTION
