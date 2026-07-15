"""Phase 30 human authorization matrix and decision engine."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import (
    AuthMethodV1,
    AuthenticatedActorV1,
    AuthorizationDecisionOutcomeV1,
    AuthorizationDecisionV1,
    PermissionV1,
    PlatformRoleV1,
    ResourceAccessGrantV1,
)
from aegis_contracts.versioning import (
    AUTHENTICATED_ACTOR_SCHEMA_VERSION,
    AUTHORIZATION_DECISION_SCHEMA_VERSION,
)

ROLE_PERMISSION_MATRIX: dict[PlatformRoleV1, frozenset[PermissionV1]] = {
    PlatformRoleV1.VIEWER: frozenset(
        {
            PermissionV1.RUNS_READ,
            PermissionV1.INVESTIGATION_READ,
            PermissionV1.REPLAY_READ,
            PermissionV1.REPORTS_READ,
            PermissionV1.SCORING_READ,
            PermissionV1.WS_SUBSCRIBE,
        }
    ),
    PlatformRoleV1.ANALYST: frozenset(
        {
            PermissionV1.RUNS_READ,
            PermissionV1.INVESTIGATION_READ,
            PermissionV1.INVESTIGATION_TRIGGER,
            PermissionV1.REPLAY_READ,
            PermissionV1.REPORTS_READ,
            PermissionV1.REPORTS_EXPORT,
            PermissionV1.SCORING_READ,
            PermissionV1.SCORING_COMPUTE,
            PermissionV1.SCORING_EXPORT,
            PermissionV1.WS_SUBSCRIBE,
        }
    ),
    PlatformRoleV1.OPERATOR: frozenset(
        {
            PermissionV1.RUNS_READ,
            PermissionV1.RUNS_WRITE,
            PermissionV1.INVESTIGATION_READ,
            PermissionV1.INVESTIGATION_TRIGGER,
            PermissionV1.APPROVALS_DECIDE,
            PermissionV1.REPLAY_READ,
            PermissionV1.REPLAY_WRITE,
            PermissionV1.REPORTS_READ,
            PermissionV1.REPORTS_EXPORT,
            PermissionV1.REPORTS_TRIGGER,
            PermissionV1.SCORING_READ,
            PermissionV1.SCORING_COMPUTE,
            PermissionV1.SCORING_EXPORT,
            PermissionV1.WS_SUBSCRIBE,
        }
    ),
    PlatformRoleV1.SCENARIO_AUTHOR: frozenset(
        {
            PermissionV1.RUNS_READ,
            PermissionV1.INVESTIGATION_READ,
            PermissionV1.REPLAY_READ,
            PermissionV1.REPORTS_READ,
            PermissionV1.SCORING_READ,
            PermissionV1.SCENARIOS_PUBLISH,
            PermissionV1.WS_SUBSCRIBE,
        }
    ),
    PlatformRoleV1.ADMIN: frozenset(set(PermissionV1)),
}

# WARDEN policy metadata roles satisfied by approvals:decide holders.
WARDEN_APPROVER_ROLE_ALIASES: frozenset[str] = frozenset(
    {"incident_commander", "security_lead"}
)


def permissions_for_roles(roles: list[PlatformRoleV1] | list[str]) -> frozenset[PermissionV1]:
    resolved: set[PermissionV1] = set()
    for role in roles:
        platform_role = role if isinstance(role, PlatformRoleV1) else PlatformRoleV1(role)
        resolved.update(ROLE_PERMISSION_MATRIX[platform_role])
    return frozenset(resolved)


def actor_has_permission(actor: AuthenticatedActorV1, permission: PermissionV1 | str) -> bool:
    required = permission if isinstance(permission, PermissionV1) else PermissionV1(permission)
    effective = set(actor.permissions) or set(permissions_for_roles(list(actor.roles)))
    return required in effective


def can_satisfy_warden_approver_roles(
    actor: AuthenticatedActorV1,
    required_roles: list[str] | None,
) -> bool:
    """Map WARDEN approver role metadata to platform approvals:decide."""
    if not required_roles:
        return actor_has_permission(actor, PermissionV1.APPROVALS_DECIDE)
    if not actor_has_permission(actor, PermissionV1.APPROVALS_DECIDE):
        return False
    return all(role in WARDEN_APPROVER_ROLE_ALIASES or role in {r.value for r in actor.roles} for role in required_roles)


class AuthorizationEngine:
    """Deny-by-default authorization decisions for human operators."""

    def decide(
        self,
        *,
        actor: AuthenticatedActorV1,
        permission: PermissionV1 | str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        grants: list[ResourceAccessGrantV1] | None = None,
        decided_at: datetime | None = None,
    ) -> AuthorizationDecisionV1:
        required = permission if isinstance(permission, PermissionV1) else PermissionV1(permission)
        now = decided_at or datetime.now(tz=UTC)
        role_allowed = actor_has_permission(actor, required)

        grant_restricted = False
        grant_allowed = False
        if resource_type == "run" and resource_id and grants is not None:
            matching = [
                grant
                for grant in grants
                if grant.user_id == actor.user_id
                and grant.resource_type == "run"
                and grant.resource_id == resource_id
            ]
            if matching:
                grant_restricted = True
                grant_allowed = any(required in grant.permissions for grant in matching)

        if grant_restricted:
            allowed = role_allowed and grant_allowed
            reason = (
                "RESOURCE_GRANT_ALLOWED" if allowed else "RESOURCE_GRANT_DENIED"
            )
        elif role_allowed:
            allowed = True
            reason = "ROLE_PERMISSION_GRANTED"
        else:
            allowed = False
            reason = "ROLE_PERMISSION_DENIED"

        return AuthorizationDecisionV1(
            schema_version=AUTHORIZATION_DECISION_SCHEMA_VERSION,
            outcome=(
                AuthorizationDecisionOutcomeV1.ALLOW
                if allowed
                else AuthorizationDecisionOutcomeV1.DENY
            ),
            permission=required,
            user_id=actor.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            reason_code=reason,
            decided_at=now,
        )


def build_actor(
    *,
    user_id: str,
    display_name: str,
    roles: list[PlatformRoleV1],
    session_id: str,
    auth_method: str,
) -> AuthenticatedActorV1:
    permissions = sorted(permissions_for_roles(roles), key=lambda item: item.value)
    return AuthenticatedActorV1(
        schema_version=AUTHENTICATED_ACTOR_SCHEMA_VERSION,
        user_id=user_id,
        display_name=display_name,
        roles=roles,
        permissions=permissions,
        session_id=session_id,
        auth_method=AuthMethodV1(auth_method),
    )
