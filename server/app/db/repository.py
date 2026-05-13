"""Repository pattern over SQLAlchemy. RFC §6.1 — the data-access layer is
shaped so the v2 Postgres migration is `DB_URL` and nothing else.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationRow, EvalRunRow, TurnRow


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

    async def add_turn(
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
    ) -> TurnRow:
        row = TurnRow(
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

    async def list_turns(self, conversation_id: str) -> list[TurnRow]:
        stmt = (
            select(TurnRow)
            .where(TurnRow.conversation_id == conversation_id)
            .order_by(TurnRow.created_at)
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
