"""LLM factory — single config seam for model selection. RFC §4.5.

Every node asks for a role (`planner`, `agent`, `synthesizer`); the factory
returns a configured ChatOpenAI. Switching models or providers happens here,
not in the orchestrator.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_openai import ChatOpenAI

from app.config import get_settings

Role = Literal["planner", "agent", "synthesizer"]


# OpenAI pricing in USD per 1M tokens (input, output) as of 2025-2026.
# These are deliberately co-located with the factory so swapping a model
# updates pricing in the same edit. Update when OpenAI revises pricing.
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
}


def _temperature_for(role: Role) -> float:
    # Planner needs to be deterministic — routing accuracy is the eval metric.
    # Synthesizer benefits from a touch of variety.
    return {"planner": 0.0, "agent": 0.2, "synthesizer": 0.4}[role]


@lru_cache
def get_llm(role: Role, streaming: bool = False) -> ChatOpenAI:
    settings = get_settings()
    model = {
        "planner": settings.model_planner,
        "agent": settings.model_agent,
        "synthesizer": settings.model_synthesizer,
    }[role]
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=_temperature_for(role),
        streaming=streaming,
        timeout=30,
        max_retries=2,
    )


def model_for(role: Role) -> str:
    settings = get_settings()
    return {
        "planner": settings.model_planner,
        "agent": settings.model_agent,
        "synthesizer": settings.model_synthesizer,
    }[role]


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Best-effort per-call cost from token counts. Returns 0 if model unknown."""

    if model not in _PRICING:
        return 0.0
    in_price, out_price = _PRICING[model]
    return (tokens_in / 1_000_000) * in_price + (tokens_out / 1_000_000) * out_price
