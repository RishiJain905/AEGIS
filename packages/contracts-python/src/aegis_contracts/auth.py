"""Phase 30 authentication and authorization contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import AuthoredId, RunId, UtcTimestamp
from aegis_contracts.versioning import (
    AUTHENTICATED_ACTOR_SCHEMA_VERSION,
    AUTHORIZATION_DECISION_SCHEMA_VERSION,
    PERMISSION_SCHEMA_VERSION,
    RESOURCE_ACCESS_GRANT_SCHEMA_VERSION,
    ROLE_SCHEMA_VERSION,
    SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
    SESSION_INFO_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class PlatformRoleV1(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    SCENARIO_AUTHOR = "scenario_author"
    ADMIN = "admin"


class PermissionV1(StrEnum):
    RUNS_READ = "runs:read"
    RUNS_WRITE = "runs:write"
    INVESTIGATION_READ = "investigation:read"
    INVESTIGATION_TRIGGER = "investigation:trigger"
    APPROVALS_DECIDE = "approvals:decide"
    REPLAY_READ = "replay:read"
    REPLAY_WRITE = "replay:write"
    REPORTS_READ = "reports:read"
    REPORTS_EXPORT = "reports:export"
    REPORTS_TRIGGER = "reports:trigger"
    SCORING_READ = "scoring:read"
    SCORING_COMPUTE = "scoring:compute"
    SCORING_EXPORT = "scoring:export"
    SCENARIOS_PUBLISH = "scenarios:publish"
    ADMIN_MANAGE = "admin:manage"
    WS_SUBSCRIBE = "ws:subscribe"


class AuthErrorCode(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    CSRF_FAILED = "CSRF_FAILED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    DEV_AUTH_DISABLED = "DEV_AUTH_DISABLED"
    OIDC_FAILED = "OIDC_FAILED"


class AuthorizationDecisionOutcomeV1(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class SecurityAuditActionV1(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    DENIAL = "denial"
    ROLE_CHANGE = "role_change"
    PRIVILEGED_ACTION = "privileged_action"


class SecurityAuditOutcomeV1(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuthMethodV1(StrEnum):
    OIDC = "oidc"
    DEV = "dev"
    PASSWORD = "password"


class RoleContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    role: PlatformRoleV1
    permissions: list[PermissionV1] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_schema_version(self) -> RoleContractV1:
        assert_supported_schema_version("role", self.schema_version)
        if self.schema_version != ROLE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported role schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class PermissionContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    permission: PermissionV1
    description: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_schema_version(self) -> PermissionContractV1:
        assert_supported_schema_version("permission", self.schema_version)
        if self.schema_version != PERMISSION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported permission schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AuthenticatedActorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    user_id: AuthoredId = Field(alias="userId")
    display_name: str = Field(alias="displayName", min_length=1, max_length=256)
    roles: list[PlatformRoleV1] = Field(min_length=1)
    permissions: list[PermissionV1] = Field(default_factory=list)
    session_id: str = Field(alias="sessionId", min_length=8, max_length=128)
    auth_method: AuthMethodV1 = Field(alias="authMethod")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AuthenticatedActorV1:
        assert_supported_schema_version("authenticated_actor", self.schema_version)
        if self.schema_version != AUTHENTICATED_ACTOR_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported authenticated actor schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if not self.user_id.startswith("user:"):
            raise ContractValidationError(
                code=ContractErrorCode.INVALID_IDENTIFIER,
                message="Authenticated actor userId must use the user: namespace",
                details={"userId": self.user_id},
            )
        return self


class ResourceAccessGrantV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    grant_id: str = Field(alias="grantId", min_length=1, max_length=128)
    user_id: AuthoredId = Field(alias="userId")
    resource_type: Literal["run"] = Field(alias="resourceType")
    resource_id: RunId = Field(alias="resourceId")
    permissions: list[PermissionV1] = Field(min_length=1)
    created_at: UtcTimestamp = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> ResourceAccessGrantV1:
        assert_supported_schema_version("resource_access_grant", self.schema_version)
        if self.schema_version != RESOURCE_ACCESS_GRANT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported resource access grant schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class AuthorizationDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    outcome: AuthorizationDecisionOutcomeV1
    permission: PermissionV1
    user_id: AuthoredId = Field(alias="userId")
    resource_type: str | None = Field(default=None, alias="resourceType", max_length=64)
    resource_id: str | None = Field(default=None, alias="resourceId", max_length=128)
    reason_code: str = Field(alias="reasonCode", min_length=1, max_length=128)
    decided_at: UtcTimestamp = Field(alias="decidedAt")

    @model_validator(mode="after")
    def validate_schema_version(self) -> AuthorizationDecisionV1:
        assert_supported_schema_version("authorization_decision", self.schema_version)
        if self.schema_version != AUTHORIZATION_DECISION_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported authorization decision schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class SessionInfoV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    session_id: str = Field(alias="sessionId", min_length=8, max_length=128)
    user_id: AuthoredId = Field(alias="userId")
    auth_method: AuthMethodV1 = Field(alias="authMethod")
    created_at: UtcTimestamp = Field(alias="createdAt")
    expires_at: UtcTimestamp = Field(alias="expiresAt")
    revoked_at: UtcTimestamp | None = Field(default=None, alias="revokedAt")
    csrf_token: str = Field(alias="csrfToken", min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_schema_version(self) -> SessionInfoV1:
        assert_supported_schema_version("session_info", self.schema_version)
        if self.schema_version != SESSION_INFO_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported session info schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class SecurityAuditEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    event_id: str = Field(alias="eventId", min_length=1, max_length=128)
    action: SecurityAuditActionV1
    outcome: SecurityAuditOutcomeV1
    actor_user_id: AuthoredId | None = Field(default=None, alias="actorUserId")
    target: str | None = Field(default=None, max_length=256)
    permission: PermissionV1 | None = None
    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=128)
    request_id: str | None = Field(default=None, alias="requestId", max_length=128)
    correlation_id: str | None = Field(default=None, alias="correlationId", max_length=128)
    occurred_at: UtcTimestamp = Field(alias="occurredAt")
    details: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_and_details(self) -> SecurityAuditEventV1:
        assert_supported_schema_version("security_audit_event", self.schema_version)
        if self.schema_version != SECURITY_AUDIT_EVENT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported security audit event schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        forbidden_keys = {
            "password",
            "token",
            "access_token",
            "refresh_token",
            "authorization",
            "cookie",
            "csrf",
            "secret",
        }
        for key in self.details:
            lowered = key.lower()
            if any(part in lowered for part in forbidden_keys):
                raise ContractValidationError(
                    code=ContractErrorCode.VALIDATION_FAILED,
                    message="Security audit details must not contain secret field names",
                    details={"field": key},
                )
        return self


class DevLoginRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1, default=1)
    user_id: AuthoredId = Field(alias="userId")


class AuthSessionResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1, default=1)
    authenticated: bool
    actor: AuthenticatedActorV1 | None = None
    session: SessionInfoV1 | None = None
