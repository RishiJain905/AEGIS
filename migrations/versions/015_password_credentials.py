# ruff: noqa: E501

"""Add username + password credentials for real username/password authentication.

Adds a nullable unique ``username`` to ``auth_users`` (OIDC/dev-seed identities keep
NULL) and a dedicated ``auth_user_credentials`` table holding one Argon2id password
hash per credentialed account. No plaintext is ever stored. Nothing is seeded here —
a fresh database has zero accounts, and the first admin is created through the
self-disabling first-run setup endpoint.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_password_credentials"
down_revision: str | None = "014_run_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("username", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint("uq_auth_users_username", "auth_users", ["username"])
    op.create_table(
        "auth_user_credentials",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("auth_user_credentials")
    op.drop_constraint("uq_auth_users_username", "auth_users", type_="unique")
    op.drop_column("auth_users", "username")
