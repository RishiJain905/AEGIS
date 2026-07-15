"""Authz package exports."""

from aegis_policy.authz.matrix import (
    ROLE_PERMISSION_MATRIX,
    WARDEN_APPROVER_ROLE_ALIASES,
    AuthorizationEngine,
    actor_has_permission,
    build_actor,
    can_satisfy_warden_approver_roles,
    permissions_for_roles,
)

__all__ = [
    "ROLE_PERMISSION_MATRIX",
    "WARDEN_APPROVER_ROLE_ALIASES",
    "AuthorizationEngine",
    "actor_has_permission",
    "build_actor",
    "can_satisfy_warden_approver_roles",
    "permissions_for_roles",
]
