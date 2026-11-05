import itertools

import pytest

from app.calc import clamps as c
from app.calc.clamps import apply_safety_clamps

# Hand-worked numbers use: male, 80 kg, TDEE 2759 (moderate activity).
#   25% deficit floor : 2759 * 0.75 = 2069.25
#   10% deficit floor : 2759 * 0.90 = 2483.1
#   surplus ceiling   : 2759 * 1.10 = 3034.9
#   loss-rate cap     : 80 * 0.01 * 7700 / 7 = 880 kcal/day


def clamp(target, tdee=2759, weight=80, sex="male", flags=frozenset()):
    return apply_safety_clamps(target, tdee, weight, sex, set(flags))


# --- Targets that are already safe pass through unchanged ---

def test_normal_fat_loss_target_is_unchanged():
    result = clamp(2207.2)  # -20%, within every limit
    assert result.kcal == pytest.approx(2207.2)
    assert result.reasons == ()
    assert result.doctor_note is False
    assert result.focus_on_habits is False


def test_maintenance_is_unchanged():
    assert clamp(2759).reasons == ()


# --- Each clamp, one at a time ---

def test_surplus_cap():
    result = clamp(3200)
    assert result.kcal == pytest.approx(3034.9)
    assert result.reasons == (c.SURPLUS_CAP,)


def test_deficit_cap_without_flags():
    result = clamp(1800)  # asks for ~35% deficit
    assert result.kcal == pytest.approx(2069.25)
    assert result.reasons == (c.DEFICIT_CAP,)


def test_screening_flag_limits_deficit_to_10_percent():
    result = clamp(2207.2, flags={"diabetes"})
    assert result.kcal == pytest.approx(2483.1)
    assert result.reasons == (c.SCREENING_DEFICIT_CAP,)
    assert result.doctor_note is True
    assert result.focus_on_habits is False


def test_eating_disorder_history_means_maintenance():
    result = clamp(2207.2, flags={"eating_disorder_history"})
    assert result.kcal == pytest.approx(2759)
    assert result.reasons == (c.EATING_DISORDER_NO_DEFICIT,)
    assert result.doctor_note is True
    assert result.focus_on_habits is True


def test_weekly_loss_rate_cap():
    # 50 kg, TDEE 3000 -> rate cap 50 * 0.01 * 7700 / 7 = 550 kcal/day.
    # -20% target = 2400 (600 deficit) passes the 25% cap (750) but not the rate cap.
    result = clamp(2400, tdee=3000, weight=50)
    assert result.kcal == pytest.approx(2450)
    assert result.reasons == (c.WEEKLY_LOSS_RATE_CAP,)


def test_calorie_floor_female():
    # TDEE 1450, -20% = 1160: below the 1200 floor for women.
    result = clamp(1160, tdee=1450, weight=55, sex="female")
    assert result.kcal == 1200
    assert result.reasons == (c.CALORIE_FLOOR,)


def test_calorie_floor_other_uses_1500():
    # Even at maintenance, a TDEE below the floor is raised to it.
    result = clamp(1400, tdee=1400, weight=55, sex="other")
    assert result.kcal == 1500
    assert result.reasons == (c.CALORIE_FLOOR,)


# --- Several clamps at once ---

def test_deficit_cap_then_floor():
    # TDEE 1500 female: 1000 requested -> 25% cap gives 1125 -> floor raises to 1200.
    result = clamp(1000, tdee=1500, weight=60, sex="female")
    assert result.kcal == 1200
    assert result.reasons == (c.DEFICIT_CAP, c.CALORIE_FLOOR)


# --- Properties that must hold for any input ---

@pytest.mark.parametrize(
    ("target", "tdee", "weight", "sex", "flags"),
    list(
        itertools.product(
            [900, 1500, 2000, 2500, 3000, 3500],
            [1300, 2000, 2759, 3400],
            [45, 80, 140],
            ["female", "male", "other"],
            [frozenset(), frozenset({"heart_or_bp"}), frozenset({"eating_disorder_history"})],
        )
    ),
)
def test_clamps_never_make_a_target_less_safe(target, tdee, weight, sex, flags):
    result = clamp(target, tdee, weight, sex, flags)
    floor = 1200 if sex == "female" else 1500

    assert result.kcal >= floor
    # A deficit is never deeper than requested...
    if target < tdee:
        assert result.kcal >= target
    # ...and a surplus is never bigger than requested (unless the floor forces it up).
    if target > tdee and target > floor:
        assert result.kcal <= target
    # The surplus cap holds unless the floor itself is above it.
    assert result.kcal <= max(tdee * 1.10, floor) + 1e-9
    # Planned loss never exceeds 1% of body weight per week.
    assert tdee - result.kcal <= weight * 0.01 * 7700 / 7 + 1e-9
    # With eating disorder history there's never a deficit.
    if "eating_disorder_history" in flags:
        assert result.kcal >= tdee - 1e-9


# --- Bad inputs ---

def test_unknown_flag_is_rejected():
    with pytest.raises(ValueError):
        clamp(2200, flags={"diabetis"})


@pytest.mark.parametrize(
    ("target", "tdee", "weight"),
    [(0, 2759, 80), (2200, -1, 80), (2200, 2759, 10), (2200, 2759, True)],
)
def test_rejects_bad_numbers(target, tdee, weight):
    with pytest.raises(ValueError):
        clamp(target, tdee, weight)
