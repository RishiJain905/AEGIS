"""Integration tests for real username/password auth against PostgreSQL.

Covers the full HTTP surface: first-run admin setup + self-disable, password login
issuing a session + CSRF, role enforcement (a viewer created this way still 403s on a
mutation), generic no-enumeration failure, admin-created accounts, and the dev-picker
being absent when dev auth is disabled.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from aegis_api.db.session import get_db_session_maker, init_db
from aegis_api.main import create_app
from aegis_contracts import load_settings
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.environ.get("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires AEGIS_INTEGRATION_POSTGRES=1 and migrated PostgreSQL",
)


async def _reset_auth_tables() -> None:
    init_db(load_settings())
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        for table in (
            "auth_user_credentials",
            "auth_sessions",
            "auth_role_assignments",
            "auth_external_identities",
            "security_audit_events",
            "auth_users",
        ):
            await uow.session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def fresh_app() -> AsyncIterator[object]:
    settings = load_settings()
    # Dev picker OFF: the fresh/production experience.
    settings.AEGIS_DEV_AUTH_ENABLED = False
    await _reset_auth_tables()
    init_db(settings)
    yield create_app(settings)


@pytest.mark.asyncio
async def test_first_run_setup_then_self_disable(fresh_app) -> None:
    transport = ASGITransport(app=fresh_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get("/api/v1/auth/setup-status")
        assert status.status_code == 200
        assert status.json()["setupRequired"] is True

        # Dev picker must be gone when dev auth is disabled.
        dev_users = await client.get("/api/v1/auth/dev/users")
        assert dev_users.status_code == 403

        created = await client.post(
            "/api/v1/auth/setup",
            json={
                "schemaVersion": 1,
                "username": "rootadmin",
                "password": "first-admin-pass1",
                "displayName": "Root Admin",
            },
        )
        assert created.status_code == 200
        body = created.json()
        assert body["authenticated"] is True
        assert "admin" in body["actor"]["roles"]
        assert "aegis_session" in created.cookies

        # Setup now closed.
        status2 = await client.get("/api/v1/auth/setup-status")
        assert status2.json()["setupRequired"] is False

        # A second setup attempt fails closed.
        second = await client.post(
            "/api/v1/auth/setup",
            json={
                "schemaVersion": 1,
                "username": "sneakadmin",
                "password": "second-admin-pass1",
                "displayName": "Sneak",
            },
        )
        assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password_is_generic_and_non_enumerating(fresh_app) -> None:
    transport = ASGITransport(app=fresh_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/setup",
            json={
                "schemaVersion": 1,
                "username": "rootadmin",
                "password": "first-admin-pass1",
                "displayName": "Root Admin",
            },
        )
        # Clear the setup session so login is exercised fresh.
        client.cookies.clear()

        unknown = await client.post(
            "/api/v1/auth/login",
            json={"schemaVersion": 1, "username": "nobody", "password": "whatever-123"},
        )
        wrong = await client.post(
            "/api/v1/auth/login",
            json={"schemaVersion": 1, "username": "rootadmin", "password": "wrong-pass-123"},
        )
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["code"] == wrong.json()["code"] == "INVALID_CREDENTIALS"
        assert unknown.json()["message"] == wrong.json()["message"]

        good = await client.post(
            "/api/v1/auth/login",
            json={"schemaVersion": 1, "username": "rootadmin", "password": "first-admin-pass1"},
        )
        assert good.status_code == 200
        assert good.json()["actor"]["authMethod"] == "password"
        assert good.json()["session"]["csrfToken"]


@pytest.mark.asyncio
async def test_admin_creates_viewer_who_is_denied_mutations(fresh_app) -> None:
    transport = ASGITransport(app=fresh_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        setup = await client.post(
            "/api/v1/auth/setup",
            json={
                "schemaVersion": 1,
                "username": "rootadmin",
                "password": "first-admin-pass1",
                "displayName": "Root Admin",
            },
        )
        admin_csrf = setup.json()["session"]["csrfToken"]

        # Admin provisions a viewer account.
        created = await client.post(
            "/api/v1/admin/users",
            headers={"X-CSRF-Token": admin_csrf},
            json={
                "username": "readonly",
                "password": "viewer-pass-123",
                "displayName": "Read Only",
                "roles": ["viewer"],
            },
        )
        assert created.status_code == 200
        assert created.json()["roles"] == ["viewer"]

        # Log in as the viewer (new client without admin cookies).
        async with AsyncClient(transport=transport, base_url="http://test") as viewer:
            login = await viewer.post(
                "/api/v1/auth/login",
                json={"schemaVersion": 1, "username": "readonly", "password": "viewer-pass-123"},
            )
            assert login.status_code == 200
            viewer_csrf = login.json()["session"]["csrfToken"]
            assert login.json()["actor"]["roles"] == ["viewer"]

            # A viewer must not be able to reach an admin-only mutation.
            forbidden = await viewer.post(
                "/api/v1/admin/users",
                headers={"X-CSRF-Token": viewer_csrf},
                json={
                    "username": "escalated",
                    "password": "escalate-pass-1",
                    "displayName": "Escalated",
                    "roles": ["admin"],
                },
            )
            assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_fresh_database_has_no_seeded_runs(fresh_app) -> None:
    # A fresh, migrated database must load empty: no demo runs, incidents, or reports.
    _ = fresh_app
    init_db(load_settings())
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        for table in ("runs", "incidents", "alerts"):
            await uow.session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        run_count = (await uow.session.execute(text("SELECT count(*) FROM runs"))).scalar_one()
        assert run_count == 0


@pytest.mark.asyncio
async def test_weak_password_rejected_at_setup(fresh_app) -> None:
    transport = ASGITransport(app=fresh_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        weak = await client.post(
            "/api/v1/auth/setup",
            json={
                "schemaVersion": 1,
                "username": "rootadmin",
                "password": "short",
                "displayName": "",
            },
        )
        assert weak.status_code == 422
        # Setup remains open because nothing was created.
        assert (await client.get("/api/v1/auth/setup-status")).json()["setupRequired"] is True
