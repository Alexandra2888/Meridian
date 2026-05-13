"""LangGraph wiring. RFC §4.3.

Topology:

    START
      │
      ▼
    load_context
      │
      ▼
    plan ──► route_from_plan ──┬─► discovery_agent ──┐
                               │                     ▼
                               ├─► career_agent  ──► synthesize ──► persist ──► END
                               │                     ▲
                               └─► (neither) ────────┘

`route_from_plan` returns a list of node names; LangGraph fans those out in
parallel. The reducers on OrchestratorState merge their writes safely.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.orchestrator.agents import career_agent, discovery_agent
from app.orchestrator.nodes import load_context, persist, plan, synthesize
from app.orchestrator.state import OrchestratorState

NODE_NAMES = {
    "load_context",
    "plan",
    "discovery_agent",
    "career_agent",
    "synthesize",
    "persist",
}


def _route_from_plan(
    state: OrchestratorState,
) -> list[Literal["discovery_agent", "career_agent", "synthesize"]]:
    plan_obj = state.get("plan") or {}
    route = plan_obj.get("route", "neither")
    if route == "discovery":
        return ["discovery_agent"]
    if route == "career":
        return ["career_agent"]
    if route == "both":
        # The list form is what gives us native parallel fan-out — both nodes
        # start at the same time and LangGraph waits at `synthesize` until both
        # complete.
        return ["discovery_agent", "career_agent"]
    # route == "neither" → still call synthesize so the clarifying question
    # streams through the same pipeline (single voice, same SSE protocol).
    return ["synthesize"]


def build_graph():
    sg: StateGraph = StateGraph(OrchestratorState)

    sg.add_node("load_context", load_context)
    sg.add_node("plan", plan)
    sg.add_node("discovery_agent", discovery_agent)
    sg.add_node("career_agent", career_agent)
    sg.add_node("synthesize", synthesize)
    sg.add_node("persist", persist)

    sg.add_edge(START, "load_context")
    sg.add_edge("load_context", "plan")

    sg.add_conditional_edges(
        "plan",
        _route_from_plan,
        ["discovery_agent", "career_agent", "synthesize"],
    )

    # Both agents drain into synthesize. LangGraph automatically waits for all
    # incoming parallel branches before invoking the join node.
    sg.add_edge("discovery_agent", "synthesize")
    sg.add_edge("career_agent", "synthesize")

    sg.add_edge("synthesize", "persist")
    sg.add_edge("persist", END)

    return sg.compile()


@lru_cache
def get_graph():
    return build_graph()
