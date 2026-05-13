"""Planner: classify the learner's intent and choose a route.

Emits a structured `PlanOutput` — `route` drives conditional edges, `confidence`
gates the clarifying-question fallback (RFC §8, Risk 2). Cheap model, low
temperature, structured output for determinism.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.clients.llm import estimate_cost_usd, get_llm, model_for
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState
from app.schemas.orchestrator import PlanOutput

log = get_logger(__name__)


SYSTEM_PROMPT = """You are the planner for Meridian, a learner orchestration layer for an online university.

Decide which specialist agents should answer the learner's message.

Available routes:
- "discovery"  → only the Discovery agent runs (program recommendations, admissions, what-to-study questions)
- "career"     → only the Career agent runs (jobs, salaries, career outcomes for graduates)
- "both"       → both agents run in parallel (compound questions touching study AND career)
- "neither"    → off-topic, empty, or you cannot tell. Set a clarifying_question.

Output STRICT JSON matching this schema:
{
  "route": "discovery" | "career" | "both" | "neither",
  "confidence": float between 0 and 1,
  "rationale": "one sentence",
  "clarifying_question": "string or null — only when route=neither"
}

Examples:
- "Which program is right for me?" → discovery
- "What jobs can I get with an MBA?" → career
- "What program suits me and what jobs will it lead to?" → both
- "What's the weather today?" → neither, clarifying_question asks them to rephrase
"""


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines = [f"- {t['role']}: {t['content']}" for t in history[-4:]]
    return "Recent conversation:\n" + "\n".join(lines) + "\n"


async def plan(state: OrchestratorState, config: RunnableConfig) -> dict:
    llm = get_llm("planner").with_structured_output(PlanOutput, method="json_schema")
    history_block = _format_history(state.get("history", []))
    user_block = f"Learner just sent: {state['user_message']}"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{history_block}{user_block}"),
    ]

    result: PlanOutput = await llm.ainvoke(messages, config=config)

    # `with_structured_output` doesn't surface token usage directly — estimate
    # conservatively from message length. Real production swaps this for
    # LangSmith's authoritative counts.
    approx_in = sum(len(m.content) for m in messages) // 4
    approx_out = len(result.model_dump_json()) // 4
    cost = estimate_cost_usd(model_for("planner"), approx_in, approx_out)

    log.info(
        "plan",
        route=result.route,
        confidence=result.confidence,
        rationale=result.rationale,
    )
    return {
        "plan": result.model_dump(),
        "tokens_in": approx_in,
        "tokens_out": approx_out,
        "cost_usd": cost,
    }
