"""The HubSpot client never raises — failures trip the circuit breaker and the
orchestrator gets a degraded profile. Verified without touching the network.
"""

from __future__ import annotations

import asyncio

import pytest

from app.clients.crm.hubspot import HubSpotCRMClient, _CB_FAILURE_THRESHOLD


class _BoomClient:
    """Stub-in for the HubSpot SDK client that raises on every call."""

    def __init__(self) -> None:
        self.crm = self
        self.contacts = self
        self.basic_api = self

    def get_by_id(self, *args, **kwargs):  # noqa: D401 — sdk-shaped
        raise ConnectionError("boom")

    def get_page(self, *args, **kwargs):
        raise ConnectionError("boom")


@pytest.mark.asyncio
async def test_failures_return_degraded_profile(monkeypatch):
    client = HubSpotCRMClient(access_token="dummy", timeout_seconds=0.05)
    client._client = _BoomClient()  # type: ignore[assignment]

    profile = await client.get_learner("123")
    assert profile.degraded is True
    assert profile.learner_id == "123"


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold():
    client = HubSpotCRMClient(access_token="dummy", timeout_seconds=0.05)
    client._client = _BoomClient()  # type: ignore[assignment]

    for _ in range(_CB_FAILURE_THRESHOLD):
        await client.get_learner("123")
    assert client._cb.is_open() is True

    # Subsequent call returns degraded without even attempting an SDK call.
    profile = await client.get_learner("123")
    assert profile.degraded is True
