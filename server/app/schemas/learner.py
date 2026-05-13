from typing import Literal

from pydantic import BaseModel, EmailStr, Field

EnrolmentStatus = Literal["prospect", "applied", "enrolled", "graduated"]


class LearnerProfile(BaseModel):
    """Canonical learner shape consumed by the orchestrator. RFC §4.6."""

    learner_id: str
    name: str
    email: str = Field(description="Learner email; not validated as EmailStr to allow stub data")
    enrolment_status: EnrolmentStatus
    program: str | None = None
    interests: list[str] = Field(default_factory=list)
    career_goals: list[str] = Field(default_factory=list)
    country: str | None = None

    # Set true when the CRM client failed and the orchestrator is running on
    # an empty profile. Surfaced in the synthesis prompt so the response can
    # acknowledge the missing context instead of pretending it was loaded.
    degraded: bool = False
