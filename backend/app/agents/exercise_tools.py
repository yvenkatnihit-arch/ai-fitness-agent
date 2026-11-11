"""Read-only exercise tools for the exercise specialist (Step 8.2, D-106). Our exercise library only; nothing is changed; run as the user.

Every exercise comes back marked `fits_you` (true, false with the reason, or unknown when onboarding did not save the injury answers),
using the SAME rules that plan generation uses (injuries, level, place, equipment: app.calc.exercise_filter), so chat never recommends
something the plan builder would hide from this user."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
from app.calc.exercise_filter import ExerciseNeeds, ExerciseOption, setting_for, why_hidden
from app.calc.exercise_search import alternatives_to, find_by_name, search
from app.core.vocabulary import InjuryArea, MuscleGroup
from app.db import exercises as repo
from app.db.transactions import user_transaction

NOT_FOUND = "No exercise with that key in our library. Use a key returned by search_exercises."
UNKNOWN_FIT = "We do not know this user's injuries yet, so we cannot say whether it suits them."


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=80, description="exercise name or words, e.g. squat, glute bridge, push up")
    muscle: MuscleGroup | None = Field(default=None, description="only exercises that train this muscle group")
    injury: InjuryArea | None = Field(default=None, description="a body area the user says hurts or is injured right now, e.g. shoulder or knee: "
                                      "exercises that are not suitable with it are left out, even if it is not in their profile")
    fits_me_only: bool = Field(default=True, description="true: hide exercises this user should not do (injury, level, place, equipment)")
    limit: int = Field(default=5, ge=1, le=8)


class KeyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_key: str = Field(min_length=1, max_length=80, description="the `key` of an exercise returned by search_exercises")


def _fit(option: ExerciseOption, context: repo.TrainingContext | None) -> tuple[bool | None, str | None]:
    """(fits, reason): None for fits means unknown. A user who trains in both places fits if either place works."""
    if context is None:
        return None, UNKNOWN_FIT
    places = ("gym", "home") if context.workout_location == "both" else (setting_for(context.workout_location),)
    reasons = [why_hidden(option, ExerciseNeeds(place, context.level, context.injuries, context.equipment)) for place in places]
    return (True, None) if any(r is None for r in reasons) else (False, reasons[0])


def _summary(option: ExerciseOption, context: repo.TrainingContext | None) -> dict[str, Any]:
    fits, why_not = _fit(option, context)
    out = {"key": option.key, "name": option.name, "muscles": list(option.muscle_groups), "equipment": list(option.equipment) or ["none"],
           "level": option.difficulty, "where": option.location, "fits_you": fits}
    if why_not:
        out["why_not"] = why_not
    return out


def _search(ctx: RunContext, args: SearchArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        options = repo.list_exercises(conn)
        context = repo.read_training_context(conn)
    found = search(options, args.query, args.muscle, None)                   # every match, ranked; filter by what suits the user, THEN cut to the limit
    if args.injury:
        found = [o for o in found if args.injury not in o.contraindications]  # what the person told us now counts as much as their profile
    shown = [_summary(o, context) for o in found]
    if args.fits_me_only:
        shown = [s for s in shown if s["fits_you"] is not False]
    if not shown:
        return {"exercises": [], "note": "Nothing in our library matches" + (" and suits this user." if args.fits_me_only or args.injury else ".")}
    out: dict[str, Any] = {"exercises": shown[:args.limit]}
    if args.injury:
        out["avoiding_injury"] = args.injury
    return out


def _get(ctx: RunContext, args: KeyArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        options = repo.list_exercises(conn)
        context = repo.read_training_context(conn)
    option = next((o for o in options if o.key == args.exercise_key), None)
    if option is None:
        return {"error": NOT_FOUND}
    return {**_summary(option, context), "movement": option.movement_pattern.replace("_", " "), "form_cues": list(option.form_cues),
            "not_for_people_with": list(option.contraindications)}


class AlternativesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise: str = Field(min_length=1, max_length=80, description="the name of the exercise the user wants an alternative to, e.g. bench press")
    injury: InjuryArea | None = Field(default=None, description="a body area the user says hurts right now, e.g. shoulder; not suitable exercises are left out")
    limit: int = Field(default=5, ge=1, le=8)


def _alternatives(ctx: RunContext, args: AlternativesArgs) -> dict[str, Any]:
    """Exercises that train the same main muscle as the named one, kept only if they suit THIS user (profile and any injury they mention)."""
    with user_transaction(ctx.user_id) as conn:
        options = repo.list_exercises(conn)
        context = repo.read_training_context(conn)
    target = find_by_name(options, args.exercise)
    if target is None:
        return {"error": f"No exercise like '{args.exercise}' in our library."}
    candidates = [o for o in alternatives_to(options, target) if not args.injury or args.injury not in o.contraindications]
    shown = [s for s in (_summary(o, context) for o in candidates) if s["fits_you"] is not False]
    out: dict[str, Any] = {"exercise": target.name, "muscles": list(target.muscle_groups), "alternatives": shown[:args.limit]}
    reason = _fit(target, context)[1]
    if args.injury and args.injury in target.contraindications:
        out["why_not_this_one"] = f"{target.name} is not suitable with a {args.injury.replace('_', ' ')} injury"
    elif reason:
        out["why_not_this_one"] = reason
    if not shown:
        out["note"] = "Nothing else in our library trains the same muscle and suits this user."
    return out


SEARCH_EXERCISES = Tool("search_exercises", "Search our exercise library by name or muscle. Each result says whether it fits this user.",
                        SearchArgs, _search, scope="read")
GET_EXERCISE = Tool("get_exercise", "Full details of one exercise from our library: muscles, equipment, level, form cues, who it is not for.",
                    KeyArgs, _get, scope="read")
FIND_ALTERNATIVES = Tool("find_alternatives", "Find alternatives to a named exercise: other exercises for the same muscle that suit this user. "
                         "Use it whenever the user asks for an alternative, substitute or replacement.", AlternativesArgs, _alternatives, scope="read")
