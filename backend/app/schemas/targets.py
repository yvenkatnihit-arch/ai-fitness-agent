"""What the app shows about daily targets."""

from pydantic import BaseModel

from app.calc import clamps, macros

# One plain-English line per reason code (from app/calc/clamps.py and app/calc/macros.py).
REASON_MESSAGES: dict[str, str] = {
    clamps.SURPLUS_CAP: "We kept your calorie surplus small so the gain is mostly muscle, not fat.",
    clamps.DEFICIT_CAP: "We limited your calorie deficit to a safe, sustainable level.",
    clamps.SCREENING_DEFICIT_CAP: "Because of your health answers, we kept your calorie deficit mild.",
    clamps.EATING_DISORDER_NO_DEFICIT: "Your plan focuses on balanced, regular meals rather than eating less.",
    clamps.WEEKLY_LOSS_RATE_CAP: "We slowed your planned weight loss to at most about 1% of your body weight a week.",
    clamps.CALORIE_FLOOR: "We raised your target to a safe daily minimum.",
    macros.KIDNEY_PROTEIN_CAP: "Because of your kidney health answer, we kept your protein moderate.",
    macros.PROTEIN_CALORIE_CAP: "We capped protein at a sensible share of your daily calories.",
}

DOCTOR_NOTE = (
    "Some of your health answers mean you should check this plan with your doctor before starting."
)


class TargetsOut(BaseModel):
    # Numbers are None when focus_on_habits is true: the app shows habits, not numbers (brief section 7).
    calorie_target_kcal: int | None
    protein_g: int | None
    fat_g: int | None
    carbs_g: int | None
    reasons: list[str]          # plain-English lines, safe to show
    doctor_note: str | None
    focus_on_habits: bool


def to_targets_out(calorie_kcal: float, protein_g: float, fat_g: float, carbs_g: float,
                   reason_codes: list[str], doctor_note: bool, focus_on_habits: bool) -> TargetsOut:
    """Round for display (whole kcal and grams) and hide numbers when focusing on habits."""
    show = not focus_on_habits
    return TargetsOut(
        calorie_target_kcal=round(calorie_kcal) if show else None,
        protein_g=round(protein_g) if show else None,
        fat_g=round(fat_g) if show else None,
        carbs_g=round(carbs_g) if show else None,
        reasons=[REASON_MESSAGES[code] for code in reason_codes],
        doctor_note=DOCTOR_NOTE if doctor_note else None,
        focus_on_habits=focus_on_habits,
    )
