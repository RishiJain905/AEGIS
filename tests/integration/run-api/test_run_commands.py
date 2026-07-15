"""Integration tests for run command HTTP API."""

from __future__ import annotations

import pytest
from aegis_api.main import create_app
from aegis_contracts import load_settings
from fastapi.testclient import TestClient
from tests.integration.auth_helpers import auth_headers, login_as


@pytest.fixture
def api_client(migrated_database: None, db_session) -> TestClient:  # noqa: ARG001
    _ = db_session
    app = create_app(load_settings())
    with TestClient(app) as client:
        yield client


def test_create_run_start_and_step(api_client: TestClient) -> None:
    csrf = login_as(api_client)
    create_response = api_client.post(
        "/api/v1/runs",
        json={
            "schemaVersion": 1,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
            "seed": 1000,
        },
        headers={"Idempotency-Key": "integration-create-1000", **auth_headers(csrf)},
    )
    assert create_response.status_code == 200, create_response.text
    payload = create_response.json()
    run_id = payload["run"]["id"]

    graph_response = api_client.get(f"/api/v1/runs/{run_id}/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert graph["runId"] == run_id
    assert len(graph["nodes"]) > 0

    step_response = api_client.post(
        f"/api/v1/runs/{run_id}/step",
        headers={"Idempotency-Key": "integration-step-1", **auth_headers(csrf)},
    )
    assert step_response.status_code == 200, step_response.text

    bootstrap_response = api_client.get(f"/api/v1/runs/{run_id}/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    assert bootstrap["lastAppliedSequence"] >= 1


def test_run_command_idempotency(api_client: TestClient) -> None:
    csrf = login_as(api_client)
    create_response = api_client.post(
        "/api/v1/runs",
        json={
            "schemaVersion": 1,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
            "seed": 1006,
        },
        headers={"Idempotency-Key": "integration-idempotent-create", **auth_headers(csrf)},
    )
    assert create_response.status_code == 200
    run_id = create_response.json()["run"]["id"]

    first = api_client.post(
        f"/api/v1/runs/{run_id}/pause",
        headers={"Idempotency-Key": "integration-pause-once", **auth_headers(csrf)},
    )
    second = api_client.post(
        f"/api/v1/runs/{run_id}/pause",
        headers={"Idempotency-Key": "integration-pause-once", **auth_headers(csrf)},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotency"]["replayed"] is True
