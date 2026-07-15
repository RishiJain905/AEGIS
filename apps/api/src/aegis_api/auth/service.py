"""Session and identity application service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts import (
    AuthErrorCode,
    AuthMethodV1,
    AuthSessionResponseV1,
    AuthenticatedActorV1,
    PermissionV1,
    PlatformRoleV1,
    SecurityAuditActionV1,
    SecurityAuditEventV1,
    SecurityAuditOutcomeV1,
    SessionInfoV1,
)
from aegis_contracts.versioning import (
    SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
    SESSION_INFO_SCHEMA_VERSION,
)
from aegis_persistence.repositories.auth import AuthUserRecord, PostgresAuthRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.authz import AuthorizationEngine, build_actor

from aegis_api.auth.tokens import (
    constant_time_equals,
    generate_audit_event_id,
    generate_csrf_token,
    generate_opaque_token,
    generate_session_id,
    hash_token,
)


class AuthServiceError(Exception):
    def __init__(
        self,
        *,
        code: AuthErrorCode,
        message: str,
        status_code: int,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthService:
    def __init__(self, *, session_ttl_seconds: int) -> None:
        self._session_ttl_seconds = session_ttl_seconds
        self._authz = AuthorizationEngine()

    async def create_session_for_user(
        self,
        uow: PostgresUnitOfWork,
        *,
        user: AuthUserRecord,
        auth_method: AuthMethodV1,
        request_id: str | None = None,
    ) -> tuple[AuthenticatedActorV1, SessionInfoV1, str]:
        now = datetime.now(tz=UTC)
        session_id = generate_session_id()
        raw_token = generate_opaque_token()
        csrf_token = generate_csrf_token()
        expires_at = now + timedelta(seconds=self._session_ttl_seconds)
        session = await uow.auth.create_session(
            session_id=session_id,
            session_token_hash=hash_token(raw_token),
            user_id=user.user_id,
            auth_method=auth_method.value,
            csrf_token=csrf_token,
            created_at=now,
            expires_at=expires_at,
        )
        actor = build_actor(
            user_id=user.user_id,
            display_name=user.display_name,
            roles=user.roles,
            session_id=session_id,
            auth_method=auth_method.value,
        )
        await self.record_audit(
            uow,
            action=SecurityAuditActionV1.LOGIN,
            outcome=SecurityAuditOutcomeV1.SUCCESS,
            actor_user_id=user.user_id,
            reason_code=f"{auth_method.value.upper()}_LOGIN",
            request_id=request_id,
            details={"authMethod": auth_method.value},
        )
        return actor, session, raw_token

    async def resolve_actor_from_token(
        self,
        uow: PostgresUnitOfWork,
        *,
        raw_token: str | None,
    ) -> AuthenticatedActorV1:
        if not raw_token:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="Authentication required",
                status_code=401,
            )
        row = await uow.auth.get_session_by_token_hash(hash_token(raw_token))
        if row is None:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="Invalid session",
                status_code=401,
            )
        now = datetime.now(tz=UTC)
        if row.revoked_at is not None:
            raise AuthServiceError(
                code=AuthErrorCode.SESSION_REVOKED,
                message="Session has been revoked",
                status_code=401,
            )
        if row.expires_at <= now:
            raise AuthServiceError(
                code=AuthErrorCode.SESSION_EXPIRED,
                message="Session has expired",
                status_code=401,
            )
        user = await uow.auth.get_user(row.user_id)
        if user is None:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="Session user is inactive or missing",
                status_code=401,
            )
        return build_actor(
            user_id=user.user_id,
            display_name=user.display_name,
            roles=user.roles,
            session_id=row.session_id,
            auth_method=row.auth_method,
        )

    async def get_session_info(
        self,
        uow: PostgresUnitOfWork,
        *,
        session_id: str,
    ) -> SessionInfoV1:
        row = await uow.auth.get_session(session_id)
        if row is None:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="Session not found",
                status_code=401,
            )
        return SessionInfoV1(
            schema_version=SESSION_INFO_SCHEMA_VERSION,
            session_id=row.session_id,
            user_id=row.user_id,
            auth_method=row.auth_method,  # type: ignore[arg-type]
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            csrf_token=row.csrf_token,
        )

    async def logout(
        self,
        uow: PostgresUnitOfWork,
        *,
        actor: AuthenticatedActorV1,
        request_id: str | None = None,
    ) -> None:
        now = datetime.now(tz=UTC)
        await uow.auth.revoke_session(actor.session_id, revoked_at=now)
        await self.record_audit(
            uow,
            action=SecurityAuditActionV1.LOGOUT,
            outcome=SecurityAuditOutcomeV1.SUCCESS,
            actor_user_id=actor.user_id,
            reason_code="LOGOUT",
            request_id=request_id,
        )

    def validate_csrf(
        self,
        *,
        session_csrf: str,
        header_csrf: str | None,
    ) -> None:
        if not header_csrf or not constant_time_equals(session_csrf, header_csrf):
            raise AuthServiceError(
                code=AuthErrorCode.CSRF_FAILED,
                message="CSRF validation failed",
                status_code=403,
            )

    async def authorize(
        self,
        uow: PostgresUnitOfWork,
        *,
        actor: AuthenticatedActorV1,
        permission: PermissionV1,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        grants = await uow.auth.list_grants_for_user(actor.user_id)
        decision = self._authz.decide(
            actor=actor,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            grants=grants if grants else None,
        )
        if decision.outcome.value == "allow":
            return
        await self.record_audit(
            uow,
            action=SecurityAuditActionV1.DENIAL,
            outcome=SecurityAuditOutcomeV1.FAILURE,
            actor_user_id=actor.user_id,
            permission=permission,
            target=resource_id,
            reason_code=decision.reason_code,
            request_id=request_id,
        )
        raise AuthServiceError(
            code=AuthErrorCode.FORBIDDEN,
            message="Permission denied",
            status_code=403,
            details={"permission": permission.value, "reasonCode": decision.reason_code},
        )

    async def issue_ws_ticket(
        self,
        uow: PostgresUnitOfWork,
        *,
        actor: AuthenticatedActorV1,
    ) -> str:
        ticket = generate_opaque_token()
        expires_at = datetime.now(tz=UTC) + timedelta(minutes=5)
        await uow.auth.set_ws_ticket(
            actor.session_id,
            ticket_hash=hash_token(ticket),
            expires_at=expires_at,
        )
        return ticket

    async def resolve_actor_from_ws_ticket(
        self,
        uow: PostgresUnitOfWork,
        *,
        ticket: str | None,
    ) -> AuthenticatedActorV1:
        if not ticket:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="WebSocket authentication required",
                status_code=401,
            )
        row = await uow.auth.get_session_by_ws_ticket_hash(hash_token(ticket))
        if row is None:
            # Also accept active session cookie token for same-origin WS.
            try:
                return await self.resolve_actor_from_token(uow, raw_token=ticket)
            except AuthServiceError:
                raise AuthServiceError(
                    code=AuthErrorCode.UNAUTHENTICATED,
                    message="Invalid WebSocket credentials",
                    status_code=401,
                ) from None
        now = datetime.now(tz=UTC)
        if row.revoked_at is not None or row.expires_at <= now:
            raise AuthServiceError(
                code=AuthErrorCode.SESSION_EXPIRED,
                message="WebSocket session is no longer valid",
                status_code=401,
            )
        if row.ws_ticket_expires_at is None or row.ws_ticket_expires_at <= now:
            raise AuthServiceError(
                code=AuthErrorCode.SESSION_EXPIRED,
                message="WebSocket ticket expired",
                status_code=401,
            )
        user = await uow.auth.get_user(row.user_id)
        if user is None:
            raise AuthServiceError(
                code=AuthErrorCode.UNAUTHENTICATED,
                message="WebSocket user inactive",
                status_code=401,
            )
        return build_actor(
            user_id=user.user_id,
            display_name=user.display_name,
            roles=user.roles,
            session_id=row.session_id,
            auth_method=row.auth_method,
        )

    async def record_audit(
        self,
        uow: PostgresUnitOfWork,
        *,
        action: SecurityAuditActionV1,
        outcome: SecurityAuditOutcomeV1,
        actor_user_id: str | None = None,
        target: str | None = None,
        permission: PermissionV1 | None = None,
        reason_code: str | None = None,
        request_id: str | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        event = SecurityAuditEventV1(
            schema_version=SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
            event_id=generate_audit_event_id(),
            action=action,
            outcome=outcome,
            actor_user_id=actor_user_id,
            target=target,
            permission=permission,
            reason_code=reason_code,
            request_id=request_id,
            correlation_id=request_id,
            occurred_at=datetime.now(tz=UTC),
            details=details or {},
        )
        await uow.auth.add_security_audit_event(event)

    def session_response(
        self,
        *,
        actor: AuthenticatedActorV1 | None,
        session: SessionInfoV1 | None,
    ) -> AuthSessionResponseV1:
        return AuthSessionResponseV1(
            schema_version=1,
            authenticated=actor is not None,
            actor=actor,
            session=session,
        )


DEV_SEED_USERS: list[tuple[str, str, list[PlatformRoleV1]]] = [
    ("user:viewer-alpha", "Viewer Alpha", [PlatformRoleV1.VIEWER]),
    ("user:analyst-alpha", "Analyst Alpha", [PlatformRoleV1.ANALYST]),
    ("user:operator-alpha", "Operator Alpha", [PlatformRoleV1.OPERATOR]),
    ("user:scenario-author-alpha", "Scenario Author Alpha", [PlatformRoleV1.SCENARIO_AUTHOR]),
    ("user:admin-alpha", "Admin Alpha", [PlatformRoleV1.ADMIN]),
]
