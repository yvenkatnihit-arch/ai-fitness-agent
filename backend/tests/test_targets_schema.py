from app.calc import clamps, macros
from app.schemas.targets import DOCTOR_NOTE, REASON_MESSAGES, to_targets_out


def reason_codes(module) -> set[str]:
    """Every UPPER_CASE string constant in a calc module is a reason code."""
    return {v for k, v in vars(module).items() if k.isupper() and isinstance(v, str)}


def test_every_reason_code_has_a_message():
    assert reason_codes(clamps) | reason_codes(macros) == set(REASON_MESSAGES)


def test_numbers_are_rounded_for_display():
    out = to_targets_out(2207.2, 160.0, 61.31, 253.85, [], False, False)
    assert (out.calorie_target_kcal, out.protein_g, out.fat_g, out.carbs_g) == (2207, 160, 61, 254)
    assert out.reasons == [] and out.doctor_note is None


def test_habits_focus_hides_every_number():
    out = to_targets_out(1781.4, 112, 49.5, 222.0, [clamps.EATING_DISORDER_NO_DEFICIT], True, True)
    assert (out.calorie_target_kcal, out.protein_g, out.fat_g, out.carbs_g) == (None, None, None, None)
    assert out.focus_on_habits is True
    assert out.doctor_note == DOCTOR_NOTE
    assert out.reasons == [REASON_MESSAGES[clamps.EATING_DISORDER_NO_DEFICIT]]
