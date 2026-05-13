"""Synthesis: unify agent outputs into ONE coherent response, streamed token-by-token.

This is the only node that streams tokens to the learner. Internal agent LLM
calls are non-streaming — they produce structured outputs the orchestrator
consumes, and learners never see them raw (RFC §4.7).
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.clients.llm import estimate_cost_usd, get_llm, model_for
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState

log = get_logger(__name__)


SYSTEM_PROMPT = """You are Meridian — a single, coherent voice for the learner.

You receive structured outputs from up to two specialist agents (Discovery and Career).
Your job is to write ONE warm, useful response that integrates them into a single answer.

Rules:
- Lead with the learner's actual question, not preamble.
- If both agents contributed, weave them together — don't paste two paragraphs side-by-side.
- If only one agent ran, just answer that part naturally.
- If the learner profile is `degraded` (CRM unavailable), acknowledge "I couldn't pull your profile right now" in one short sentence, then answer generally.
- Keep it concise. 4-8 sentences typically. Use a short bulleted list only when listing 3+ items.
- Stay grounded — do not invent program names or salary figures beyond what the agents provided.
- Address the learner by first name when available. Don't be overly formal.
- If the planner said `neither`, ask their clarifying question warmly.
"""


def _build_user_prompt(state: OrchestratorState) -> str:
    parts: list[str] = []
    learner = state.get("learner") or {}
    parts.append("LEARNER:\n" + json.dumps(learner, indent=0))

    plan = state.get("plan") or {}
    parts.append("PLAN:\n" + json.dumps(plan, indent=0))

    discovery = state.get("discovery_out")
    if discovery:
        parts.append("DISCOVERY OUTPUT:\n" + json.dumps(discovery, indent=0))

    career = state.get("career_out")
    if career:
        parts.append("CAREER OUTPUT:\n" + json.dumps(career, indent=0))

    parts.append("LEARNER MESSAGE:\n" + state["user_message"])
    parts.append("Write the unified response now.")
    return "\n\n".join(parts)


async def synthesize(state: OrchestratorState, config: RunnableConfig) -> dict:
    llm = get_llm("synthesizer", streaming=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=_build_user_prompt(state)),
    ]

    # Tag the call so the /chat handler can filter `on_chat_model_stream` events
    # to ONLY this node's tokens (RFC §4.7).
    existing_tags = list(config.get("tags", []) if config else [])
    cfg: RunnableConfig = {**(config or {}), "tags": [*existing_tags, "synthesis"]}

    chunks: list[str] = []
    async for chunk in llm.astream(messages, config=cfg):
        # `chunk.content` may be str or a list[dict] for tool-call style payloads.
        content = chunk.content if isinstance(chunk.content, str) else ""
        if content:
            chunks.append(content)

    final = "".join(chunks)

    approx_in = sum(len(m.content) for m in messages) // 4
    approx_out = len(final) // 4
    cost = estimate_cost_usd(model_for("synthesizer"), approx_in, approx_out)

    log.info("synthesize", chars=len(final))
    return {
        "final_response": final,
        "tokens_in": approx_in,
        "tokens_out": approx_out,
        "cost_usd": cost,
    }
