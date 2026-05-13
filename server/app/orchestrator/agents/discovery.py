"""Discovery agent — program recommendations grounded in the catalog.

The catalog is `app/data/programs.json`. Agents are required to cite program
IDs to mitigate Risk 1 (hallucinated facts) from RFC §8.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.clients.llm import estimate_cost_usd, get_llm, model_for
from app.data import programs
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState
from app.schemas.orchestrator import DiscoveryAgentOutput

log = get_logger(__name__)


SYSTEM_PROMPT = """You are the Discovery agent for Meridian. You recommend programs from the institution's catalog.

Hard rules:
- ONLY recommend programs from the CATALOG provided below. Never invent programs.
- Cite the program IDs you used as evidence (the `id` field).
- If the learner's interests don't match any program closely, say so honestly.
- Tailor your reasoning to the learner's current enrolment_status — applicants need different framing than prospects.

Output STRICT JSON matching:
{
  "program_recommendations": ["BBA in X", "MBA in Y", ...]  // ranked best-fit first
  "reasoning": "2-4 sentences",
  "citations": ["program-id-1", "program-id-2"]
}
"""


def _format_learner(learner: dict | None) -> str:
    if not learner:
        return "No learner profile available."
    if learner.get("degraded"):
        return "(CRM lookup failed; running with no learner context.)"
    return (
        f"learner_id={learner.get('learner_id')}, name={learner.get('name')}, "
        f"status={learner.get('enrolment_status')}, program={learner.get('program')}, "
        f"interests={learner.get('interests')}, career_goals={learner.get('career_goals')}, "
        f"country={learner.get('country')}"
    )


async def discovery_agent(state: OrchestratorState, config: RunnableConfig) -> dict:
    llm = get_llm("agent").with_structured_output(DiscoveryAgentOutput, method="json_schema")

    catalog_json = json.dumps(programs(), indent=0)
    learner_block = _format_learner(state.get("learner"))

    messages = [
        SystemMessage(content=SYSTEM_PROMPT + f"\n\nCATALOG:\n{catalog_json}"),
        HumanMessage(
            content=(
                f"Learner profile: {learner_block}\n\n"
                f"Learner question: {state['user_message']}"
            )
        ),
    ]

    result: DiscoveryAgentOutput = await llm.ainvoke(messages, config=config)

    approx_in = sum(len(m.content) for m in messages) // 4
    approx_out = len(result.model_dump_json()) // 4
    cost = estimate_cost_usd(model_for("agent"), approx_in, approx_out)

    log.info(
        "discovery_agent",
        recs=result.program_recommendations,
        citations=result.citations,
    )
    return {
        "discovery_out": result.model_dump(),
        "agents_invoked": ["discovery"],
        "tokens_in": approx_in,
        "tokens_out": approx_out,
        "cost_usd": cost,
    }
