"""Career agent — job outcomes grounded in the careers catalog."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.clients.llm import estimate_cost_usd, get_llm, model_for
from app.data import careers, programs
from app.observability import get_logger
from app.orchestrator.state import OrchestratorState
from app.schemas.orchestrator import CareerAgentOutput

log = get_logger(__name__)


SYSTEM_PROMPT = """You are the Career agent for Meridian. You explain realistic career outcomes for graduates.

Hard rules:
- ONLY cite roles and figures from the CAREERS catalog provided below. Never invent salary numbers.
- Always include the salary band as-stated in the catalog when discussing a role.
- If the learner is enrolled in a specific program, prioritise the career_pathways linked to it.
- Cite the career record IDs you used as evidence.

Output STRICT JSON matching:
{
  "job_outcomes": ["Role name (band)", ...],
  "market_notes": "2-3 sentences on demand, geography, or stepping-stone framing",
  "citations": ["career-id-1", "career-id-2"]
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
        f"career_goals={learner.get('career_goals')}, country={learner.get('country')}"
    )


async def career_agent(state: OrchestratorState, config: RunnableConfig) -> dict:
    llm = get_llm("agent").with_structured_output(CareerAgentOutput, method="json_schema")

    careers_json = json.dumps(careers(), indent=0)
    programs_json = json.dumps(programs(), indent=0)
    learner_block = _format_learner(state.get("learner"))

    messages = [
        SystemMessage(
            content=(
                SYSTEM_PROMPT
                + f"\n\nCAREERS:\n{careers_json}\n\nPROGRAMS (for career_pathways linkage):\n{programs_json}"
            )
        ),
        HumanMessage(
            content=(
                f"Learner profile: {learner_block}\n\n"
                f"Learner question: {state['user_message']}"
            )
        ),
    ]

    result: CareerAgentOutput = await llm.ainvoke(messages, config=config)

    approx_in = sum(len(m.content) for m in messages) // 4
    approx_out = len(result.model_dump_json()) // 4
    cost = estimate_cost_usd(model_for("agent"), approx_in, approx_out)

    log.info(
        "career_agent",
        outcomes=result.job_outcomes,
        citations=result.citations,
    )
    return {
        "career_out": result.model_dump(),
        "agents_invoked": ["career"],
        "tokens_in": approx_in,
        "tokens_out": approx_out,
        "cost_usd": cost,
    }
