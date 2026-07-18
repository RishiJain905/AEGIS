# ruff: noqa: E501

"""Add run ownership (owner_user_id) with demo/admin backfill.

Records the creating actor on each run so listing can be scoped to the caller and
owner-or-admin authorization can gate run retrieval and lifecycle commands
(AEGIS-OITB-008). Additive nullable column; legacy/seeded rows are backfilled to a
demo/admin owner so the demo never 403s unexpectedly. See ADR 0034.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_run_ownership"
down_revision: str | None = "013_auth_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Demo/admin owner assigned to pre-ownership (seeded/legacy) runs. Matches the
# ADMIN dev-seed identity so those runs remain visible to an admin and never
# surprise-403 in the demo. Deliberately not an FK: auth users are seeded at app
# startup, not by migration, so this id may not exist in auth_users at migrate time.
_DEMO_OWNER_USER_ID = "user:admin-alpha"


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("owner_user_id", sa.String(length=128), nullable=True),
    )
    # Backfill the query column for pre-ownership rows.
    op.execute(
        sa.text("UPDATE runs SET owner_user_id = :owner WHERE owner_user_id IS NULL").bindparams(
            owner=_DEMO_OWNER_USER_ID
        )
    )
    # Keep the JSONB payload (the source of RunV1 identity via run_to_domain) consistent
    # with the column so the domain object also reflects the backfilled owner.
    op.execute(
        sa.text(
            "UPDATE runs SET payload = jsonb_set(payload, '{ownerUserId}', to_jsonb(cast(:owner as text))) "
            "WHERE NOT (payload ? 'ownerUserId') OR payload->>'ownerUserId' IS NULL"
        ).bindparams(owner=_DEMO_OWNER_USER_ID)
    )
    op.create_index("ix_runs_owner_user_id", "runs", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_owner_user_id", table_name="runs")
    op.drop_column("runs", "owner_user_id")
