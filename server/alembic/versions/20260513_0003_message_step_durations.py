"""add messages.step_durations

Revision ID: 20260513_0003
Revises: 20260513_0002
Create Date: 2026-05-13

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0003"
down_revision: str | Sequence[str] | None = "20260513_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("messages")}
    if "step_durations" not in existing:
        op.add_column(
            "messages",
            sa.Column("step_durations", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("messages", "step_durations")
