"""Repository pattern over SQLAlchemy. RFC §6.1 — the data-access layer is
shaped so the v2 Postgres migration is `DB_URL` and nothing else.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConversationRow, EvalRunRow, MessageRow


class ConversationRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(
        self, conversation_id: str | None, learner_id: str
    ) -> ConversationRow:
        if conversation_id is not None:
            row = await self.session.get(ConversationRow, conversation_id)
            if row is not None:
                return row
        row = ConversationRow(learner_id=learner_id)
        if conversation_id is not None:
            row.id = conversation_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, conversation_id: str) -> ConversationRow | None:
        return await self.session.get(ConversationRow, conversation_id)

    async def get_with_messages(self, conversation_id: str) -> ConversationRow | None:
        stmt = (
            select(ConversationRow)
            .where(ConversationRow.id == conversation_id)
            .options(selectinload(ConversationRow.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_learner(
        self, learner_id: str, limit: int = 50
    ) -> list[ConversationRow]:
        stmt = (
            select(ConversationRow)
            .where(ConversationRow.learner_id == learner_id)
            .order_by(ConversationRow.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_title(
        self, conversation_id: str, title: str
    ) -> ConversationRow | None:
        row = await self.session.get(ConversationRow, conversation_id)
        if row is None:
            return None
        row.title = title
        await self.session.flush()
        return row

    async def touch(self, conversation_id: str) -> None:
        """Bump `updated_at` so the conversation rises to the top of the sidebar.

        SQLAlchemy's `onupdate` only fires when other columns change; this keeps
        recency ordering correct after a new message is added.
        """

        from datetime import UTC, datetime

        stmt = (
            update(ConversationRow)
            .where(ConversationRow.id == conversation_id)
            .values(updated_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)

    async def delete(self, conversation_id: str) -> bool:
        stmt = sa_delete(ConversationRow).where(ConversationRow.id == conversation_id)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        agents_invoked: list[str] | None = None,
        latency_ms: int | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: float | None = None,
        trace_id: str | None = None,
    ) -> MessageRow:
        row = MessageRow(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agents_invoked=agents_invoked or [],
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=Decimal(str(cost_usd)) if cost_usd is not None else None,
            trace_id=trace_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def set_step_durations(
        self,
        conversation_id: str,
        trace_id: str,
        step_durations: dict[str, int],
    ) -> None:
        """Attach per-node durations to the assistant message of this turn.

        The SSE handler computes durations as nodes finish and calls this once
        the graph has completed. We identify the row by `(conversation_id,
        trace_id)` — `trace_id` is unique per chat turn and the assistant row
        is the only one written with it.
        """

        stmt = (
            update(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
            .where(MessageRow.role == "assistant")
            .where(MessageRow.trace_id == trace_id)
            .values(step_durations=step_durations)
        )
        await self.session.execute(stmt)

    async def list_messages(self, conversation_id: str) -> list[MessageRow]:
        stmt = (
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
            .order_by(MessageRow.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class EvalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        dataset: str,
        test_case_id: str,
        passed: bool,
        score: float | None = None,
        notes: str | None = None,
        extra: dict | None = None,
    ) -> EvalRunRow:
        row = EvalRunRow(
            dataset=dataset,
            test_case_id=test_case_id,
            passed=passed,
            score=Decimal(str(score)) if score is not None else None,
            notes=notes,
            extra=extra or {},
        )
        self.session.add(row)
        await self.session.flush()
        return row
