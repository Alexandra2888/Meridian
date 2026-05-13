"""Persist node — write the user turn AND the assistant turn at end of run.

Doing it here (rather than in the /chat handler) keeps state-mutation owned by
the graph and means re-running with the same trace_id is a single rollback.
"""

from __future__ import annotations

import time

from app.db import ConversationRepo, session_scope
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState

log = get_logger(__name__)


async def persist(state: OrchestratorState) -> dict:
    conversation_id = state["conversation_id"]
    turn_id = state["turn_id"]
    learner_id = state["learner_id"]
    t_start = state.get("t_start") or time.monotonic()
    latency_ms = int((time.monotonic() - t_start) * 1000)
    agents = state.get("agents_invoked", [])

    async with session_scope() as session:
        repo = ConversationRepo(session)
        await repo.get_or_create(conversation_id, learner_id)

        # Persist the learner's turn first.
        await repo.add_turn(
            conversation_id=conversation_id,
            role="user",
            content=state["user_message"],
        )

        # Then the assistant turn with all the metadata that powers the
        # observability dashboard once one exists (RFC §6.2).
        await repo.add_turn(
            conversation_id=conversation_id,
            role="assistant",
            content=state.get("final_response", ""),
            agents_invoked=agents,
            latency_ms=latency_ms,
            tokens_in=state.get("tokens_in", 0),
            tokens_out=state.get("tokens_out", 0),
            cost_usd=state.get("cost_usd", 0.0),
            trace_id=state.get("trace_id"),
        )

    log.info(
        "persist",
        conversation_id=conversation_id,
        turn_id=turn_id,
        agents=agents,
        latency_ms=latency_ms,
        cost_usd=round(state.get("cost_usd", 0.0), 6),
    )
    return {}
