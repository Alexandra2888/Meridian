"""SSE plumbing: translate LangGraph's `astream_events(v2)` into the wire
protocol the frontend consumes (RFC §4.7).

Five event types are emitted: status, delta, error, final, done.

The handler intentionally only forwards `on_chat_model_stream` events that the
synthesis node tagged — internal agent LLM calls remain invisible to the client.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.db import ConversationRepo, session_scope
from app.observability import get_logger, new_trace_id
from app.orchestrator import get_graph
from app.orchestrator.graph import NODE_NAMES
from app.schemas import (
    ChatRequest,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    FinalEvent,
    StatusEvent,
)

log = get_logger(__name__)


def _sse_frame(event: str, data: dict) -> str:
    """SSE wire format: `event: <name>\\ndata: <json>\\n\\n`."""

    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def chat_event_stream(req: ChatRequest) -> AsyncIterator[str]:
    graph = get_graph()
    trace_id = new_trace_id()
    conversation_id = req.conversation_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    t_start = time.monotonic()

    initial_state: dict[str, Any] = {
        "learner_id": req.learner_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "trace_id": trace_id,
        "t_start": t_start,
        "user_message": req.message,
        "history": [t.model_dump() for t in req.history],
        "agents_invoked": [],
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
    }

    # Per-node timing. on_chain_start sets the start; on_chain_end computes ms.
    node_started_at: dict[str, float] = {}
    # Collected per-node durations; persisted after the graph completes so the
    # agent-trace panel survives a reload.
    step_durations: dict[str, int] = {}

    final_state: dict[str, Any] = {}

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            name = event.get("name")
            tags = event.get("tags") or []

            if kind == "on_chain_start" and name in NODE_NAMES:
                node_started_at[name] = time.monotonic()
                yield _sse_frame(
                    "status",
                    StatusEvent(node=name, status="started").model_dump(),
                )

            elif kind == "on_chain_end" and name in NODE_NAMES:
                t0 = node_started_at.pop(name, time.monotonic())
                duration_ms = int((time.monotonic() - t0) * 1000)
                step_durations[name] = duration_ms
                yield _sse_frame(
                    "status",
                    StatusEvent(
                        node=name, status="finished", duration_ms=duration_ms
                    ).model_dump(),
                )
                # Capture the final aggregated state from the terminal node.
                if name == "persist":
                    final_state = event.get("data", {}).get("input", {}) or final_state

            elif kind == "on_chat_model_stream" and "synthesis" in tags:
                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield _sse_frame("delta", DeltaEvent(content=content).model_dump())

        # Fall back to the latest snapshot if `persist` didn't surface it.
        if not final_state:
            # Re-run is not desirable here; use the seed dict so at least the
            # ids are present. Token counts will be zero in this edge case.
            final_state = initial_state

        # Persist per-node durations onto the assistant message we just wrote.
        # Best-effort: a DB hiccup here mustn't break the SSE stream.
        if step_durations:
            try:
                async with session_scope() as session:
                    repo = ConversationRepo(session)
                    await repo.set_step_durations(
                        conversation_id, trace_id, step_durations
                    )
            except Exception:  # noqa: BLE001
                log.warning("step_durations_persist_failed", trace_id=trace_id)

        total_latency_ms = int((time.monotonic() - t_start) * 1000)
        final_payload = FinalEvent(
            agents_invoked=final_state.get("agents_invoked", []) or [],
            total_latency_ms=total_latency_ms,
            cost_usd=round(float(final_state.get("cost_usd", 0.0)), 6),
            tokens_in=int(final_state.get("tokens_in", 0)),
            tokens_out=int(final_state.get("tokens_out", 0)),
            conversation_id=conversation_id,
            message_id=message_id,
            learner=final_state.get("learner"),
        )
        yield _sse_frame("final", final_payload.model_dump())
        yield _sse_frame("done", DoneEvent().model_dump())

    except asyncio.CancelledError:
        log.info("chat_stream_cancelled", trace_id=trace_id)
        raise

    except Exception as exc:  # noqa: BLE001 — last-resort wire-level error
        log.exception("chat_stream_failed", trace_id=trace_id)
        yield _sse_frame(
            "error",
            ErrorEvent(message=str(exc), recoverable=False).model_dump(),
        )
        yield _sse_frame("done", DoneEvent().model_dump())
