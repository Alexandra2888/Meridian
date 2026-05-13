import pytest

from app.clients.crm import StubCRMClient
from app.schemas import LearnerProfile


@pytest.mark.asyncio
async def test_stub_returns_seeded_learner():
    client = StubCRMClient()
    profile = await client.get_learner("stub-003")
    assert isinstance(profile, LearnerProfile)
    assert profile.name == "Priya Subramanian"
    assert profile.enrolment_status == "enrolled"
    assert "ai" in profile.interests


@pytest.mark.asyncio
async def test_stub_falls_back_on_unknown_id():
    client = StubCRMClient()
    profile = await client.get_learner("does-not-exist")
    # Never 404s — the orchestrator should always have a profile to reason over.
    assert profile.learner_id  # any seeded learner is fine


@pytest.mark.asyncio
async def test_stub_health():
    client = StubCRMClient()
    assert await client.health() is True
