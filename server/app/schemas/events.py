"""SSE event payloads emitted by /chat. RFC §4.7."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.orchestrator import AgentName


class StatusEvent(BaseModel):
    event: Literal["status"] = "status"
    node: str
    status: Literal["started", "finished"]
    duration_ms: int | None = None


class DeltaEvent(BaseModel):
    event: Literal["delta"] = "delta"
    content: str


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    message: str
    recoverable: bool = False


class FinalEvent(BaseModel):
    event: Literal["final"] = "final"
    agents_invoked: list[AgentName] = Field(default_factory=list)
    total_latency_ms: int
    cost_usd: float
    tokens_in: int
    tokens_out: int
    conversation_id: str
    turn_id: str
    learner: dict | None = Field(
        default=None, description="Snapshot of LearnerProfile shown to the FE context card"
    )


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"


SSEEvent = StatusEvent | DeltaEvent | ErrorEvent | FinalEvent | DoneEvent
