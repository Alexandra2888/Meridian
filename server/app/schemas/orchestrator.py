from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["discovery", "career"]
Route = Literal["discovery", "career", "both", "neither"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    learner_id: str = Field(description="Learner ID; HubSpot contact id when CRM_PROVIDER=hubspot")
    message: str
    conversation_id: str | None = Field(
        default=None,
        description="Server creates one when null. Pass the prior id to continue a thread.",
    )
    history: list[ChatMessage] = Field(default_factory=list)


class PlanOutput(BaseModel):
    """Structured planner output. Drives conditional routing in the graph."""

    route: Route
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(description="One sentence — why this route")
    clarifying_question: str | None = Field(
        default=None,
        description="Set only when route=neither and confidence is low; the FE can render it.",
    )


class DiscoveryAgentOutput(BaseModel):
    program_recommendations: list[str] = Field(
        description="Program names from the catalog ranked best-fit first"
    )
    reasoning: str
    citations: list[str] = Field(default_factory=list, description="Program IDs used as evidence")


class CareerAgentOutput(BaseModel):
    job_outcomes: list[str] = Field(description="Concrete roles graduates of the program take")
    market_notes: str
    citations: list[str] = Field(default_factory=list, description="Career record IDs cited")
