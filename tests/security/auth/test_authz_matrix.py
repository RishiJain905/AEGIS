"""Unit tests for Phase 30 authorization matrix and decisions."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import PermissionV1, PlatformRoleV1
from aegis_policy.authz import (
    ROLE_PERMISSION_MATRIX,
    AuthorizationEngine,
    actor_has_permission,
    build_actor,
    can_satisfy_warden_approver_roles,
)


def test_role_permission_matrix_covers_all_platform_roles() -> None:
    assert set(ROLE_PERMISSION_MATRIX) == set(PlatformRoleV1)


def test_viewer_cannot_approve_or_mutate() -> None:
    actor = build_actor(
        user_id="user:viewer-alpha",
        display_name="Viewer",
        roles=[PlatformRoleV1.VIEWER],
        session_id="sess_viewer",
        auth_method="dev",
    )
    assert actor_has_permission(actor, PermissionV1.RUNS_READ)
    assert not actor_has_permission(actor, PermissionV1.APPROVALS_DECIDE)
    assert not actor_has_permission(actor, PermissionV1.RUNS_WRITE)
    assert not actor_has_permission(actor, PermissionV1.ADMIN_MANAGE)


def test_operator_can_approve_but_not_admin() -> None:
    actor = build_actor(
        user_id="user:operator-alpha",
        display_name="Operator",
        roles=[PlatformRoleV1.OPERATOR],
        session_id="sess_operator",
        auth_method="dev",
    )
    assert actor_has_permission(actor, PermissionV1.APPROVALS_DECIDE)
    assert actor_has_permission(actor, PermissionV1.RUNS_WRITE)
    assert not actor_has_permission(actor, PermissionV1.ADMIN_MANAGE)
    assert not actor_has_permission(actor, PermissionV1.SCENARIOS_PUBLISH)


def test_admin_has_all_permissions() -> None:
    actor = build_actor(
        user_id="user:admin-alpha",
        display_name="Admin",
        roles=[PlatformRoleV1.ADMIN],
        session_id="sess_admin",
        auth_method="dev",
    )
    for permission in PermissionV1:
        assert actor_has_permission(actor, permission)


def test_authorization_engine_denies_by_default() -> None:
    engine = AuthorizationEngine()
    actor = build_actor(
        user_id="user:analyst-alpha",
        display_name="Analyst",
        roles=[PlatformRoleV1.ANALYST],
        session_id="sess_analyst",
        auth_method="dev",
    )
    decision = engine.decide(
        actor=actor,
        permission=PermissionV1.APPROVALS_DECIDE,
        decided_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert decision.outcome.value == "deny"
    assert decision.reason_code == "ROLE_PERMISSION_DENIED"


def test_warden_approver_aliases_map_to_approvals_decide() -> None:
    operator = build_actor(
        user_id="user:operator-alpha",
        display_name="Operator",
        roles=[PlatformRoleV1.OPERATOR],
        session_id="sess_operator",
        auth_method="dev",
    )
    viewer = build_actor(
        user_id="user:viewer-alpha",
        display_name="Viewer",
        roles=[PlatformRoleV1.VIEWER],
        session_id="sess_viewer",
        auth_method="dev",
    )
    assert can_satisfy_warden_approver_roles(
        operator,
        ["incident_commander", "security_lead"],
    )
    assert not can_satisfy_warden_approver_roles(
        viewer,
        ["incident_commander"],
    )
