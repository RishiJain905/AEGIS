"""Add event streaming tables and outbox relay columns for Phase 11."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_event_streaming"
down_revision: str | None = "002_simulation_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox", sa.Column("claim_owner", sa.String(length=128), nullable=True))
    op.add_column(
        "outbox",
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("outbox", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("outbox", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox", sa.Column("redis_message_id", sa.String(length=128), nullable=True))
    op.create_index("ix_outbox_claimed_at", "outbox", ["claimed_at"], unique=False)
    op.create_index("ix_outbox_next_retry_at", "outbox", ["next_retry_at"], unique=False)

    op.create_table(
        "consumer_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("consumer_id", sa.String(length=256), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("stream_message_id", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["domain_events.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumer_id", "event_id", name="uq_consumer_receipts_consumer_event"),
    )
    op.create_index(
        "ix_consumer_receipts_consumer_id",
        "consumer_receipts",
        ["consumer_id"],
        unique=False,
    )

    op.create_table(
        "consumer_cursors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("consumer_group", sa.String(length=128), nullable=False),
        sa.Column("consumer_name", sa.String(length=128), nullable=False),
        sa.Column("stream_key", sa.String(length=256), nullable=False),
        sa.Column("last_event_id", sa.String(length=64), nullable=False),
        sa.Column("last_run_id", sa.String(length=64), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_group",
            "consumer_name",
            "stream_key",
            name="uq_consumer_cursors_group_name_stream",
        ),
    )

    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("consumer_id", sa.String(length=256), nullable=False),
        sa.Column("stream_key", sa.String(length=256), nullable=False),
        sa.Column("stream_message_id", sa.String(length=128), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dead_letters_run_id", "dead_letters", ["run_id"], unique=False)
    op.create_index("ix_dead_letters_event_id", "dead_letters", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dead_letters_event_id", table_name="dead_letters")
    op.drop_index("ix_dead_letters_run_id", table_name="dead_letters")
    op.drop_table("dead_letters")
    op.drop_table("consumer_cursors")
    op.drop_index("ix_consumer_receipts_consumer_id", table_name="consumer_receipts")
    op.drop_table("consumer_receipts")
    op.drop_index("ix_outbox_next_retry_at", table_name="outbox")
    op.drop_index("ix_outbox_claimed_at", table_name="outbox")
    op.drop_column("outbox", "redis_message_id")
    op.drop_column("outbox", "next_retry_at")
    op.drop_column("outbox", "last_error")
    op.drop_column("outbox", "publish_attempts")
    op.drop_column("outbox", "claim_owner")
    op.drop_column("outbox", "claimed_at")
