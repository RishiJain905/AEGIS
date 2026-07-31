# ruff: noqa: E501

"""Wall-clock run creation time; reports may exist without an incident.

``runs.started_at`` is the deterministic scenario epoch — the same pinned constant on
every row — so nothing in the schema could say which run was newest: "latest run"
pickers and report sorting chose arbitrarily. ``created_at`` is the wall clock stamped
at creation by the repository, deliberately outside the sim clock and never part of the
hashed event stream. Nullable because history holds no record for existing rows; they
sort after anything stamped.

``report_versions.incident_id`` becomes nullable so a run that ends with zero incidents
can still persist its after-action report (the SCRIBE fallback currently returns
``SKIPPED_NO_INCIDENT`` for want of a case to attach to; the schema stops forcing that).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019_run_created_at"
down_revision: str | None = "018_agent_session_origin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "report_versions",
        "incident_id",
        existing_type=sa.String(64),
        nullable=True,
    )


def downgrade() -> None:
    # Re-tightening the FK requires no NULLs; incident-less reports cannot survive
    # the downgrade and are dropped with it.
    op.execute("DELETE FROM report_versions WHERE incident_id IS NULL")
    op.alter_column(
        "report_versions",
        "incident_id",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.drop_column("runs", "created_at")
