"""Ownership + run-scoping for the Phase 3 copilot agent-session routes (ADR 0035).

The run-scoped agent routes let an operator task the defensive agents against a
run before any incident exists. Like every other run-scoped router they must be
owner-or-admin gated. ANALYST holds ``investigation:trigger`` but not
``runs:write`` — a non-owner *with* the route permission — so a 403 for ANALYST
proves the per-run ownership gate fires (not merely the RBAC permission gate).
"""

from __future__ import annotations

import pytest
from aegis_api.main import create_app
from aegis_contracts import load_settings
from fastapi.testclient import TestClient
from tests.integration.auth_helpers import auth_headers, login_as

OWNER = "user:operator-alpha"  # OPERATOR: runs:write + investigation:trigger
ANALYST = "user:analyst-alpha"  # ANALYST: investigation:trigger, NO runs:write
VIEWER = "user:viewer-alpha"  # VIEWER: investigation:read only
ADMIN = "user:admin-alpha"


@pytest.fixture
def api_client(migrated_database: None, db_session) -> TestClient:  # noqa: ARG001
    _ = db_session
    app = create_app(load_settings())
    with TestClient(app) as client:
        yield client


def _create_run(client: TestClient, *, seed: int, key: str) -> str:
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
    return response.json()["run"]["id"]


def _session_body() -> dict:
    return {
        "schemaVersion": 1,
        "role": "WATCHTOWER",
        "traceId": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "enqueueInitialTask": False,
        "providerId": "mock",
        "instructions": "Sweep current alerts and telemetry",
    }


def test_create_run_session_requires_owner_or_admin(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=3001, key="agent-own-3001")
    path = f"/api/v1/runs/{run_id}/agent-sessions"

    # Non-owner WITH investigation:trigger -> blocked by the ownership gate.
    analyst_csrf = login_as(api_client, user_id=ANALYST)
    forbidden = api_client.post(
        path, json=_session_body(), headers=auth_headers(analyst_csrf)
    )
    assert forbidden.status_code == 403, forbidden.text

    # Owner -> creates a run-scoped session (no incident).
    owner_csrf = login_as(api_client, user_id=OWNER)
    created = api_client.post(path, json=_session_body(), headers=auth_headers(owner_csrf))
    assert created.status_code == 200, created.text
    detail = created.json()
    assert detail["session"]["runId"] == run_id
    assert detail["session"]["incidentId"] is None


def test_list_run_sessions_requires_owner_or_admin(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=3002, key="agent-own-3002")
    path = f"/api/v1/runs/{run_id}/agent-sessions"

    owner_csrf = login_as(api_client, user_id=OWNER)
    created = api_client.post(path, json=_session_body(), headers=auth_headers(owner_csrf))
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]

    # Non-owner VIEWER (holds investigation:read) -> 403 from the ownership gate.
    login_as(api_client, user_id=VIEWER)
    assert api_client.get(path).status_code == 403

    # Owner sees the session it created.
    login_as(api_client, user_id=OWNER)
    owner_list = api_client.get(path)
    assert owner_list.status_code == 200, owner_list.text
    assert session_id in {s["session"]["id"] for s in owner_list.json()["sessions"]}

    # Admin reaches any run.
    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code == 200


def test_create_run_session_missing_run_is_404(api_client: TestClient) -> None:
    admin_csrf = login_as(api_client, user_id=ADMIN)
    missing = api_client.post(
        "/api/v1/runs/run_01ARZ3NDEKTSV4RRFFQ69G5MISS/agent-sessions",
        json=_session_body(),
        headers=auth_headers(admin_csrf),
    )
    assert missing.status_code == 404, missing.text
