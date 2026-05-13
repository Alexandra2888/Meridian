"""Persist node — write the user message AND the assistant message at end of run.

Doing it here (rather than in the /chat handler) keeps state-mutation owned by
the graph and means re-running with the same trace_id is a single rollback.
"""

from __future__ import annotations

import asyncio
import time

from app.db import ConversationRepo, session_scope
from app.observability import get_logger
from app.orchestrator.nodes.title import generate_and_save_title
from app.orchestrator.state import OrchestratorState

log = get_logger(__name__)


async def persist(state: OrchestratorState) -> dict:
    conversation_id = state["conversation_id"]
    message_id = state["message_id"]
    learner_id = state["learner_id"]
    user_message = state["user_message"]
    assistant_message = state.get("final_response", "") or ""
    t_start = state.get("t_start") or time.monotonic()
    latency_ms = int((time.monotonic() - t_start) * 1000)
    agents = state.get("agents_invoked", [])

    needs_title = False
    async with session_scope() as session:
        repo = ConversationRepo(session)
        conversation = await repo.get_or_create(conversation_id, learner_id)
        needs_title = conversation.title is None

        # Persist the learner's message first.
        await repo.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )

        # Then the assistant message with all the metadata that powers the
        # observability dashboard once one exists (RFC §6.2).
        await repo.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_message,
            agents_invoked=agents,
            latency_ms=latency_ms,
            tokens_in=state.get("tokens_in", 0),
            tokens_out=state.get("tokens_out", 0),
            cost_usd=state.get("cost_usd", 0.0),
            trace_id=state.get("trace_id"),
        )

        # `onupdate` only fires when other columns of `conversations` change —
        # bump `updated_at` so the sidebar's recency ordering is correct.
        await repo.touch(conversation_id)

    if needs_title and user_message.strip() and assistant_message.strip():
        # Fire-and-forget so the SSE stream closes immediately; the FE polls
        # via a follow-up `router.refresh()` to pick up the title.
        asyncio.create_task(
            generate_and_save_title(conversation_id, user_message, assistant_message)
        )

    log.info(
        "persist",
        conversation_id=conversation_id,
        message_id=message_id,
        agents=agents,
        latency_ms=latency_ms,
        cost_usd=round(state.get("cost_usd", 0.0), 6),
    )
    return {}
