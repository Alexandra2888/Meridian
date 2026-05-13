"""Happy-path tests for `ConversationRepo` — the data-access layer that backs
the sidebar + chat history endpoints.

Hits the in-memory SQLite engine wired up by the `db` fixture in conftest.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from app.db import ConversationRepo, session_scope


async def _seed_conversation(learner_id: str = "stub-001") -> str:
    """Create a conversation with a user + assistant message; return its id."""

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get_or_create(None, learner_id)
        await repo.add_message(row.id, "user", "hello")
        await repo.add_message(
            row.id,
            "assistant",
            "hi back",
            agents_invoked=["discovery"],
            latency_ms=1234,
            tokens_in=10,
            tokens_out=20,
            cost_usd=0.0123,
            trace_id="trace-abc",
        )
        return row.id


async def test_get_or_create_inserts_then_returns_existing(db):
    async with session_scope() as session:
        repo = ConversationRepo(session)
        row1 = await repo.get_or_create(None, "stub-001")
        assert row1.id
        assert row1.learner_id == "stub-001"
        assert row1.title is None

        # Passing the id we just got back returns the same row (no insert).
        row2 = await repo.get_or_create(row1.id, "stub-001")
        assert row2.id == row1.id


async def test_add_message_then_list_orders_by_created_at(db):
    cid = await _seed_conversation()

    async with session_scope() as session:
        repo = ConversationRepo(session)
        msgs = await repo.list_messages(cid)
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[1].agents_invoked == ["discovery"]
        assert msgs[1].latency_ms == 1234
        assert msgs[1].cost_usd == Decimal("0.012300")
        assert msgs[1].trace_id == "trace-abc"


async def test_list_by_learner_recent_first_and_scoped(db):
    older = await _seed_conversation("stub-001")
    # Ensure a measurable updated_at gap — SQLite stores microseconds but
    # we don't want monotonic-clock races on very fast machines.
    await asyncio.sleep(0.01)
    newer = await _seed_conversation("stub-001")
    # A different learner's conversation must not leak.
    other = await _seed_conversation("stub-002")

    async with session_scope() as session:
        repo = ConversationRepo(session)
        rows = await repo.list_by_learner("stub-001")
        ids = [r.id for r in rows]
        assert ids == [newer, older]
        assert other not in ids


async def test_update_title_and_then_get(db):
    cid = await _seed_conversation()

    async with session_scope() as session:
        repo = ConversationRepo(session)
        updated = await repo.update_title(cid, "A nice title")
        assert updated is not None
        assert updated.title == "A nice title"

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get(cid)
        assert row is not None
        assert row.title == "A nice title"


async def test_update_title_returns_none_for_missing(db):
    async with session_scope() as session:
        repo = ConversationRepo(session)
        result = await repo.update_title("does-not-exist", "x")
        assert result is None


async def test_touch_bumps_updated_at(db):
    cid = await _seed_conversation()

    async with session_scope() as session:
        repo = ConversationRepo(session)
        before = (await repo.get(cid)).updated_at

    await asyncio.sleep(0.01)

    async with session_scope() as session:
        repo = ConversationRepo(session)
        await repo.touch(cid)

    async with session_scope() as session:
        repo = ConversationRepo(session)
        after = (await repo.get(cid)).updated_at

    assert after > before


async def test_delete_cascades_messages(db):
    cid = await _seed_conversation()

    async with session_scope() as session:
        repo = ConversationRepo(session)
        assert len(await repo.list_messages(cid)) == 2

        deleted = await repo.delete(cid)
        assert deleted is True

    async with session_scope() as session:
        repo = ConversationRepo(session)
        assert await repo.get(cid) is None
        # ON DELETE CASCADE wipes the messages too.
        assert await repo.list_messages(cid) == []


async def test_delete_returns_false_for_missing(db):
    async with session_scope() as session:
        repo = ConversationRepo(session)
        assert await repo.delete("does-not-exist") is False


async def test_set_step_durations_matches_by_trace_id(db):
    cid = await _seed_conversation()

    async with session_scope() as session:
        repo = ConversationRepo(session)
        await repo.set_step_durations(
            cid, "trace-abc", {"plan": 1100, "synthesize": 1400}
        )

    async with session_scope() as session:
        repo = ConversationRepo(session)
        msgs = await repo.list_messages(cid)
        # Only the assistant row (trace-abc) gets the durations; the user row
        # remains untouched.
        assistant = next(m for m in msgs if m.role == "assistant")
        user = next(m for m in msgs if m.role == "user")
        assert assistant.step_durations == {"plan": 1100, "synthesize": 1400}
        assert not user.step_durations
