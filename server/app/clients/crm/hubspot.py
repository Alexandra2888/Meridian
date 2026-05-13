"""HubSpot CRM client. RFC §4.6.

Field mapping (HubSpot Contact properties → LearnerProfile):

    learner_id        ← hs_object_id
    name              ← firstname + lastname
    email             ← email
    enrolment_status  ← meridian_enrolment_status   (custom dropdown)
    program           ← meridian_program            (custom single-line text)
    interests         ← meridian_interests          (custom multi-checkbox, comma-sep)
    career_goals      ← meridian_career_goals       (custom multi-line text, comma-sep)
    country           ← country                     (standard property)

Resilience:
    - 5s per-call timeout (HubSpot p99 ~1s; tail latency exists)
    - exp-backoff retry on 429 / 5xx, max 2 retries
    - circuit breaker: 3 consecutive failures → 30s open → degraded mode
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from hubspot import HubSpot
from hubspot.crm.contacts.exceptions import ApiException
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.clients.crm.base import degraded_profile
from app.schemas.learner import EnrolmentStatus, LearnerProfile

log = structlog.get_logger(__name__)


CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "country",
    "meridian_enrolment_status",
    "meridian_program",
    "meridian_interests",
    "meridian_career_goals",
]

_CB_OPEN_SECONDS = 30.0
_CB_FAILURE_THRESHOLD = 3


def _is_retryable(exc: BaseException) -> bool:
    """429 and 5xx are retryable; everything else is not."""

    if isinstance(exc, ApiException):
        # HubSpot SDK exposes status as an int attribute
        status = getattr(exc, "status", None)
        return status == 429 or (isinstance(status, int) and 500 <= status < 600)
    # Network-level (timeout, connection reset) are also retryable
    return isinstance(exc, asyncio.TimeoutError | ConnectionError)


@dataclass
class _CircuitBreaker:
    failures: int = 0
    opened_at: float | None = field(default=None)

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= _CB_FAILURE_THRESHOLD:
            self.opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= _CB_OPEN_SECONDS:
            # half-open: let the next call try
            self.opened_at = None
            self.failures = 0
            return False
        return True


def _enrolment(value: str | None) -> EnrolmentStatus:
    """Coerce HubSpot's free-form value into our enum."""

    v = (value or "").strip().lower()
    if v in {"prospect", "applied", "enrolled", "graduated"}:
        return v  # type: ignore[return-value]
    return "prospect"


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _to_profile(contact_id: str, props: dict[str, Any]) -> LearnerProfile:
    first = (props.get("firstname") or "").strip()
    last = (props.get("lastname") or "").strip()
    name = f"{first} {last}".strip() or "learner"
    return LearnerProfile(
        learner_id=contact_id,
        name=name,
        email=props.get("email") or "",
        enrolment_status=_enrolment(props.get("meridian_enrolment_status")),
        program=props.get("meridian_program") or None,
        interests=_split_csv(props.get("meridian_interests")),
        career_goals=_split_csv(props.get("meridian_career_goals")),
        country=props.get("country") or None,
    )


class HubSpotCRMClient:
    def __init__(self, access_token: str, timeout_seconds: float = 5.0) -> None:
        if not access_token:
            log.warning("hubspot_token_missing — calls will 401 until token is set")
        self._client = HubSpot(access_token=access_token)
        self._timeout = timeout_seconds
        self._cb = _CircuitBreaker()

    async def get_learner(self, learner_id: str) -> LearnerProfile:
        if self._cb.is_open():
            log.warning("crm_circuit_open", learner_id=learner_id)
            return degraded_profile(learner_id)

        try:
            contact = await self._fetch_contact(learner_id)
        except Exception as exc:  # noqa: BLE001 — circuit-breaker boundary
            self._cb.record_failure()
            log.warning(
                "crm_call_failed",
                learner_id=learner_id,
                exc_type=type(exc).__name__,
                consecutive_failures=self._cb.failures,
            )
            return degraded_profile(learner_id)

        self._cb.record_success()
        props = getattr(contact, "properties", {}) or {}
        return _to_profile(learner_id, props)

    async def health(self) -> bool:
        if self._cb.is_open():
            return False
        # Lightweight: list 1 contact. Doesn't matter what comes back.
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._client.crm.contacts.basic_api.get_page, limit=1),
                timeout=self._timeout,
            )
        except Exception:  # noqa: BLE001
            return False
        return True

    async def _fetch_contact(self, learner_id: str) -> Any:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),  # initial + 2 retries
            wait=wait_exponential(multiplier=0.25, min=0.25, max=2.0),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.crm.contacts.basic_api.get_by_id,
                        contact_id=learner_id,
                        properties=CONTACT_PROPERTIES,
                    ),
                    timeout=self._timeout,
                )
