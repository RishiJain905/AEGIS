# ruff: noqa: E501

"""Add Phase 25 replay snapshot manifest persistence."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_replay_snapshots"
down_revision: str | None = "010_scribe_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replay_snapshot_manifests",
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sim_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scenario_version_id", sa.String(length=128), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("projector_version", sa.String(length=64), nullable=False),
        sa.Column("workspace_version", sa.String(length=64), nullable=False),
        sa.Column("event_range_from", sa.Integer(), nullable=False),
        sa.Column("event_range_to", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("compression", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=256), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("state_digest", sa.String(length=128), nullable=False),
        sa.Column("trigger_reason", sa.String(length=64), nullable=False),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column("compatible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_replay_snapshot_manifests_run_sequence",
        ),
    )
    op.create_index(
        "ix_replay_snapshot_manifests_run_sequence",
        "replay_snapshot_manifests",
        ["run_id", "sequence"],
    )
    op.create_index(
        "ix_replay_snapshot_manifests_object_key",
        "replay_snapshot_manifests",
        ["object_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_replay_snapshot_manifests_object_key",
        table_name="replay_snapshot_manifests",
    )
    op.drop_index(
        "ix_replay_snapshot_manifests_run_sequence",
        table_name="replay_snapshot_manifests",
    )
    op.drop_table("replay_snapshot_manifests")
