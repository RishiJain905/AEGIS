"""Shared helpers for authenticated integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_api.auth.service import DEV_SEED_USERS
from aegis_api.db.session import get_db_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi.testclient import TestClient


async def seed_dev_auth_users() -> None:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        now = datetime.now(tz=UTC)
        for user_id, display_name, roles in DEV_SEED_USERS:
            await uow.auth.upsert_user(
                user_id=user_id,
                display_name=display_name,
                roles=roles,
                now=now,
            )


def login_as(
    client: TestClient,
    *,
    user_id: str = "user:operator-alpha",
) -> str:
    """Authenticate the TestClient and return the CSRF token."""
    response = client.post(
        "/api/v1/auth/dev/login",
        json={"schemaVersion": 1, "userId": user_id},
    )
    assert response.status_code == 200, response.text
    csrf = response.json()["session"]["csrfToken"]
    return csrf


def auth_headers(csrf: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf}


def issue_ws_ticket(client: TestClient, *, csrf: str) -> str:
    response = client.post("/api/v1/auth/ws-ticket", headers=auth_headers(csrf))
    assert response.status_code == 200, response.text
    return response.json()["ticket"]
