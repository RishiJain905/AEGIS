"""Add generation artifact persistence for Phase 18."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_generation_artifacts"
down_revision: str | None = "004_asset_risk_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_artifacts",
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_ref", sa.String(length=512), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_generation_artifacts_trace_id",
        "generation_artifacts",
        ["trace_id"],
    )
    op.create_index(
        "ix_generation_artifacts_provider_id",
        "generation_artifacts",
        ["provider_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_artifacts_provider_id", table_name="generation_artifacts")
    op.drop_index("ix_generation_artifacts_trace_id", table_name="generation_artifacts")
    op.drop_table("generation_artifacts")
