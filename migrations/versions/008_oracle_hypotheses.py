# ruff: noqa: E501

"""Add Phase 21 ORACLE hypothesis persistence tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_oracle_hypotheses"
down_revision: str | None = "007_investigation_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hypothesis_revisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["hypotheses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hypothesis_id",
            "revision_number",
            name="uq_hypothesis_revision_number",
        ),
    )
    op.create_index(
        "ix_hypothesis_revisions_incident_created",
        "hypothesis_revisions",
        ["incident_id", "created_at"],
    )
    op.create_table(
        "hypothesis_comparisons",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hypothesis_comparisons_incident_created",
        "hypothesis_comparisons",
        ["incident_id", "created_at"],
    )
    op.create_table(
        "verification_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["hypotheses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incident_id",
            "idempotency_key",
            name="uq_verification_incident_idempotency",
        ),
    )
    op.create_index(
        "ix_verification_requests_incident_created",
        "verification_requests",
        ["incident_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_verification_requests_incident_created", table_name="verification_requests")
    op.drop_table("verification_requests")
    op.drop_index("ix_hypothesis_comparisons_incident_created", table_name="hypothesis_comparisons")
    op.drop_table("hypothesis_comparisons")
    op.drop_index("ix_hypothesis_revisions_incident_created", table_name="hypothesis_revisions")
    op.drop_table("hypothesis_revisions")
