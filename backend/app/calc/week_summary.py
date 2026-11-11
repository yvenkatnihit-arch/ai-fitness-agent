"""The last seven days of logging, summed by code (Step 8.4, D-108). The model only reads the result; it never adds or compares.

"On target" means within ON_TARGET_BAND of the calorie target. It is a coaching label, not a medical limit, so it lives here and not in
safety_config.py."""

from collections.abc import Sequence
from datetime import date, timedelta

ON_TARGET_BAND = 0.10        # eaten calories within 10 percent of the target count as "on target"
DAYS = 7
KEYS = ("kcal", "protein_g", "carbs_g", "fat_g")


def last_days(today: date, days: int = DAYS) -> list[date]:
    """Oldest first, ending today."""
    return [today - timedelta(days=n) for n in range(days - 1, -1, -1)]


def summarize_week(totals_by_day: dict[date, dict[str, float]], today: date, kcal_target: float | None, protein_target: float | None) -> dict:
    """`totals_by_day` has only the days something was logged. Days without a log are reported as not logged: they are NOT counted as zero,
    because someone who forgot to log is not someone who ate nothing."""
    days = []
    for day in last_days(today):
        logged = day in totals_by_day
        entry = {"date": day.isoformat(), "weekday": day.strftime("%A"), "logged": logged}
        if logged:
            entry.update({k: round(totals_by_day[day][k], 1) for k in KEYS})
        days.append(entry)
    logged_days = [d for d in days if d["logged"]]
    out: dict = {"days": days, "days_logged": len(logged_days), "days_checked": DAYS}
    if not logged_days:
        return out
    out["average_when_logged"] = {k: round(sum(d[k] for d in logged_days) / len(logged_days), 1) for k in KEYS}
    if kcal_target and kcal_target > 0:
        low, high = kcal_target * (1 - ON_TARGET_BAND), kcal_target * (1 + ON_TARGET_BAND)
        out["calorie_target"] = round(kcal_target)
        out["days_within_10_percent_of_calorie_target"] = sum(low <= d["kcal"] <= high for d in logged_days)
        out["average_percent_of_calorie_target"] = round(out["average_when_logged"]["kcal"] / kcal_target * 100)
    if protein_target and protein_target > 0:
        out["protein_target_g"] = round(protein_target)
        out["average_percent_of_protein_target"] = round(out["average_when_logged"]["protein_g"] / protein_target * 100)
    return out


def remaining_today(eaten: dict[str, float], kcal_target: float, protein_target: float, carbs_target: float, fat_target: float) -> dict[str, float]:
    """What is left of today's targets (target minus eaten), whole numbers like the Targets screen. Negative means over the target."""
    targets = {"kcal": kcal_target, "protein_g": protein_target, "carbs_g": carbs_target, "fat_g": fat_target}
    return {k: round(round(targets[k]) - eaten[k], 1) for k in KEYS}


def logged_days_only(days: Sequence[dict]) -> dict:
    """What a user who must not see numbers is told: which days they logged, nothing else."""
    return {"days_logged": sum(d["logged"] for d in days), "days_checked": DAYS,
            "logged_on": [d["weekday"] for d in days if d["logged"]]}
