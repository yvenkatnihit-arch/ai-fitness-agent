"""Change the profile after onboarding (Step 6.8, D-069): merge -> validate with the ONBOARDING forms -> save -> recalculate.

The one function `update_profile` is used by PATCH /profile now and, later, by the approval of a help-bot profile proposal
(D-046), so both get exactly the same validation and the same safety rules. No LLM anywhere.

Order of work, all inside ONE user transaction so a failure at any point rolls the whole edit back:
  read current answers -> merge the change into its section -> validate the MERGED section with the onboarding model
  -> save only what really changed -> if a number-affecting field changed, recalculate the targets with the engine
  (an impossible result raises and undoes the edit) -> commit -> write the new targets row (server-written table).
Nothing here edits a plan: the result only says which plans no longer match.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.calc.engine import Targets, calculate_targets
from app.calc.goals import target_weight_problem
from app.calc.profile_edit import ALL_FIELDS, FIELDS, Effects, effects, group_by_section
from app.calc.session_time import DEFAULT_SESSION_MINUTES
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import profile as repo
from app.db import targets as targets_repo
from app.schemas.onboarding import BasicsIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn
from app.workflows.inputs import body_profile

MODELS = {"basics": BasicsIn, "goal": GoalIn, "preferences": PreferencesIn, "training": TrainingIn, "screening": ScreeningIn}


class NotOnboarded(Exception):
    """Profile edits start after onboarding. str(e) is safe to show."""

    def __init__(self) -> None:
        super().__init__("Please finish onboarding first.")


class ProfileInvalid(Exception):
    """The merged answers are not acceptable together (for example a target weight on the wrong side). Safe to show."""


@dataclass(frozen=True)
class ProfileUpdate:
    profile: dict[str, Any]          # flat: every field by name
    changed: tuple[str, ...]         # only the fields whose value really changed
    effects: Effects
    targets: Targets | None          # the new targets when they were recalculated
    focus_on_habits: bool


def flat_profile(sections: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {field: sections[section][field] for section, fields in FIELDS.items() for field in fields}


def _with_defaults(section: str, values: dict[str, Any]) -> dict[str, Any]:
    """Accounts made before a question existed have no answer: use the app default so unrelated edits still validate."""
    out = dict(values)
    if section == "training" and out.get("session_minutes") is None:
        out["session_minutes"] = DEFAULT_SESSION_MINUTES
    if section == "preferences" and not out.get("cuisines"):
        out["cuisines"] = ["indian"]
    return out


def update_profile(user_id: UUID, changes: dict[str, Any]) -> ProfileUpdate:
    """Raises UnknownFields, pydantic.ValidationError, ProfileInvalid or NotOnboarded (all safe to turn into a 4xx)."""
    groups = group_by_section(changes)
    today = india_today()
    new_targets: Targets | None = None
    goal_id: UUID | None = None
    inputs: dict[str, Any] = {}
    with user_transaction(user_id) as conn:
        current = repo.read_profile(conn)
        if current is None:
            raise NotOnboarded()
        validated = {}
        changed: set[str] = set()
        for section, patch in groups.items():
            before = _with_defaults(section, current[section])
            model = MODELS[section].model_validate({**before, **patch})      # the SAME validation as onboarding
            after = model.model_dump()
            diff = {f for f in FIELDS[section] if after[f] != before[f]}
            if diff:
                validated[section] = model
                changed |= diff
        if not changed:
            return ProfileUpdate(flat_profile(current), (), effects(()), None, False)

        weight = validated["basics"].weight_kg if "basics" in validated else current["basics"]["weight_kg"]
        if "goal" in validated:
            problem = target_weight_problem(validated["goal"].goal_type, weight, validated["goal"].target_weight_kg)
            if problem:
                raise ProfileInvalid(problem)
        elif "weight_kg" in changed:   # a new weight can put the existing target on the wrong side
            goal_now = GoalIn.model_validate(current["goal"])
            problem = target_weight_problem(goal_now.goal_type, weight, goal_now.target_weight_kg)
            if problem:
                raise ProfileInvalid(problem)

        if "basics" in validated:
            repo.update_basics(conn, validated["basics"], "weight_kg" in changed, today)
        if "goal" in validated:
            repo.update_goal(conn, validated["goal"], weight, today)
        if "preferences" in validated:
            repo.update_preferences(conn, validated["preferences"])
        if "training" in validated:
            repo.update_training(conn, validated["training"])
        if "screening" in validated:
            repo.update_screening(conn, validated["screening"])

        result_effects = effects(changed)
        if result_effects.targets_recalculated:
            saved = targets_repo.read_inputs(conn)     # sees the edits made above, inside this same transaction
            if saved is None:
                raise NotOnboarded()
            profile = body_profile(saved, today)
            try:
                new_targets = calculate_targets(profile)
            except ValueError as error:                 # an impossible combination: undo the whole edit
                raise ProfileInvalid(str(error)) from None
            goal_id = saved.goal_id
            inputs = {
                "weight_kg": profile.weight_kg, "height_cm": profile.height_cm, "age_years": profile.age_years,
                "sex": profile.sex, "activity_level": profile.activity_level, "goal": profile.goal, "pace": profile.pace,
                "screening_flags": sorted(profile.screening_flags), "calculated_on": today.isoformat(),
                "reason": "profile edit",
            }
        refreshed = repo.read_profile(conn)
    if new_targets is not None and goal_id is not None:
        with admin_transaction("profile edit: save recalculated targets") as conn:    # calculated_targets is server-written
            targets_repo.insert_targets(conn, user_id, goal_id, new_targets, inputs)
    ordered = tuple(f for f in ALL_FIELDS if f in changed)
    return ProfileUpdate(flat_profile(refreshed or current), ordered, result_effects, new_targets,
                         bool(new_targets.focus_on_habits) if new_targets else False)
