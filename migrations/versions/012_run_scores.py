# ruff: noqa: E501

"""Add Phase 29 run score persistence."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_run_scores"
down_revision: str | None = "011_replay_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_scores",
        sa.Column("score_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("integrity_checksum", sa.String(length=128), nullable=False),
        sa.Column("input_checksum", sa.String(length=128), nullable=False),
        sa.Column("scenario_version", sa.String(length=64), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("grading_engine_version", sa.String(length=64), nullable=False),
        sa.Column("event_sequence_from", sa.Integer(), nullable=False),
        sa.Column("event_sequence_to", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("grade", sa.String(length=8), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("score_id"),
        sa.UniqueConstraint("fingerprint", name="uq_run_scores_fingerprint"),
    )
    op.create_index(
        "ix_run_scores_run_created",
        "run_scores",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_scores_run_created", table_name="run_scores")
    op.drop_table("run_scores")
