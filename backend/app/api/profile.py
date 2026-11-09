from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.calc.profile_edit import UnknownFields
from app.core.auth import CurrentUser, get_current_user
from app.db import profile as repo
from app.db import user_transaction
from app.schemas.profile import ProfileOut, ProfileUpdateOut, to_update_out
from app.workflows.update_profile import NotOnboarded, ProfileInvalid, flat_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: CurrentUser = Depends(get_current_user)) -> ProfileOut:
    """The user's current answers (no LLM: read from the database)."""
    with user_transaction(user.id) as conn:
        current = repo.read_profile(conn)
    if current is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please finish onboarding first.")
    return ProfileOut(**flat_profile(current))


@router.patch("", response_model=ProfileUpdateOut)
def patch_profile(changes: dict[str, Any] = Body(...), user: CurrentUser = Depends(get_current_user)) -> ProfileUpdateOut:
    """Change some answers, e.g. {"weight_kg": 74}. Validated exactly like onboarding. If a number-affecting answer changed, the
    daily targets are recalculated by the engine. Plans are never edited: the answer says which ones no longer match."""
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nothing to change.")
    try:
        return to_update_out(update_profile(user.id, changes))
    except UnknownFields as error:
        raise RequestValidationError(
            [{"loc": ("body", field), "msg": "This can't be changed here.", "type": "extra_forbidden"} for field in error.fields]
        ) from None
    except ValidationError as error:   # the merged section failed the onboarding rules: report each field like a normal 422
        raise RequestValidationError(
            [{"loc": ("body", *e["loc"]), "msg": e["msg"], "type": e["type"]} for e in error.errors()]
        ) from None
    except ProfileInvalid as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except NotOnboarded as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
