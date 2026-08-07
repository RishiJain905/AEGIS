# ruff: noqa: E501

"""Add per-user encrypted credentials for cloud model providers.

A run can be driven by the operator's own model subscription (OpenAI, OpenRouter,
Ollama Cloud) rather than the local endpoint, which means the platform holds their API
key. ``auth_user_provider_credentials`` stores one encrypted key per
``(user_id, provider)`` — Fernet ciphertext plus the four-character hint the console
shows so an operator can tell which key is connected. No plaintext key is stored.

Kept apart from ``auth_user_credentials``: that table holds login secrets AEGIS owns,
this one holds third-party keys the operator lends us, and the two have different
lifecycles. Deleting the account removes the keys with it (CASCADE), so an offboarded
operator leaves no borrowed credential behind.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_provider_credentials"
down_revision: str | None = "019_run_created_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_user_provider_credentials",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_hint", sa.String(length=8), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False, server_default="fernet"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "provider"),
    )


def downgrade() -> None:
    # Dropping the table destroys the stored keys; operators reconnect their providers
    # after a downgrade. Nothing else references these rows.
    op.drop_table("auth_user_provider_credentials")
