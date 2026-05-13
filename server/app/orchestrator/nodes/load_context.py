"""Pulls a LearnerProfile via the active CRM client.

If the call fails (HubSpot 5xx, timeout, or circuit-open) the CRM client itself
returns a degraded profile — this node never raises. The synthesis prompt sees
`degraded=True` and acknowledges the missing context.
"""

from __future__ import annotations

from app.clients.crm import get_crm_client
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState

log = get_logger(__name__)


async def load_context(state: OrchestratorState) -> dict:
    learner_id = state["learner_id"]
    crm = get_crm_client()
    profile = await crm.get_learner(learner_id)
    log.info("load_context", learner_id=learner_id, degraded=profile.degraded)
    return {"learner": profile.model_dump()}
