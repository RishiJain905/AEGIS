"""Integration tests for Phase 30 authentication against PostgreSQL."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from aegis_api.auth.service import DEV_SEED_USERS
from aegis_api.db.session import get_db_session_maker, init_db
from aegis_api.main import create_app
from aegis_contracts import load_settings
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires AEGIS_INTEGRATION_POSTGRES=1 and migrated PostgreSQL",
)


@pytest.fixture
async def auth_app():
    settings = load_settings()
    settings.AEGIS_DEV_AUTH_ENABLED = True
    init_db(settings)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        now = datetime.now(tz=UTC)
        for user_id, display_name, roles in DEV_SEED_USERS:
            await uow.auth.upsert_user(
                user_id=user_id,
                display_name=display_name,
                roles=roles,
                now=now,
            )
    app = create_app(settings)
    yield app


@pytest.mark.asyncio
async def test_dev_login_logout_and_revocation(auth_app) -> None:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unauth = await client.get("/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert unauth.status_code == 401
        assert unauth.json()["code"] == "UNAUTHENTICATED"

        login = await client.post(
            "/api/v1/auth/dev/login",
            json={"schemaVersion": 1, "userId": "user:operator-alpha"},
        )
        assert login.status_code == 200
        body = login.json()
        assert body["authenticated"] is True
        assert body["actor"]["userId"] == "user:operator-alpha"
        assert "aegis_session" in login.cookies
        csrf = body["session"]["csrfToken"]

        session = await client.get("/api/v1/auth/session")
        assert session.json()["authenticated"] is True

        denied_without_csrf = await client.post("/api/v1/auth/ws-ticket")
        assert denied_without_csrf.status_code == 403
        assert denied_without_csrf.json()["code"] == "CSRF_FAILED"

        ticket = await client.post(
            "/api/v1/auth/ws-ticket",
            headers={"X-CSRF-Token": csrf},
        )
        assert ticket.status_code == 200
        assert ticket.json()["ticket"]

        # Authenticated operator can call a protected read endpoint (404 for unknown run is ok).
        protected = await client.get("/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert protected.status_code in {200, 404}
        assert protected.status_code != 401

        logout = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert logout.status_code == 200
        after = await client.get("/api/v1/auth/session")
        assert after.json()["authenticated"] is False
        blocked = await client.get("/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert blocked.status_code == 401


@pytest.mark.asyncio
async def test_client_supplied_actor_cannot_elevate_approval(auth_app) -> None:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/dev/login",
            json={"schemaVersion": 1, "userId": "user:viewer-alpha"},
        )
        csrf = login.json()["session"]["csrfToken"]
        response = await client.post(
            "/api/v1/action-proposals/prp_01ARZ3NDEKTSV4RRFFQ69G5FAV/approve",
            headers={
                "X-CSRF-Token": csrf,
                "X-Actor-Id": "user:admin-alpha",
                "Authorization": "Bearer synthetic-operator-token",
            },
            json={
                "schemaVersion": 1,
                "proposalId": "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "expectedRevisionId": "rev-1",
                "expectedRevision": 1,
                "idempotencyKey": "idem-1",
                "actorId": "user:admin-alpha",
                "comment": "forged",
            },
        )
        assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_tampered_session_cookie_rejected(auth_app) -> None:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("aegis_session", "tampered-not-a-real-session")
        response = await client.get("/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert response.status_code == 401
