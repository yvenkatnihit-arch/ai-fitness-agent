"""When might the user reach their target weight? (Step 6.5, D-050)

Pure code. It replays the plan week by week with the same calculation engine that sets the daily
calorie target, so every safety limit applies (deficit cap, weekly-loss cap, calorie floor, flag caps):

    each week:  daily gap = calorie target - TDEE        (negative = eating below maintenance)
                weekly change = gap * 7 / 7700 kcal per kg
                new weight = weight + weekly change * adherence
                then recalculate TDEE and the target for the new weight

TDEE falls as weight falls, so the pace slows down; that is why a fixed "kg per week" would be too hopeful.

The answer is a RANGE, never a promise: people follow plans about 70-100% of the time.
"""

import math
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal

from app.calc.engine import BodyProfile, calculate_targets
from app.safety import safety_config as cfg

Status = Literal["ready", "no_target", "wrong_direction", "already_there", "not_moving", "too_far", "habits_only"]

# Share of planned weeks actually followed: best case, likely, worst case.
ADHERENCE_EARLIEST, ADHERENCE_LIKELY, ADHERENCE_LATEST = 1.0, 0.85, 0.70
MAX_WEEKS = 104                  # two years; beyond that we say so instead of guessing
CLOSE_ENOUGH_KG = 0.5            # within this of the target counts as there
MIN_MOVING_KG_PER_WEEK = 0.05    # slower than this is "not moving"
GOAL_DIRECTION = {"fat_loss": -1, "muscle_gain": 1, "weight_gain": 1}   # which way each goal moves the scale


@dataclass(frozen=True)
class Forecast:
    status: Status
    current_weight_kg: float
    target_weight_kg: float | None
    weekly_change_kg: float | None = None    # this week, if the plan is followed fully (negative = losing)
    earliest: date | None = None
    likely: date | None = None
    latest: date | None = None
    weeks_likely: int | None = None


def weekly_change_kg(profile: BodyProfile) -> float:
    """How much the weight changes in a week if the plan is followed exactly."""
    t = calculate_targets(profile)
    return (t.calorie_target_kcal - t.tdee_kcal) * 7 / cfg.KCAL_PER_KG_FAT


def _days_to_target(profile: BodyProfile, target_kg: float, adherence: float) -> int | None:
    """Days until the weight reaches the target, or None if it does not within MAX_WEEKS."""
    weight = profile.weight_kg
    losing = target_kg < weight
    for week in range(MAX_WEEKS):
        change = weekly_change_kg(replace(profile, weight_kg=weight)) * adherence
        if abs(change) < 0.01 or (change < 0) != losing:
            return None                      # the plan has stopped moving (or turned round): it will not get there
        remaining = target_kg - weight
        if abs(change) >= abs(remaining):    # reached part-way through this week
            return math.ceil((week + abs(remaining) / abs(change)) * 7)
        weight += change
        if not cfg.MIN_WEIGHT_KG <= weight <= cfg.MAX_WEIGHT_KG:
            return None
    return None


def forecast_goal(profile: BodyProfile, target_weight_kg: float | None, today: date) -> Forecast:
    """The forecast for this person. `profile.weight_kg` is their current weight."""
    current = profile.weight_kg
    if "eating_disorder_history" in profile.screening_flags:
        return Forecast("habits_only", current, None)          # numbers are hidden for them (brief section 7)
    if target_weight_kg is None or profile.goal in ("general_fitness", "recomp"):
        return Forecast("no_target", current, target_weight_kg)  # these goals do not aim at a body weight
    if abs(target_weight_kg - current) <= CLOSE_ENOUGH_KG:
        return Forecast("already_there", current, target_weight_kg)

    wants_to_lose = target_weight_kg < current
    goal_direction = GOAL_DIRECTION.get(profile.goal)
    if goal_direction is not None and (goal_direction < 0) != wants_to_lose:
        return Forecast("wrong_direction", current, target_weight_kg)   # e.g. fat loss with a target above today's weight

    first_week = weekly_change_kg(profile)
    # Held within safe limits, the plan may not move the weight toward the target (e.g. a small person whose
    # calorie floor is above their maintenance): then there is honestly no date to give.
    if abs(first_week) < MIN_MOVING_KG_PER_WEEK or (first_week < 0) != wants_to_lose:
        return Forecast("not_moving", current, target_weight_kg, round(first_week, 2))

    days = {name: _days_to_target(profile, target_weight_kg, a) for name, a in
            (("earliest", ADHERENCE_EARLIEST), ("likely", ADHERENCE_LIKELY), ("latest", ADHERENCE_LATEST))}
    if days["latest"] is None or days["likely"] is None or days["earliest"] is None:
        return Forecast("too_far", current, target_weight_kg, round(first_week, 2))
    return Forecast(
        "ready", current, target_weight_kg, round(first_week, 2),
        earliest=today + timedelta(days=days["earliest"]), likely=today + timedelta(days=days["likely"]),
        latest=today + timedelta(days=days["latest"]), weeks_likely=math.ceil(days["likely"] / 7),
    )
