# ruff: noqa: E501

"""Add Phase 22 BASTION/WARDEN proposal and policy persistence tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_bastion_warden_proposals"
down_revision: str | None = "008_oracle_hypotheses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_revisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id",
            "revision_number",
            name="uq_proposal_revision_number",
        ),
    )
    op.create_index(
        "ix_proposal_revisions_incident_created",
        "proposal_revisions",
        ["incident_id", "created_at"],
    )
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("proposal_id", sa.String(length=64), nullable=False),
        sa.Column("proposal_revision_id", sa.String(length=64), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_decisions_incident_evaluated",
        "policy_decisions",
        ["incident_id", "evaluated_at"],
    )
    op.create_index(
        "ix_policy_decisions_proposal_revision",
        "policy_decisions",
        ["proposal_id", "proposal_revision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_decisions_proposal_revision", table_name="policy_decisions")
    op.drop_index("ix_policy_decisions_incident_evaluated", table_name="policy_decisions")
    op.drop_table("policy_decisions")
    op.drop_index("ix_proposal_revisions_incident_created", table_name="proposal_revisions")
    op.drop_table("proposal_revisions")
