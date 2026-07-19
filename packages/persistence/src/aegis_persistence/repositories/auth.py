"""Phase 30 authentication persistence repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aegis_contracts import (
    PermissionV1,
    PlatformRoleV1,
    ResourceAccessGrantV1,
    SecurityAuditEventV1,
    SessionInfoV1,
)
from aegis_contracts.versioning import (
    RESOURCE_ACCESS_GRANT_SCHEMA_VERSION,
    SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
    SESSION_INFO_SCHEMA_VERSION,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.orm.tables import (
    AuthExternalIdentityRow,
    AuthResourceGrantRow,
    AuthRoleAssignmentRow,
    AuthSessionRow,
    AuthUserCredentialRow,
    AuthUserRow,
    SecurityAuditEventRow,
)


class AuthUserRecord:
    def __init__(
        self,
        *,
        user_id: str,
        display_name: str,
        status: str,
        roles: list[PlatformRoleV1],
        username: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.display_name = display_name
        self.status = status
        self.roles = roles
        self.username = username


class AuthCredentialRecord:
    """A user's login identity plus its stored password hash for verification."""

    def __init__(
        self,
        *,
        user: AuthUserRecord,
        password_hash: str,
        algorithm: str,
    ) -> None:
        self.user = user
        self.password_hash = password_hash
        self.algorithm = algorithm


class PostgresAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str,
        roles: list[PlatformRoleV1],
        status: str = "active",
        username: str | None = None,
        now: datetime,
    ) -> AuthUserRecord:
        row = await self._session.get(AuthUserRow, user_id)
        if row is None:
            row = AuthUserRow(
                user_id=user_id,
                display_name=display_name,
                username=username,
                status=status,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.display_name = display_name
            row.status = status
            row.updated_at = now
            if username is not None:
                row.username = username

        existing = await self._session.execute(
            select(AuthRoleAssignmentRow).where(AuthRoleAssignmentRow.user_id == user_id)
        )
        for assignment in existing.scalars().all():
            await self._session.delete(assignment)
        for role in roles:
            self._session.add(
                AuthRoleAssignmentRow(
                    id=f"{user_id}:{role.value}",
                    user_id=user_id,
                    role=role.value,
                    created_at=now,
                )
            )
        await self._session.flush()
        return AuthUserRecord(
            user_id=user_id,
            display_name=display_name,
            status=status,
            roles=roles,
            username=username,
        )

    async def get_user(self, user_id: str) -> AuthUserRecord | None:
        row = await self._session.get(AuthUserRow, user_id)
        if row is None or row.status != "active":
            return None
        roles = await self._roles_for(user_id)
        if not roles:
            return None
        return AuthUserRecord(
            user_id=row.user_id,
            display_name=row.display_name,
            status=row.status,
            roles=roles,
            username=row.username,
        )

    async def _roles_for(self, user_id: str) -> list[PlatformRoleV1]:
        roles_result = await self._session.execute(
            select(AuthRoleAssignmentRow).where(AuthRoleAssignmentRow.user_id == user_id)
        )
        return [PlatformRoleV1(item.role) for item in roles_result.scalars().all()]

    async def count_credentialed_users(self) -> int:
        """Number of accounts that have a password credential.

        The first-run admin bootstrap is available only while this is zero; once any
        password account exists it self-disables. Independent of dev-seed identities,
        which have no credential row.
        """
        result = await self._session.execute(
            select(func.count()).select_from(AuthUserCredentialRow)
        )
        return int(result.scalar_one())

    async def username_exists(self, username: str) -> bool:
        result = await self._session.execute(
            select(AuthUserRow.user_id).where(AuthUserRow.username == username)
        )
        return result.scalar_one_or_none() is not None

    async def create_credentialed_user(
        self,
        *,
        user_id: str,
        username: str,
        display_name: str,
        roles: list[PlatformRoleV1],
        password_hash: str,
        algorithm: str,
        now: datetime,
    ) -> AuthUserRecord:
        """Create an active user with roles and a password credential in one unit."""
        record = await self.upsert_user(
            user_id=user_id,
            display_name=display_name,
            roles=roles,
            username=username,
            now=now,
        )
        self._session.add(
            AuthUserCredentialRow(
                user_id=user_id,
                password_hash=password_hash,
                algorithm=algorithm,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()
        return record

    async def get_credential_by_username(self, username: str) -> AuthCredentialRecord | None:
        """Return the credential + identity for an active, credentialed username."""
        user_result = await self._session.execute(
            select(AuthUserRow).where(AuthUserRow.username == username)
        )
        user_row = user_result.scalar_one_or_none()
        if user_row is None or user_row.status != "active":
            return None
        credential = await self._session.get(AuthUserCredentialRow, user_row.user_id)
        if credential is None:
            return None
        roles = await self._roles_for(user_row.user_id)
        if not roles:
            return None
        return AuthCredentialRecord(
            user=AuthUserRecord(
                user_id=user_row.user_id,
                display_name=user_row.display_name,
                status=user_row.status,
                roles=roles,
                username=user_row.username,
            ),
            password_hash=credential.password_hash,
            algorithm=credential.algorithm,
        )

    async def link_external_identity(
        self,
        *,
        identity_id: str,
        user_id: str,
        issuer: str,
        subject: str,
        now: datetime,
    ) -> None:
        existing = await self._session.execute(
            select(AuthExternalIdentityRow).where(
                AuthExternalIdentityRow.issuer == issuer,
                AuthExternalIdentityRow.subject == subject,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            self._session.add(
                AuthExternalIdentityRow(
                    id=identity_id,
                    user_id=user_id,
                    issuer=issuer,
                    subject=subject,
                    created_at=now,
                )
            )
        else:
            row.user_id = user_id
        await self._session.flush()

    async def get_user_by_external_identity(
        self, *, issuer: str, subject: str
    ) -> AuthUserRecord | None:
        result = await self._session.execute(
            select(AuthExternalIdentityRow).where(
                AuthExternalIdentityRow.issuer == issuer,
                AuthExternalIdentityRow.subject == subject,
            )
        )
        identity = result.scalar_one_or_none()
        if identity is None:
            return None
        return await self.get_user(identity.user_id)

    async def create_session(
        self,
        *,
        session_id: str,
        session_token_hash: str,
        user_id: str,
        auth_method: str,
        csrf_token: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> SessionInfoV1:
        self._session.add(
            AuthSessionRow(
                session_id=session_id,
                session_token_hash=session_token_hash,
                user_id=user_id,
                auth_method=auth_method,
                csrf_token=csrf_token,
                created_at=created_at,
                expires_at=expires_at,
                revoked_at=None,
            )
        )
        await self._session.flush()
        return SessionInfoV1(
            schema_version=SESSION_INFO_SCHEMA_VERSION,
            session_id=session_id,
            user_id=user_id,
            auth_method=auth_method,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=None,
            csrf_token=csrf_token,
        )

    async def get_session_by_token_hash(self, token_hash: str) -> AuthSessionRow | None:
        result = await self._session.execute(
            select(AuthSessionRow).where(AuthSessionRow.session_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_session(self, session_id: str) -> AuthSessionRow | None:
        return await self._session.get(AuthSessionRow, session_id)

    async def revoke_session(self, session_id: str, *, revoked_at: datetime) -> None:
        row = await self._session.get(AuthSessionRow, session_id)
        if row is None:
            return
        row.revoked_at = revoked_at
        await self._session.flush()

    async def set_ws_ticket(
        self,
        session_id: str,
        *,
        ticket_hash: str,
        expires_at: datetime,
    ) -> None:
        row = await self._session.get(AuthSessionRow, session_id)
        if row is None:
            return
        row.ws_ticket_hash = ticket_hash
        row.ws_ticket_expires_at = expires_at
        await self._session.flush()

    async def get_session_by_ws_ticket_hash(self, ticket_hash: str) -> AuthSessionRow | None:
        result = await self._session.execute(
            select(AuthSessionRow).where(AuthSessionRow.ws_ticket_hash == ticket_hash)
        )
        return result.scalar_one_or_none()

    async def list_grants_for_user(self, user_id: str) -> list[ResourceAccessGrantV1]:
        result = await self._session.execute(
            select(AuthResourceGrantRow).where(AuthResourceGrantRow.user_id == user_id)
        )
        grants: list[ResourceAccessGrantV1] = []
        for row in result.scalars().all():
            grants.append(
                ResourceAccessGrantV1(
                    schema_version=RESOURCE_ACCESS_GRANT_SCHEMA_VERSION,
                    grant_id=row.grant_id,
                    user_id=row.user_id,
                    resource_type=row.resource_type,
                    resource_id=row.resource_id,
                    permissions=[PermissionV1(item) for item in row.permissions],
                    created_at=row.created_at,
                )
            )
        return grants

    async def upsert_grant(
        self,
        *,
        grant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        permissions: list[str],
        created_at: datetime,
    ) -> None:
        row = await self._session.get(AuthResourceGrantRow, grant_id)
        if row is None:
            self._session.add(
                AuthResourceGrantRow(
                    grant_id=grant_id,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permissions=permissions,
                    created_at=created_at,
                )
            )
        else:
            row.permissions = permissions
        await self._session.flush()

    async def add_security_audit_event(self, event: SecurityAuditEventV1) -> None:
        self._session.add(
            SecurityAuditEventRow(
                event_id=event.event_id,
                action=event.action.value,
                outcome=event.outcome.value,
                actor_user_id=event.actor_user_id,
                target=event.target,
                permission=event.permission.value if event.permission else None,
                reason_code=event.reason_code,
                request_id=event.request_id,
                correlation_id=event.correlation_id,
                occurred_at=event.occurred_at,
                details=dict(event.details),
            )
        )
        await self._session.flush()

    async def list_security_audit_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(SecurityAuditEventRow)
            .order_by(SecurityAuditEventRow.occurred_at.desc())
            .limit(limit)
        )
        return [
            {
                "schemaVersion": SECURITY_AUDIT_EVENT_SCHEMA_VERSION,
                "eventId": row.event_id,
                "action": row.action,
                "outcome": row.outcome,
                "actorUserId": row.actor_user_id,
                "target": row.target,
                "permission": row.permission,
                "reasonCode": row.reason_code,
                "requestId": row.request_id,
                "correlationId": row.correlation_id,
                "occurredAt": row.occurred_at.isoformat().replace("+00:00", "Z"),
                "details": row.details,
            }
            for row in result.scalars().all()
        ]
