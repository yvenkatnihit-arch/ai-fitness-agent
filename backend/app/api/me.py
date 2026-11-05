from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.db import user_transaction
from app.schemas.me import MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    """Who am I? Proves the token is valid and that queries run as this user (RLS)."""
    with user_transaction(user.id) as conn:
        has_profile = conn.execute(
            "select exists (select 1 from public.profiles where id = auth.uid())"
        ).fetchone()[0]
    return MeResponse(id=user.id, email=user.email, has_profile=has_profile)
