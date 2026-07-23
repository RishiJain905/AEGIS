"""Integration tests for the operator skill-telemetry profile endpoint.

Verifies the endpoint is owner-scoped: a caller reads their own profile, cannot read another
user's profile (403) unless they are an admin.
"""

from __future__ import annotations

import pytest
from aegis_api.main import create_app
from aegis_contracts import load_settings
from fastapi.testclient import TestClient
from tests.integration.auth_helpers import login_as

OWNER = "user:operator-alpha"
OTHER = "user:viewer-alpha"
ADMIN = "user:admin-alpha"


@pytest.fixture
def api_client(migrated_database: None, db_session) -> TestClient:  # noqa: ARG001
    _ = db_session
    app = create_app(load_settings())
    with TestClient(app) as client:
        yield client


def test_operator_profile_returns_own_profile(api_client: TestClient) -> None:
    login_as(api_client, user_id=OWNER)
    response = api_client.get("/api/v1/profile/operator")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ownerUserId"] == OWNER
    assert body["metrics"]["runsAnalyzed"] >= 0
    assert isinstance(body["coaching"], list)


def test_operator_profile_rejects_reading_another_user(api_client: TestClient) -> None:
    login_as(api_client, user_id=OWNER)
    forbidden = api_client.get("/api/v1/profile/operator", params={"userId": OTHER})
    assert forbidden.status_code == 403, forbidden.text


def test_admin_may_read_another_users_profile(api_client: TestClient) -> None:
    login_as(api_client, user_id=ADMIN)
    response = api_client.get("/api/v1/profile/operator", params={"userId": OWNER})
    assert response.status_code == 200, response.text
    assert response.json()["ownerUserId"] == OWNER
