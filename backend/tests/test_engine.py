import pathlib
import re

import pytest

from app.calc.engine import BodyProfile, calculate_targets

# Five example people, every number worked out by hand.
# Columns: bmr, tdee, goal target, safe target, protein, fat, carbs, reasons, doctor_note, focus_on_habits
CASES = [
    pytest.param(
        BodyProfile(80, 180, 30, "male", "moderate", "fat_loss"),
        # 10*80+6.25*180-5*30+5 = 1780; *1.55 = 2759; *0.8 = 2207.2 (within all limits)
        # protein 80*2 = 160; fat 2207.2*.25/9 = 61.311; carbs (2207.2-640-551.8)/4 = 253.85
        (1780, 2759, 2207.2, 2207.2, 160, 61.3111, 253.85, (), False, False),
        id="typical fat loss",
    ),
    pytest.param(
        BodyProfile(60, 165, 25, "female", "light", "fat_loss", frozenset({"diabetes"})),
        # 1345.25; *1.375 = 1849.71875; *0.8 = 1479.775 -> 10% cap: *0.9 = 1664.746875
        # protein 120; fat 1664.746875*.25/9 = 46.2430; carbs (1664.746875-480-416.18671875)/4 = 192.1400
        (1345.25, 1849.71875, 1479.775, 1664.746875, 120, 46.2430, 192.1400,
         ("screening_deficit_cap",), True, False),
        id="diabetes flag softens the deficit",
    ),
    pytest.param(
        BodyProfile(70, 170, 40, "other", "sedentary", "general_fitness",
                    frozenset({"eating_disorder_history"})),
        # 1484.5; *1.2 = 1781.4; maintenance, nothing to clamp
        # protein 112; fat 1781.4*.25/9 = 49.4833; carbs (1781.4-448-445.35)/4 = 222.0125
        (1484.5, 1781.4, 1781.4, 1781.4, 112, 49.4833, 222.0125, (), True, True),
        id="eating disorder history: maintenance, focus on habits",
    ),
    pytest.param(
        BodyProfile(45, 150, 60, "female", "sedentary", "fat_loss"),
        # 450+937.5-300-161 = 926.5; *1.2 = 1111.8; *0.8 = 889.44 -> floor 1200
        # protein 90; fat 300/9 = 33.333; carbs (1200-360-300)/4 = 135
        (926.5, 1111.8, 889.44, 1200, 90, 33.3333, 135, ("calorie_floor",), False, False),
        id="small sedentary woman hits the calorie floor",
    ),
    pytest.param(
        BodyProfile(140, 185, 35, "male", "moderate", "fat_loss", frozenset({"kidney"})),
        # 1400+1156.25-175+5 = 2386.25; *1.55 = 3698.6875; *0.8 = 2958.95 -> 10% cap: 3328.81875
        # protein 140*2 = 280 -> kidney 140*0.8 = 112; fat 3328.81875*.25/9 = 92.4672
        # carbs (3328.81875-448-832.2046875)/4 = 512.1535
        (2386.25, 3698.6875, 2958.95, 3328.81875, 112, 92.4672, 512.1535,
         ("screening_deficit_cap", "kidney_protein_cap"), True, False),
        id="kidney flag: softer deficit and protein cap",
    ),
]


@pytest.mark.parametrize(("profile", "expected"), CASES)
def test_example_people(profile, expected):
    bmr, tdee, goal, safe, protein, fat, carbs, reasons, doctor, habits = expected
    t = calculate_targets(profile)

    assert t.bmr_kcal == pytest.approx(bmr)
    assert t.tdee_kcal == pytest.approx(tdee)
    assert t.goal_target_kcal == pytest.approx(goal)
    assert t.calorie_target_kcal == pytest.approx(safe)
    assert t.protein_g == pytest.approx(protein, rel=1e-4)
    assert t.fat_g == pytest.approx(fat, rel=1e-4)
    assert t.carbs_g == pytest.approx(carbs, rel=1e-4)
    assert t.reasons == reasons
    assert t.doctor_note is doctor
    assert t.focus_on_habits is habits


@pytest.mark.parametrize(("profile", "expected"), CASES)
def test_macros_add_up_to_the_safe_target(profile, expected):
    t = calculate_targets(profile)
    assert t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9 == pytest.approx(t.calorie_target_kcal)


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError):
        calculate_targets(BodyProfile(80, 180, 17, "male", "moderate", "fat_loss"))


def test_calc_package_never_imports_db_web_or_llm_code():
    # D-005: calc/ is pure Python. This keeps "the LLM never does math" enforceable.
    forbidden = re.compile(r"^\s*(from|import)\s+(fastapi|psycopg|langchain|langgraph|httpx|supabase|google)", re.M)
    calc_dir = pathlib.Path(__file__).parents[1] / "app" / "calc"
    offenders = [p.name for p in calc_dir.glob("*.py") if forbidden.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
