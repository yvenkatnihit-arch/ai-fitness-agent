import pytest

from app.safety import safety_config as cfg


# --- Values match the brief and decisions ---

def test_minimum_age_is_18():
    assert cfg.MIN_AGE_YEARS == 18


@pytest.mark.parametrize(("sex", "floor"), [("female", 1200), ("male", 1500), ("other", 1500)])
def test_calorie_floors(sex, floor):
    assert cfg.calorie_floor(sex) == floor


def test_deficit_surplus_and_loss_rate_caps():
    assert cfg.MAX_DEFICIT_FRACTION == 0.25
    assert cfg.MAX_SURPLUS_FRACTION == 0.10
    assert cfg.MAX_WEEKLY_LOSS_FRACTION == 0.01


def test_checkin_rules():
    assert cfg.MIN_WEIGH_INS_FOR_CHECKIN == 4
    assert (cfg.MIN_ADJUSTMENT_KCAL, cfg.MAX_ADJUSTMENT_KCAL) == (100, 200)


# --- Limits can't be changed at runtime ---

def test_calorie_floors_are_read_only():
    with pytest.raises(TypeError):
        cfg.CALORIE_FLOOR_KCAL["female"] = 800


# --- Screening flags make the deficit cap stricter ---

def test_no_flags_uses_normal_deficit_cap():
    assert cfg.max_deficit_fraction(set()) == 0.25


def test_any_flag_limits_deficit_to_mild():
    assert cfg.max_deficit_fraction({"diabetes"}) == cfg.FLAGGED_MAX_DEFICIT_FRACTION


def test_eating_disorder_history_means_no_deficit():
    assert cfg.max_deficit_fraction({"eating_disorder_history"}) == 0.0
    # Even combined with other flags, the strictest rule wins.
    assert cfg.max_deficit_fraction({"eating_disorder_history", "diabetes"}) == 0.0


def test_unknown_flag_is_rejected():
    # A typo must fail loudly, not silently fall back to the normal 25% cap.
    with pytest.raises(ValueError):
        cfg.max_deficit_fraction({"diabetis"})


# --- The limits make sense together ---

def test_limits_are_consistent():
    assert 0 <= cfg.EATING_DISORDER_MAX_DEFICIT_FRACTION < cfg.FLAGGED_MAX_DEFICIT_FRACTION
    assert cfg.FLAGGED_MAX_DEFICIT_FRACTION < cfg.MAX_DEFICIT_FRACTION < 1
    assert 0 < cfg.MAX_SURPLUS_FRACTION < 1
    assert cfg.MIN_ADJUSTMENT_KCAL < cfg.MAX_ADJUSTMENT_KCAL
    assert cfg.CALORIE_FLOOR_KCAL["other"] == max(cfg.CALORIE_FLOOR_KCAL.values())
