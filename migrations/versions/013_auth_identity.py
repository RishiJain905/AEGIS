# ruff: noqa: E501

"""Add Phase 30 authentication identity, sessions, and security audit tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_auth_identity"
down_revision: str | None = "012_run_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "auth_external_identities",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_auth_external_identities_issuer_subject"),
    )
    op.create_index(
        "ix_auth_external_identities_user_id",
        "auth_external_identities",
        ["user_id"],
    )
    op.create_table(
        "auth_role_assignments",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role", name="uq_auth_role_assignments_user_role"),
    )
    op.create_index(
        "ix_auth_role_assignments_user_id",
        "auth_role_assignments",
        ["user_id"],
    )
    op.create_table(
        "auth_resource_grants",
        sa.Column("grant_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("grant_id"),
    )
    op.create_index(
        "ix_auth_resource_grants_user_resource",
        "auth_resource_grants",
        ["user_id", "resource_type", "resource_id"],
    )
    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("auth_method", sa.String(length=32), nullable=False),
        sa.Column("csrf_token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ws_ticket_hash", sa.String(length=128), nullable=True),
        sa.Column("ws_ticket_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "security_audit_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.String(length=128), nullable=True),
        sa.Column("target", sa.String(length=256), nullable=True),
        sa.Column("permission", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_security_audit_events_occurred_at",
        "security_audit_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_security_audit_events_actor",
        "security_audit_events",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_audit_events_actor", table_name="security_audit_events")
    op.drop_index("ix_security_audit_events_occurred_at", table_name="security_audit_events")
    op.drop_table("security_audit_events")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_auth_resource_grants_user_resource", table_name="auth_resource_grants")
    op.drop_table("auth_resource_grants")
    op.drop_index("ix_auth_role_assignments_user_id", table_name="auth_role_assignments")
    op.drop_table("auth_role_assignments")
    op.drop_index("ix_auth_external_identities_user_id", table_name="auth_external_identities")
    op.drop_table("auth_external_identities")
    op.drop_table("auth_users")
