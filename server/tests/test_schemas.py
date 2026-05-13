from app.schemas import (
    ChatRequest,
    DiscoveryAgentOutput,
    FinalEvent,
    LearnerProfile,
    PlanOutput,
)


def test_learner_profile_defaults():
    p = LearnerProfile(
        learner_id="x",
        name="X",
        email="x@example.com",
        enrolment_status="prospect",
    )
    assert p.interests == []
    assert p.degraded is False


def test_plan_output_confidence_bounds():
    p = PlanOutput(route="both", confidence=0.7, rationale="r")
    assert 0 <= p.confidence <= 1


def test_chat_request_defaults():
    r = ChatRequest(learner_id="abc", message="hi")
    assert r.conversation_id is None
    assert r.history == []


def test_discovery_agent_output_citations_optional():
    out = DiscoveryAgentOutput(program_recommendations=["BBA"], reasoning="...")
    assert out.citations == []


def test_final_event_serializes_event_field():
    f = FinalEvent(
        total_latency_ms=1234,
        cost_usd=0.0021,
        tokens_in=10,
        tokens_out=20,
        conversation_id="c",
        turn_id="t",
    )
    assert f.model_dump()["event"] == "final"
