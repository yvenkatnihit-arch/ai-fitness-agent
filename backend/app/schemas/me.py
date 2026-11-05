from uuid import UUID

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    has_profile: bool  # False until onboarding creates the profile row (Phase 3)
