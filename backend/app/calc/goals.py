"""Does a target weight make sense for the goal? Pure function, no I/O."""

from app.calc.targets import Goal


def target_weight_problem(goal: Goal, current_kg: float, target_kg: float | None) -> str | None:
    """Return a short reason the target doesn't fit the goal, or None if it's fine."""
    if target_kg is None:
        return None
    if goal == "fat_loss" and target_kg >= current_kg:
        return "For fat loss, the target weight should be below your current weight."
    if goal == "weight_gain" and target_kg <= current_kg:
        return "For weight gain, the target weight should be above your current weight."
    if goal == "muscle_gain" and target_kg < current_kg:
        return "For muscle gain, the target weight shouldn't be below your current weight."
    return None
