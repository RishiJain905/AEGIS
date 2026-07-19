"""Admin console application service.

Read-first administration: expose the identities the platform authorizes, the
policy that is *actually enforced* server-side, and non-secret runtime settings.
Secret exclusion is fail-closed — settings are assembled from an explicit allowlist
of non-sensitive fields, then run through the shared provider redaction as a second
line of defence so any accidentally included secret-shaped value is scrubbed.
"""

from __future__ import annotations

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, PermissionV1, PlatformRoleV1
from aegis_contracts.entities import ActionClass
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.redaction import redact_mapping
from aegis_persistence.orm.tables import AuthRoleAssignmentRow, AuthUserRow
from aegis_policy.authz import (
    ROLE_PERMISSION_MATRIX,
    WARDEN_APPROVER_ROLE_ALIASES,
    permissions_for_roles,
)
from aegis_policy.commands import COMMAND_TO_ACTION_CLASS, SCENARIO_RESTRICTED_COMMANDS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.admin.models import (
    AdminActionClassV1,
    AdminCommandV1,
    AdminPolicyResponseV1,
    AdminRolePermissionsV1,
    AdminSettingsResponseV1,
    AdminUsersResponseV1,
    AdminUserV1,
)

# Class 0-3 action-class presentation metadata. approval_required mirrors the
# PolicyEngine: OPERATIONAL/CRITICAL demand a human approval gate before execution.
_ACTION_CLASS_META: dict[ActionClass, tuple[str, bool, str]] = {
    ActionClass.READ_ONLY: (
        "Class 0 — Read-only",
        False,
        "Observation only. Auto-allowed; no state change.",
    ),
    ActionClass.LOW_IMPACT: (
        "Class 1 — Low impact",
        False,
        "Reversible low-impact change. Auto-allowed.",
    ),
    ActionClass.OPERATIONAL: (
        "Class 2 — Operational",
        True,
        "State-changing action. Requires explicit human approval before execution.",
    ),
    ActionClass.CRITICAL: (
        "Class 3 — Critical",
        True,
        "High-impact action. Requires human approval; blocked on highly critical assets.",
    ),
}


def user_to_model(
    *,
    user_id: str,
    display_name: str,
    status: str,
    roles: list[PlatformRoleV1],
) -> AdminUserV1:
    """Project an auth identity into the admin view, deriving effective permissions."""
    permissions = sorted(permission.value for permission in permissions_for_roles(roles))
    return AdminUserV1(
        user_id=user_id,
        display_name=display_name,
        status=status,
        roles=sorted(role.value for role in roles),
        permissions=permissions,
    )


class AdminService:
    """Read-first admin aggregations over the auth registry, policy, and settings."""

    async def list_users(self, session: AsyncSession) -> AdminUsersResponseV1:
        users_result = await session.execute(select(AuthUserRow).order_by(AuthUserRow.user_id))
        user_rows = list(users_result.scalars().all())

        roles_result = await session.execute(select(AuthRoleAssignmentRow))
        roles_by_user: dict[str, list[PlatformRoleV1]] = {}
        for assignment in roles_result.scalars().all():
            roles_by_user.setdefault(assignment.user_id, []).append(
                PlatformRoleV1(assignment.role)
            )

        users = [
            user_to_model(
                user_id=row.user_id,
                display_name=row.display_name,
                status=row.status,
                roles=roles_by_user.get(row.user_id, []),
            )
            for row in user_rows
        ]
        return AdminUsersResponseV1(users=users, total=len(users))

    def build_policy_snapshot(self) -> AdminPolicyResponseV1:
        roles = [
            AdminRolePermissionsV1(
                role=role.value,
                permissions=sorted(permission.value for permission in permissions),
            )
            for role, permissions in sorted(
                ROLE_PERMISSION_MATRIX.items(), key=lambda item: item[0].value
            )
        ]
        action_classes = [
            AdminActionClassV1(
                action_class=action_class.value,
                label=label,
                approval_required=approval_required,
                description=description,
            )
            for action_class, (label, approval_required, description) in _ACTION_CLASS_META.items()
        ]
        commands = [
            AdminCommandV1(
                command=command.value,
                action_class=action_class.value,
                scenario_restricted=command in SCENARIO_RESTRICTED_COMMANDS,
            )
            for command, action_class in sorted(
                COMMAND_TO_ACTION_CLASS.items(), key=lambda item: item[0].value
            )
        ]
        return AdminPolicyResponseV1(
            roles=roles,
            permissions=sorted(permission.value for permission in PermissionV1),
            action_classes=action_classes,
            commands=commands,
            approver_roles=sorted(WARDEN_APPROVER_ROLE_ALIASES),
        )

    def build_settings_snapshot(
        self,
        settings: AegisSettings,
        provider_settings: ProviderSettings,
        *,
        health: dict[str, object],
    ) -> AdminSettingsResponseV1:
        # Explicit non-secret allowlist. API keys, passwords, tokens, and OIDC client
        # secrets are never selected here; base URLs and model names are configuration,
        # not credentials.
        provider = redact_mapping(
            {
                "defaultProvider": provider_settings.AEGIS_PROVIDER_DEFAULT.value,
                "timeoutSeconds": provider_settings.AEGIS_PROVIDER_TIMEOUT_SECONDS,
                "maxRetries": provider_settings.AEGIS_PROVIDER_MAX_RETRIES,
                "maxOutputTokens": provider_settings.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS,
                "openaiModel": provider_settings.AEGIS_PROVIDER_OPENAI_MODEL,
                "openaiBaseUrl": provider_settings.AEGIS_PROVIDER_OPENAI_BASE_URL,
                "localModel": provider_settings.AEGIS_PROVIDER_LOCAL_MODEL,
                "localBaseUrl": provider_settings.AEGIS_PROVIDER_LOCAL_BASE_URL,
                "inMemoryArtifacts": provider_settings.AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS,
            }
        )
        websocket = redact_mapping(
            {
                "enabled": settings.AEGIS_WS_ENABLED,
                "path": settings.AEGIS_WS_PATH,
                "maxConnections": settings.AEGIS_WS_MAX_CONNECTIONS,
                "heartbeatIntervalSeconds": settings.AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS,
            }
        )
        security = redact_mapping(
            {
                "requestBodyMaxBytes": settings.AEGIS_REQUEST_BODY_MAX_BYTES,
                "rateLimitRequestsPerMinute": settings.AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE,
                "rateLimitBurst": settings.AEGIS_RATE_LIMIT_BURST,
                "hstsEnabled": settings.AEGIS_SECURITY_HSTS_ENABLED,
            }
        )
        observability = redact_mapping(
            {
                "otelEnabled": settings.OTEL_ENABLED,
                "serviceName": settings.OTEL_SERVICE_NAME,
                "otlpEndpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                "otlpProtocol": settings.OTEL_EXPORTER_OTLP_PROTOCOL,
                "telemetryRetentionHours": settings.AEGIS_TELEMETRY_RETENTION_HOURS,
            }
        )
        auth = redact_mapping(
            {
                "devAuthEnabled": settings.AEGIS_DEV_AUTH_ENABLED,
                "oidcEnabled": settings.AEGIS_OIDC_ENABLED,
                "oidcIssuer": settings.AEGIS_OIDC_ISSUER,
                "sessionTtlSeconds": settings.AEGIS_SESSION_TTL_SECONDS,
                "corsAllowedOrigins": settings.cors_allowed_origins,
            }
        )
        return AdminSettingsResponseV1(
            environment=settings.AEGIS_ENV.value,
            version=WORKSPACE_VERSION,
            log_level=settings.LOG_LEVEL.value,
            provider=provider,
            websocket=websocket,
            security=security,
            observability=observability,
            auth=auth,
            health=health,
        )
