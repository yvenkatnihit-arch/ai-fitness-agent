import pytest

from app.calc.goals import target_weight_problem


@pytest.mark.parametrize(
    ("goal", "current", "target", "ok"),
    [
        ("fat_loss", 80, 72, True),
        ("fat_loss", 80, 80, False),
        ("fat_loss", 80, 85, False),
        ("weight_gain", 50, 56, True),
        ("weight_gain", 50, 48, False),
        ("muscle_gain", 70, 74, True),
        ("muscle_gain", 70, 70, True),   # recomp-style muscle gain at the same weight is fine
        ("muscle_gain", 70, 65, False),
        ("recomp", 70, 65, True),        # no direction rule for recomp
        ("general_fitness", 70, 75, True),
        ("fat_loss", 80, None, True),    # no target given
    ],
)
def test_target_weight_direction(goal, current, target, ok):
    assert (target_weight_problem(goal, current, target) is None) is ok
