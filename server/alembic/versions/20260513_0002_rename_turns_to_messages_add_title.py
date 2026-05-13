"""rename turns→messages; add conversations.title + conversations.updated_at

Revision ID: 20260513_0002
Revises: 20260513_0001
Create Date: 2026-05-13

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0002"
down_revision: str | Sequence[str] | None = "20260513_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Dev safeguard: SQLAlchemy's `init_db()` runs `Base.metadata.create_all`
    # on app startup, and once the model class was renamed `MessageRow` →
    # table "messages", an empty `messages` table may already exist alongside
    # `turns`. Drop it so the rename succeeds. Production environments that
    # only run migrations will have no `messages` table at this point.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "messages" in inspector.get_table_names():
        op.drop_table("messages")
        # Re-inspect — drop_table also removes its indexes from the catalog.
        inspector = sa.inspect(bind)

    # SQLite needs the index dropped/recreated around the rename. Postgres
    # carries indexes through `rename_table` but it costs nothing to be explicit.
    turns_indexes = {ix["name"] for ix in inspector.get_indexes("turns")}
    if "ix_turns_conversation_id" in turns_indexes:
        op.drop_index("ix_turns_conversation_id", table_name="turns")
    op.rename_table("turns", "messages")
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.add_column(
        "conversations",
        sa.Column("title", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill so the new `updated_at` is comparable for sorting.
    op.execute("UPDATE conversations SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_column("conversations", "updated_at")
    op.drop_column("conversations", "title")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.rename_table("messages", "turns")
    op.create_index("ix_turns_conversation_id", "turns", ["conversation_id"])
