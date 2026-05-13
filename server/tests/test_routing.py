"""The routing function is pure — no LLM call. Verify each plan output maps to
the expected fan-out target."""

from __future__ import annotations

from app.orchestrator.graph import _route_from_plan


def _state(route: str) -> dict:
    return {"plan": {"route": route}}


def test_discovery_only():
    assert _route_from_plan(_state("discovery")) == ["discovery_agent"]


def test_career_only():
    assert _route_from_plan(_state("career")) == ["career_agent"]


def test_both_fans_out_parallel():
    assert _route_from_plan(_state("both")) == ["discovery_agent", "career_agent"]


def test_neither_routes_to_synthesize():
    # `neither` still goes through synthesize so the clarifying question is
    # delivered via the same SSE protocol as a normal answer.
    assert _route_from_plan(_state("neither")) == ["synthesize"]


def test_unknown_route_safe_default():
    assert _route_from_plan({"plan": {}}) == ["synthesize"]
