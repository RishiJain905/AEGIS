"""Add asset risk score persistence for Phase 17."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_asset_risk_scores"
down_revision: str | None = "003_event_streaming"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_risk_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=256), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "sequence",
            name="uq_asset_risk_scores_run_asset_sequence",
        ),
    )
    op.create_index(
        "ix_asset_risk_scores_run_id",
        "asset_risk_scores",
        ["run_id"],
    )
    op.create_index(
        "ix_asset_risk_scores_dedup",
        "asset_risk_scores",
        ["run_id", "deduplication_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_risk_scores_dedup", table_name="asset_risk_scores")
    op.drop_index("ix_asset_risk_scores_run_id", table_name="asset_risk_scores")
    op.drop_table("asset_risk_scores")
