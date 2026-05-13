"""CRM client interface and factory. RFC §4.6.

The orchestrator only knows about `CRMClient`; swapping HubSpot for a stub (or a
future Salesforce/Zoho client) is one config change. This is the single most
important architectural seam for the productionization story.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.schemas.learner import LearnerProfile, LearnerSummary


class CRMClient(Protocol):
    """The only contract the orchestrator depends on."""

    async def get_learner(self, learner_id: str) -> LearnerProfile: ...

    async def list_learners(self, limit: int = 25) -> list[LearnerSummary]:
        """Lightweight listing for the FE picker. Bounded so a HubSpot portal
        with many contacts doesn't blow the response."""
        ...

    async def health(self) -> bool:
        """Cheap signal for /health and the demo fallback decision."""
        ...


def degraded_profile(learner_id: str) -> LearnerProfile:
    """Returned when the CRM is down and we fall through to a degraded run.

    Synthesis sees `degraded=True` and acknowledges the missing context instead
    of inventing a profile. RFC §4.6, Risk 3 in §8.
    """

    return LearnerProfile(
        learner_id=learner_id,
        name="learner",
        email="",
        enrolment_status="prospect",
        program=None,
        interests=[],
        career_goals=[],
        country=None,
        degraded=True,
    )


@lru_cache
def get_crm_client() -> CRMClient:
    """Factory keyed on CRM_PROVIDER. Cached per-process."""

    from app.clients.crm.hubspot import HubSpotCRMClient
    from app.clients.crm.stub import StubCRMClient

    settings = get_settings()
    if settings.crm_provider == "hubspot":
        return HubSpotCRMClient(
            access_token=settings.hubspot_access_token,
            timeout_seconds=settings.hubspot_timeout_seconds,
        )
    return StubCRMClient()
