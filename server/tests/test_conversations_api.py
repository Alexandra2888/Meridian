"""HTTP-level happy-path for the conversation endpoints.

Uses the `client` fixture (ASGI transport, no live network) and seeds rows
directly through the repo so the tests don't depend on `/chat` (which would
require an OpenAI key).
"""

from __future__ import annotations

from httpx import AsyncClient

from app.db import ConversationRepo, session_scope


async def _seed(learner_id: str = "stub-001") -> str:
    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get_or_create(None, learner_id)
        await repo.add_message(row.id, "user", "hello")
        await repo.add_message(
            row.id,
            "assistant",
            "hi",
            agents_invoked=["discovery"],
            latency_ms=4321,
            tokens_in=12,
            tokens_out=24,
            cost_usd=0.005,
            trace_id="trace-1",
        )
        await repo.set_step_durations(
            row.id, "trace-1", {"plan": 1000, "synthesize": 1500}
        )
        return row.id


async def test_list_conversations_empty(client: AsyncClient):
    r = await client.get("/conversations", params={"learner_id": "stub-001"})
    assert r.status_code == 200
    assert r.json() == []


async def test_list_conversations_returns_learner_rows(client: AsyncClient):
    cid = await _seed("stub-001")
    # Different learner — should not appear in the stub-001 listing.
    await _seed("stub-002")

    r = await client.get("/conversations", params={"learner_id": "stub-001"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == cid
    assert {"id", "title", "created_at", "updated_at"} <= set(rows[0].keys())


async def test_get_conversation_returns_messages_with_telemetry(client: AsyncClient):
    cid = await _seed()

    r = await client.get(f"/conversations/{cid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == cid
    assert detail["learner_id"] == "stub-001"
    assert len(detail["messages"]) == 2

    user_msg, assistant_msg = detail["messages"]
    assert user_msg["role"] == "user"
    # User rows carry no telemetry. JSON columns default to their empty
    # collection (`[]` / `{}`); numeric metrics stay null.
    assert not user_msg["agents_invoked"]
    assert user_msg["latency_ms"] is None
    assert user_msg["cost_usd"] is None
    assert not user_msg["step_durations"]

    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["agents_invoked"] == ["discovery"]
    assert assistant_msg["latency_ms"] == 4321
    # Decimal cast to float for JSON serialization.
    assert assistant_msg["cost_usd"] == 0.005
    assert assistant_msg["step_durations"] == {"plan": 1000, "synthesize": 1500}


async def test_get_conversation_404(client: AsyncClient):
    r = await client.get("/conversations/does-not-exist")
    assert r.status_code == 404


async def test_patch_title_round_trip(client: AsyncClient):
    cid = await _seed()

    r = await client.patch(
        f"/conversations/{cid}", json={"title": "Renamed by test"}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed by test"

    # Reading it back confirms persistence.
    detail = (await client.get(f"/conversations/{cid}")).json()
    assert detail["title"] == "Renamed by test"


async def test_patch_title_404(client: AsyncClient):
    r = await client.patch(
        "/conversations/does-not-exist", json={"title": "x"}
    )
    assert r.status_code == 404


async def test_patch_title_rejects_blank(client: AsyncClient):
    cid = await _seed()
    # `ConversationTitleUpdate` enforces `min_length=1`.
    r = await client.patch(f"/conversations/{cid}", json={"title": ""})
    assert r.status_code == 422


async def test_delete_conversation_lifecycle(client: AsyncClient):
    cid = await _seed()

    # Visible before.
    assert (await client.get(f"/conversations/{cid}")).status_code == 200

    r = await client.delete(f"/conversations/{cid}")
    assert r.status_code == 204
    assert r.content == b""

    # 404 after; listing for the learner is empty.
    assert (await client.get(f"/conversations/{cid}")).status_code == 404
    rows = (
        await client.get("/conversations", params={"learner_id": "stub-001"})
    ).json()
    assert rows == []


async def test_delete_conversation_404(client: AsyncClient):
    r = await client.delete("/conversations/does-not-exist")
    assert r.status_code == 404


async def test_health_and_learner_endpoints_still_work(client: AsyncClient):
    # Smoke the surrounding chrome — the sidebar feature shouldn't have
    # disturbed these.
    health = (await client.get("/health")).json()
    assert health["status"] == "ok"
    assert health["crm_provider"] == "stub"

    learners = (await client.get("/learners")).json()
    assert isinstance(learners, list) and len(learners) > 0
    assert {"learner_id", "name", "enrolment_status"} <= set(learners[0].keys())
