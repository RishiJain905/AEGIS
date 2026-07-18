"""Policy package for Phase 22 deterministic WARDEN evaluation."""

from aegis_policy.authz import (
    ROLE_PERMISSION_MATRIX,
    WARDEN_APPROVER_ROLE_ALIASES,
    AuthorizationEngine,
    actor_has_permission,
    build_actor,
    can_satisfy_warden_approver_roles,
    permissions_for_roles,
)
from aegis_policy.commands import (
    ALLOWLISTED_COMMANDS,
    COMMAND_TO_ACTION_CLASS,
    CRITICALITY_BLOCK_THRESHOLD,
    SCENARIO_RESTRICTED_COMMANDS,
    expected_action_class,
    parse_command,
)
from aegis_policy.engine import PolicyEngine

WORKSPACE_VERSION = "1.0.0"

__all__ = [
    "ALLOWLISTED_COMMANDS",
    "COMMAND_TO_ACTION_CLASS",
    "CRITICALITY_BLOCK_THRESHOLD",
    "PolicyEngine",
    "ROLE_PERMISSION_MATRIX",
    "WARDEN_APPROVER_ROLE_ALIASES",
    "AuthorizationEngine",
    "SCENARIO_RESTRICTED_COMMANDS",
    "WORKSPACE_VERSION",
    "actor_has_permission",
    "build_actor",
    "can_satisfy_warden_approver_roles",
    "expected_action_class",
    "parse_command",
    "permissions_for_roles",
]
