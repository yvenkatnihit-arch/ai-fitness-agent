"""Safety clamps: turn the goal's ideal target into a safe one, and say why it changed.

Applied in this order (each can only make the target more conservative):
  1. Surplus cap       target <= TDEE * (1 + 10%)
  2. Deficit cap       target >= TDEE * (1 - cap), cap = 25% / 10% if flagged / 0% for ED history
  3. Loss-rate cap     daily deficit <= 1% of body weight per week, in kcal (7700 kcal/kg / 7 days)
  4. Calorie floor     target >= 1200 (female) / 1500 (male, other). Applied last, always wins.
All limits come from safety_config.py.
"""

from dataclasses import dataclass

from app.calc.validation import require_positive, require_range
from app.safety import safety_config as cfg
from app.safety.safety_config import Sex

# Reason codes. The UI turns these into friendly messages; tests check them exactly.
SURPLUS_CAP = "surplus_cap"
DEFICIT_CAP = "deficit_cap"
SCREENING_DEFICIT_CAP = "screening_deficit_cap"
EATING_DISORDER_NO_DEFICIT = "eating_disorder_no_deficit"
WEEKLY_LOSS_RATE_CAP = "weekly_loss_rate_cap"
CALORIE_FLOOR = "calorie_floor"


@dataclass(frozen=True)
class SafeTarget:
    kcal: float
    reasons: tuple[str, ...]   # which clamps changed the target, in the order applied
    doctor_note: bool          # any screening flag -> plan shows "please check with your doctor"
    focus_on_habits: bool      # eating disorder history -> show balanced meals, not numbers


def apply_safety_clamps(
    target_kcal: float,
    tdee_kcal: float,
    weight_kg: float,
    sex: Sex,
    screening_flags: set[str],
) -> SafeTarget:
    """Return the safe daily calorie target. Raises ValueError for bad inputs or unknown flags."""
    require_positive("target_kcal", target_kcal)
    require_positive("tdee_kcal", tdee_kcal)
    require_range("weight_kg", weight_kg, cfg.MIN_WEIGHT_KG, cfg.MAX_WEIGHT_KG)
    max_deficit = cfg.max_deficit_fraction(screening_flags)  # also rejects unknown flags
    floor = cfg.calorie_floor(sex)

    kcal = target_kcal
    reasons: list[str] = []

    # 1. Surplus cap
    highest = tdee_kcal * (1 + cfg.MAX_SURPLUS_FRACTION)
    if kcal > highest:
        kcal = highest
        reasons.append(SURPLUS_CAP)

    # 2. Deficit cap (stricter with screening flags)
    lowest = tdee_kcal * (1 - max_deficit)
    if kcal < lowest:
        kcal = lowest
        if "eating_disorder_history" in screening_flags:
            reasons.append(EATING_DISORDER_NO_DEFICIT)
        elif screening_flags:
            reasons.append(SCREENING_DEFICIT_CAP)
        else:
            reasons.append(DEFICIT_CAP)

    # 3. Weekly loss-rate cap
    max_daily_deficit = weight_kg * cfg.MAX_WEEKLY_LOSS_FRACTION * cfg.KCAL_PER_KG_FAT / 7
    if tdee_kcal - kcal > max_daily_deficit:
        kcal = tdee_kcal - max_daily_deficit
        reasons.append(WEEKLY_LOSS_RATE_CAP)

    # 4. Calorie floor, last so nothing can push the target below it
    if kcal < floor:
        kcal = floor
        reasons.append(CALORIE_FLOOR)

    return SafeTarget(
        kcal=kcal,
        reasons=tuple(reasons),
        doctor_note=bool(screening_flags),
        focus_on_habits="eating_disorder_history" in screening_flags,
    )
