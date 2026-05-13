"""Test bootstrap.

Sets the environment so config loading succeeds without a real `.env`,
provides a fresh in-memory DB per test, and an ASGI `AsyncClient` bound to
that DB. We sidestep FastAPI's lifespan on purpose — the `db` fixture owns
engine init/teardown so tests stay hermetic.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# These need to land BEFORE app modules import the config.
os.environ.setdefault("CRM_PROVIDER", "stub")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db import session as _session_module
from app.db.models import Base


@pytest.fixture
async def db() -> AsyncIterator[None]:
    """Per-test in-memory SQLite engine, injected into the global session module.

    `StaticPool` keeps every session checkout on the same connection — required
    for `:memory:`, since each fresh connection opens its own empty database.
    """

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # Match production's session.py — without this PRAGMA, SQLite ignores
    # the ON DELETE CASCADE on `messages.conversation_id`.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    # Swap into the module so `session_scope()` and `get_sessionmaker()` see
    # the test engine instead of raising "DB engine not initialized".
    _session_module._engine = engine
    _session_module._sessionmaker = sessionmaker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        await engine.dispose()
        _session_module._engine = None
        _session_module._sessionmaker = None


@pytest.fixture
async def client(db: None) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the FastAPI app *without* triggering lifespan.

    The `db` fixture has already prepared the engine, so the routes can hit
    `session_scope()` immediately.
    """

    from app.main import app  # imported lazily so config env is in place

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
