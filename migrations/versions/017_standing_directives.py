# ruff: noqa: E501

"""Standing directives (Phase 7): persistent operator taskings.

A standing directive is a persistent operator tasking ("monitor the logistics zone
network") re-evaluated by the autonomy loop when new matching evidence lands. Adds the
``agent_directives`` table: the JSONB ``payload`` carries the StandingDirectiveV1 identity;
``run_id`` + ``active`` columns back the poller's active-directive query per run.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017_standing_directives"
down_revision: str | None = "016_run_scoped_agent_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_directives",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_agent_directives_run_active",
        "agent_directives",
        ["run_id", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_directives_run_active", table_name="agent_directives")
    op.drop_table("agent_directives")
