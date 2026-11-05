"""Onboarding endpoints. Each saves one form as the signed-in user and returns the new status."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.calc.goals import target_weight_problem
from app.core.auth import CurrentUser, get_current_user
from app.core.time import india_today
from app.db import onboarding as repo
from app.db import user_transaction
from app.schemas.onboarding import BasicsIn, ConsentIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn
from app.schemas.onboarding_status import OnboardingStatus
from app.schemas.targets import TargetsOut, to_targets_out
from app.workflows.complete_onboarding import complete_onboarding

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _conflict(error: repo.OnboardingError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(error))


@router.get("/status", response_model=OnboardingStatus)
def get_status(user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    with user_transaction(user.id) as conn:
        return repo.get_status(conn)


@router.put("/consent", response_model=OnboardingStatus)
def put_consent(body: ConsentIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            repo.save_consent(conn, body.privacy_notice_version)
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None


@router.put("/basics", response_model=OnboardingStatus)
def put_basics(body: BasicsIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            repo.save_basics(conn, body, india_today())
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None


@router.put("/goal", response_model=OnboardingStatus)
def put_goal(body: GoalIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            current = repo.latest_weight_kg(conn)
            if current is None:
                raise repo.BasicsMissing()
            problem = target_weight_problem(body.goal_type, current, body.target_weight_kg)
            if problem:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
            repo.save_goal(conn, body, current, india_today())
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None


@router.put("/preferences", response_model=OnboardingStatus)
def put_preferences(body: PreferencesIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            repo.save_preferences(conn, body)
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None


@router.put("/training", response_model=OnboardingStatus)
def put_training(body: TrainingIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            repo.save_training(conn, body)
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None


@router.post("/complete", response_model=TargetsOut)
def post_complete(user: CurrentUser = Depends(get_current_user)) -> TargetsOut:
    """All forms done -> calculate targets in code -> save -> onboarding finished."""
    try:
        t = complete_onboarding(user.id)
    except repo.OnboardingError as error:
        raise _conflict(error) from None
    return to_targets_out(t.calorie_target_kcal, t.protein_g, t.fat_g, t.carbs_g,
                          list(t.reasons), t.doctor_note, t.focus_on_habits)


@router.put("/screening", response_model=OnboardingStatus)
def put_screening(body: ScreeningIn, user: CurrentUser = Depends(get_current_user)) -> OnboardingStatus:
    try:
        with user_transaction(user.id) as conn:
            repo.save_screening(conn, body)
            return repo.get_status(conn)
    except repo.OnboardingError as error:
        raise _conflict(error) from None
