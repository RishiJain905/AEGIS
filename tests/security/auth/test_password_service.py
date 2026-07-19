"""Offline unit tests for the password AuthService flows.

Uses an in-memory fake unit-of-work so the security-critical service logic — first-run
admin bootstrap self-disable, generic no-enumeration login failure, and hashed-only
storage — is covered by the offline gate without PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from aegis_api.auth.passwords import hash_password
from aegis_api.auth.service import AuthService, AuthServiceError
from aegis_contracts import AuthErrorCode, PlatformRoleV1, SessionInfoV1
from aegis_persistence.repositories.auth import AuthCredentialRecord, AuthUserRecord


class _FakeAuthRepo:
    def __init__(self) -> None:
        self.users: dict[str, AuthUserRecord] = {}
        self.credentials: dict[str, tuple[str, str]] = {}  # user_id -> (hash, algo)
        self.audit_events: list[object] = []
        self.sessions: dict[str, SessionInfoV1] = {}

    async def count_credentialed_users(self) -> int:
        return len(self.credentials)

    async def username_exists(self, username: str) -> bool:
        return any(u.username == username for u in self.users.values())

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
        record = AuthUserRecord(
            user_id=user_id,
            display_name=display_name,
            status="active",
            roles=roles,
            username=username,
        )
        self.users[user_id] = record
        self.credentials[user_id] = (password_hash, algorithm)
        return record

    async def get_user(self, user_id: str) -> AuthUserRecord | None:
        return self.users.get(user_id)

    async def get_credential_by_username(self, username: str) -> AuthCredentialRecord | None:
        for user in self.users.values():
            if user.username == username and user.user_id in self.credentials:
                password_hash, algorithm = self.credentials[user.user_id]
                return AuthCredentialRecord(
                    user=user, password_hash=password_hash, algorithm=algorithm
                )
        return None

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
        info = SessionInfoV1(
            schema_version=1,
            session_id=session_id,
            user_id=user_id,
            auth_method=auth_method,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=None,
            csrf_token=csrf_token,
        )
        self.sessions[session_id] = info
        return info

    async def add_security_audit_event(self, event: object) -> None:
        self.audit_events.append(event)


class _FakeUow:
    def __init__(self) -> None:
        self.auth = _FakeAuthRepo()


@pytest.mark.asyncio
async def test_bootstrap_admin_creates_first_admin_then_self_disables() -> None:
    service = AuthService(session_ttl_seconds=3600)
    uow = _FakeUow()

    assert await service.setup_required(uow) is True
    actor, session, raw_token = await service.bootstrap_admin(
        uow, username="Admin1", password="longenough-pass1", display_name="Root"
    )
    assert PlatformRoleV1.ADMIN in actor.roles
    assert raw_token
    assert session.csrf_token
    # Password is stored only as a hash, never plaintext.
    stored_hash, _algo = uow.auth.credentials[actor.user_id]
    assert "longenough-pass1" not in stored_hash

    # Setup is now closed.
    assert await service.setup_required(uow) is False
    with pytest.raises(AuthServiceError) as exc:
        await service.bootstrap_admin(
            uow, username="Admin2", password="another-pass99", display_name="Second"
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_login_unknown_user_and_wrong_password_are_indistinguishable() -> None:
    service = AuthService(session_ttl_seconds=3600)
    uow = _FakeUow()
    now = datetime.now(tz=UTC)
    uow.auth.users["user:acct_1"] = AuthUserRecord(
        user_id="user:acct_1",
        display_name="Op",
        status="active",
        roles=[PlatformRoleV1.OPERATOR],
        username="operator",
    )
    uow.auth.credentials["user:acct_1"] = (hash_password("realpassword-1"), "argon2id")

    with pytest.raises(AuthServiceError) as unknown:
        await service.authenticate_password(uow, username="ghost", password="whatever-1")
    with pytest.raises(AuthServiceError) as wrong:
        await service.authenticate_password(uow, username="operator", password="wrongpass-1")

    assert unknown.value.code == AuthErrorCode.INVALID_CREDENTIALS
    assert wrong.value.code == AuthErrorCode.INVALID_CREDENTIALS
    assert unknown.value.message == wrong.value.message
    assert unknown.value.status_code == wrong.value.status_code == 401
    _ = now


@pytest.mark.asyncio
async def test_login_success_issues_session() -> None:
    service = AuthService(session_ttl_seconds=3600)
    uow = _FakeUow()
    uow.auth.users["user:acct_1"] = AuthUserRecord(
        user_id="user:acct_1",
        display_name="Op",
        status="active",
        roles=[PlatformRoleV1.OPERATOR],
        username="operator",
    )
    uow.auth.credentials["user:acct_1"] = (hash_password("realpassword-1"), "argon2id")

    actor, session, raw_token = await service.authenticate_password(
        uow, username="operator", password="realpassword-1"
    )
    assert actor.user_id == "user:acct_1"
    assert actor.auth_method.value == "password"
    assert raw_token
    assert session.expires_at > datetime.now(tz=UTC) - timedelta(seconds=1)
