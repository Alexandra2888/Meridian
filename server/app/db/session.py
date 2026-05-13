"""Async engine + sessionmaker, lifespan-managed from app.main.

`init_db()` is the dev convenience that ensures tables exist when running with
SQLite locally without an explicit `alembic upgrade head` step. In CI and
production the Alembic migrations are the canonical schema source.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.db.models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def create_engine_and_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    url = settings.db_url

    # For local SQLite, ensure the parent dir exists; the file is created lazily.
    if url.startswith("sqlite") and "///" in url:
        file_part = url.split("///", 1)[1]
        if file_part and not file_part.startswith(":memory:"):
            Path(file_part).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(url, future=True, pool_pre_ping=True)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, sm


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB engine not initialized — did app lifespan run?")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("DB sessionmaker not initialized — did app lifespan run?")
    return _sessionmaker


async def init_db() -> None:
    """Create tables if they don't exist. Idempotent; safe for SQLite dev."""

    global _engine, _sessionmaker
    if _engine is None:
        _engine, _sessionmaker = create_engine_and_sessionmaker()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
