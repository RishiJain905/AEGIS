"""Integration tests for run ownership and tenancy (AEGIS-OITB-008).

Verifies runs are owned by the creating actor: listing is caller-scoped (admins see
all), and opening/commanding a run requires owner-or-admin. See ADR 0034.
"""

from __future__ import annotations

import pytest
from aegis_api.main import create_app
from aegis_contracts import load_settings
from fastapi.testclient import TestClient
from tests.integration.auth_helpers import auth_headers, login_as

# operator-alpha holds runs:write (can create + own); viewer-alpha is a different
# non-admin (runs:read only, owns nothing); admin-alpha holds admin:manage.
OWNER = "user:operator-alpha"
OTHER = "user:viewer-alpha"
ADMIN = "user:admin-alpha"


@pytest.fixture
def api_client(migrated_database: None, db_session) -> TestClient:  # noqa: ARG001
    _ = db_session
    app = create_app(load_settings())
    with TestClient(app) as client:
        yield client


def _create_run(client: TestClient, *, seed: int, key: str) -> dict:
    csrf = login_as(client, user_id=OWNER)
    response = client.post(
        "/api/v1/runs",
        json={
            "schemaVersion": 1,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
            "seed": seed,
        },
        headers={"Idempotency-Key": key, **auth_headers(csrf)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_run_records_owner(api_client: TestClient) -> None:
    payload = _create_run(api_client, seed=2001, key="own-create-2001")
    assert payload["run"]["ownerUserId"] == OWNER


def test_list_runs_is_scoped_to_caller(api_client: TestClient) -> None:
    created = _create_run(api_client, seed=2002, key="own-create-2002")
    run_id = created["run"]["id"]

    # A different non-admin never sees the owner's run.
    login_as(api_client, user_id=OTHER)
    other_list = api_client.get("/api/v1/runs")
    assert other_list.status_code == 200, other_list.text
    assert run_id not in {run["id"] for run in other_list.json()}

    # The owner sees their own run.
    login_as(api_client, user_id=OWNER)
    owner_list = api_client.get("/api/v1/runs")
    assert owner_list.status_code == 200
    assert run_id in {run["id"] for run in owner_list.json()}

    # An admin sees all runs, including one they do not own.
    login_as(api_client, user_id=ADMIN)
    admin_list = api_client.get("/api/v1/runs")
    assert admin_list.status_code == 200
    assert run_id in {run["id"] for run in admin_list.json()}


def test_get_run_requires_owner_or_admin(api_client: TestClient) -> None:
    created = _create_run(api_client, seed=2003, key="own-create-2003")
    run_id = created["run"]["id"]

    # Non-owner, non-admin -> 403.
    login_as(api_client, user_id=OTHER)
    forbidden = api_client.get(f"/api/v1/runs/{run_id}")
    assert forbidden.status_code == 403, forbidden.text
    assert forbidden.json()["code"] == "FORBIDDEN"

    # Owner -> 200.
    login_as(api_client, user_id=OWNER)
    assert api_client.get(f"/api/v1/runs/{run_id}").status_code == 200

    # Admin -> 200.
    login_as(api_client, user_id=ADMIN)
    assert api_client.get(f"/api/v1/runs/{run_id}").status_code == 200


def test_lifecycle_command_requires_owner_or_admin(api_client: TestClient) -> None:
    created = _create_run(api_client, seed=2004, key="own-create-2004")
    run_id = created["run"]["id"]

    # A different non-admin cannot command the run.
    other_csrf = login_as(api_client, user_id=OTHER)
    forbidden = api_client.post(
        f"/api/v1/runs/{run_id}/pause",
        headers={"Idempotency-Key": "own-pause-forbidden", **auth_headers(other_csrf)},
    )
    assert forbidden.status_code == 403, forbidden.text

    # The owner can command their own run.
    owner_csrf = login_as(api_client, user_id=OWNER)
    allowed = api_client.post(
        f"/api/v1/runs/{run_id}/pause",
        headers={"Idempotency-Key": "own-pause-allowed", **auth_headers(owner_csrf)},
    )
    assert allowed.status_code == 200, allowed.text


def test_get_missing_run_is_404(api_client: TestClient) -> None:
    login_as(api_client, user_id=ADMIN)
    missing = api_client.get("/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5MISS")
    assert missing.status_code == 404, missing.text
