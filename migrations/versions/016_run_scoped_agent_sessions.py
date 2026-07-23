# ruff: noqa: E501

"""Run-scope agent sessions/tasks (nullable incident, required run_id).

Phase 3 (AI copilot) lets an operator task the defensive agents against a live
run *before* any incident exists, so an agent session/task must anchor to a run
and carry a nullable incident. Adds ``run_id`` (NOT NULL, FK runs) to
``agent_sessions`` and ``agent_tasks``, backfills it from the owning incident for
existing rows (both the query column and the JSONB payload's ``runId``), and
relaxes ``incident_id`` to nullable. See ADR 0035.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_run_scoped_agent_sessions"
down_revision: str | None = "015_password_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- agent_sessions ---------------------------------------------------
    op.add_column(
        "agent_sessions",
        sa.Column("run_id", sa.String(length=64), nullable=True),
    )
    # Backfill run_id from the owning incident (incident_id was NOT NULL before).
    op.execute(
        sa.text(
            "UPDATE agent_sessions AS s "
            "SET run_id = i.run_id "
            "FROM incidents AS i "
            "WHERE s.incident_id = i.id AND s.run_id IS NULL"
        )
    )
    # Keep the JSONB payload (source of AgentSessionV1 identity) consistent.
    op.execute(
        sa.text(
            "UPDATE agent_sessions "
            "SET payload = jsonb_set(payload, '{runId}', to_jsonb(cast(run_id as text))) "
            "WHERE run_id IS NOT NULL"
        )
    )
    op.alter_column("agent_sessions", "run_id", nullable=False)
    op.create_foreign_key(
        "fk_agent_sessions_run_id",
        "agent_sessions",
        "runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_agent_sessions_run_created",
        "agent_sessions",
        ["run_id", "created_at"],
    )
    op.alter_column("agent_sessions", "incident_id", nullable=True)

    # --- agent_tasks ------------------------------------------------------
    op.add_column(
        "agent_tasks",
        sa.Column("run_id", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE agent_tasks AS t "
            "SET run_id = i.run_id "
            "FROM incidents AS i "
            "WHERE t.incident_id = i.id AND t.run_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE agent_tasks "
            "SET payload = jsonb_set(payload, '{runId}', to_jsonb(cast(run_id as text))) "
            "WHERE run_id IS NOT NULL"
        )
    )
    op.alter_column("agent_tasks", "run_id", nullable=False)
    op.create_foreign_key(
        "fk_agent_tasks_run_id",
        "agent_tasks",
        "runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("agent_tasks", "incident_id", nullable=True)


def downgrade() -> None:
    op.alter_column("agent_tasks", "incident_id", nullable=False)
    op.drop_constraint("fk_agent_tasks_run_id", "agent_tasks", type_="foreignkey")
    op.drop_column("agent_tasks", "run_id")

    op.alter_column("agent_sessions", "incident_id", nullable=False)
    op.drop_index("ix_agent_sessions_run_created", table_name="agent_sessions")
    op.drop_constraint("fk_agent_sessions_run_id", "agent_sessions", type_="foreignkey")
    op.drop_column("agent_sessions", "run_id")
