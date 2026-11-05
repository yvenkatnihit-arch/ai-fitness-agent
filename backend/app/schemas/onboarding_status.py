from typing import Literal

from pydantic import BaseModel

Step = Literal["consent", "basics", "goal", "preferences", "training", "screening", "complete", "done"]


class OnboardingStatus(BaseModel):
    consent: bool
    basics: bool
    goal: bool
    preferences: bool
    training: bool
    screening: bool
    completed: bool  # onboarding finished (targets calculated, Step 3.3)
    next_step: Step  # what the frontend should show next; "complete" = all forms done, "done" = finished
