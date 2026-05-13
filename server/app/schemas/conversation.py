"""Pydantic schemas for the conversation history endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageView(BaseModel):
    """A single persisted message returned to the FE — mirrors `MessageRow`.

    The telemetry fields (`agents_invoked` … `step_durations`) are populated
    only on assistant rows; for user rows they're `None`. The frontend seeds
    its trace store from these so the agent-trace panel + cost/latency badges
    survive a page reload.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    agents_invoked: list[str] | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    step_durations: dict[str, int] | None = None

    @field_validator("cost_usd", mode="before")
    @classmethod
    def _decimal_to_float(cls, v: object) -> object:
        # SQLAlchemy returns Numeric columns as `Decimal`; cast for JSON serialization.
        return float(v) if isinstance(v, Decimal) else v


class ConversationSummary(BaseModel):
    """Sidebar row shape — title may be null until the title generator runs."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation payload for replaying into the chat view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    learner_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageView] = Field(default_factory=list)


class ConversationTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
