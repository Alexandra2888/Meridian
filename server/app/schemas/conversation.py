"""Pydantic schemas for the conversation history endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageView(BaseModel):
    """A single persisted message returned to the FE — mirrors `MessageRow`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


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
