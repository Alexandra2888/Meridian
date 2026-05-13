"""Happy-path + edge cases for the background AI title generator.

The LLM is stubbed — we're testing the persistence + cleanup contract, not
the actual model output.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.db import ConversationRepo, session_scope
from app.orchestrator.nodes.title import generate_and_save_title


async def _seed_titleless_conversation() -> str:
    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get_or_create(None, "stub-001")
        assert row.title is None
        return row.id


def _llm_returning(content: str) -> AsyncMock:
    """Build a fake `ChatOpenAI` whose `.ainvoke` returns an AIMessage-like obj.

    The title generator only reads `resp.content`, so a `SimpleNamespace` is
    sufficient — no need to construct a real `AIMessage`.
    """

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=content))
    return llm


async def test_generate_title_persists_cleaned_value(db):
    cid = await _seed_titleless_conversation()

    # Model surrounds the title with quotes + trailing period; the generator
    # is expected to strip them.
    llm = _llm_returning('  "Career path in data analytics."  ')
    with patch("app.orchestrator.nodes.title.get_llm", return_value=llm):
        await generate_and_save_title(cid, "What jobs?", "Data analyst roles…")

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get(cid)
        assert row is not None
        assert row.title == "Career path in data analytics"


async def test_generate_title_skips_empty_response(db):
    cid = await _seed_titleless_conversation()

    llm = _llm_returning("   ")  # whitespace only after stripping → empty
    with patch("app.orchestrator.nodes.title.get_llm", return_value=llm):
        await generate_and_save_title(cid, "Q", "A")

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get(cid)
        assert row is not None
        assert row.title is None


async def test_generate_title_swallows_llm_errors(db):
    cid = await _seed_titleless_conversation()

    failing_llm = AsyncMock()
    failing_llm.ainvoke = AsyncMock(side_effect=RuntimeError("OpenAI down"))

    # No exception bubbles — title gen is a best-effort background task.
    with patch("app.orchestrator.nodes.title.get_llm", return_value=failing_llm):
        await generate_and_save_title(cid, "Q", "A")

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get(cid)
        assert row.title is None


async def test_generate_title_truncates_oversized_output(db):
    cid = await _seed_titleless_conversation()

    too_long = "A " * 200  # 400 chars; column cap is 256.
    llm = _llm_returning(too_long)
    with patch("app.orchestrator.nodes.title.get_llm", return_value=llm):
        await generate_and_save_title(cid, "Q", "A")

    async with session_scope() as session:
        repo = ConversationRepo(session)
        row = await repo.get(cid)
        assert row.title is not None
        assert len(row.title) <= 256
