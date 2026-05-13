"""Orchestrator state.

LangGraph runs the Discovery and Career agents in parallel when both are
selected by the planner (RFC §4.3). Fields that may be written by multiple
parallel branches use reducers so the merges are well-defined.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict


class OrchestratorState(TypedDict, total=False):
    # Identity
    learner_id: str
    conversation_id: str
    turn_id: str
    trace_id: str
    t_start: float

    # Inputs
    user_message: str
    history: list[dict]  # [{"role": "user"|"assistant", "content": ...}]

    # Stage outputs (serialized as plain dicts for LangGraph checkpoint safety)
    learner: dict          # LearnerProfile.model_dump()
    plan: dict             # PlanOutput.model_dump()
    discovery_out: dict | None
    career_out: dict | None

    # Final response (built progressively by the synthesis node; the SSE stream
    # carries the live tokens — this is the persisted, full text).
    final_response: str

    # Aggregates — parallel nodes contribute, hence the `add` reducers.
    agents_invoked: Annotated[list[str], add]
    cost_usd: Annotated[float, add]
    tokens_in: Annotated[int, add]
    tokens_out: Annotated[int, add]
