"""Integration tests for run ownership and tenancy (AEGIS-OITB-008).

Verifies runs are owned by the creating actor: listing is caller-scoped (admins see
all), and opening/commanding a run requires owner-or-admin. See ADR 0034.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aegis_api.main import create_app
from aegis_contracts import IncidentState, IncidentV1, load_settings
from aegis_contracts.versioning import INCIDENT_SCHEMA_VERSION
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi.testclient import TestClient
from sqlalchemy import text
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


# ---------------------------------------------------------------------------
# Cross-router ownership (reports / replay / scoring / investigation).
#
# Before this fix these routers enforced only global RBAC (a read permission
# every role, including VIEWER, holds), so any authenticated user could read any
# run's after-action / replay / score / investigation artifacts by run_id. The
# tests below exercise a representative endpoint of each router: the non-owner is
# a VIEWER, which passes the router's mount-level RBAC and must now be stopped by
# the per-run owner-or-admin gate (403), while the owner and admin pass it.
# ---------------------------------------------------------------------------


def _seed_incident(run_id: str, incident_id: str) -> None:
    """Insert a minimal OPEN incident for ``run_id`` on a dedicated event loop."""

    async def _run() -> None:
        settings = load_settings()
        engine = create_engine(settings)
        try:
            session_maker = get_session_maker(settings, engine=engine)
            async with PostgresUnitOfWork(session_maker) as uow:
                now = datetime.now(tz=UTC)
                await uow.incidents.add(
                    IncidentV1(
                        schema_version=INCIDENT_SCHEMA_VERSION,
                        id=incident_id,
                        run_id=run_id,
                        title="ownership probe incident",
                        state=IncidentState.OPEN,
                        alert_ids=[],
                        revision=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
        finally:
            await dispose_engine(engine)

    asyncio.run(_run())


def _null_run_owner(run_id: str) -> None:
    """Make a run ownerless (legacy row) on a dedicated event loop.

    Ownership is read from the run's JSONB ``payload`` (see ``run_to_domain``), so
    the ``ownerUserId`` payload key must be removed as well as the mirror column.
    """

    async def _run() -> None:
        settings = load_settings()
        engine = create_engine(settings)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE runs SET owner_user_id = NULL, "
                        "payload = payload - 'ownerUserId' WHERE id = :rid"
                    ),
                    {"rid": run_id},
                )
        finally:
            await dispose_engine(engine)

    asyncio.run(_run())


def test_reports_router_enforces_run_ownership(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2101, key="own-create-2101")["run"]["id"]
    path = f"/api/v1/runs/{run_id}/after-action-report/versions"

    login_as(api_client, user_id=OTHER)
    assert api_client.get(path).status_code == 403

    login_as(api_client, user_id=OWNER)
    assert api_client.get(path).status_code == 200  # gate passed; empty version list

    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code == 200


def test_replay_router_enforces_run_ownership(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2102, key="own-create-2102")["run"]["id"]
    path = f"/api/v1/replay/runs/{run_id}/snapshots"

    login_as(api_client, user_id=OTHER)
    assert api_client.get(path).status_code == 403

    login_as(api_client, user_id=OWNER)
    assert api_client.get(path).status_code == 200  # gate passed; empty snapshot list

    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code == 200


def test_scoring_router_enforces_run_ownership(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2103, key="own-create-2103")["run"]["id"]
    path = f"/api/v1/runs/{run_id}/score"

    login_as(api_client, user_id=OTHER)
    assert api_client.get(path).status_code == 403

    # No score exists yet, so the owner/admin pass the gate and get 404 (never 403).
    login_as(api_client, user_id=OWNER)
    assert api_client.get(path).status_code == 404

    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code == 404


def test_blast_radius_router_enforces_run_ownership(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2106, key="own-create-2106")["run"]["id"]
    path = (
        f"/api/v1/runs/{run_id}/blast-radius"
        "?assetId=asset:svc-logistics-api&command=isolate"
    )

    # Non-owner, non-admin -> 403.
    login_as(api_client, user_id=OTHER)
    assert api_client.get(path).status_code == 403

    # Owner/admin pass the gate; the run's initial graph snapshot yields a preview.
    login_as(api_client, user_id=OWNER)
    owner_response = api_client.get(path)
    assert owner_response.status_code == 200, owner_response.text
    body = owner_response.json()
    assert body["command"] == "isolate"
    assert body["actionClass"] == "class_2"
    assert body["targetAssetId"] == "asset:svc-logistics-api"

    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code == 200


def test_blast_radius_rejects_unknown_command(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2107, key="own-create-2107")["run"]["id"]
    login_as(api_client, user_id=OWNER)
    response = api_client.get(
        f"/api/v1/runs/{run_id}/blast-radius?assetId=asset:svc-logistics-api&command=nope"
    )
    assert response.status_code == 400, response.text


def test_investigation_router_enforces_run_ownership(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2104, key="own-create-2104")["run"]["id"]
    incident_id = "incident:inc_ownershipprobe01"
    _seed_incident(run_id, incident_id)
    path = f"/api/v1/incidents/{incident_id}/investigation"

    login_as(api_client, user_id=OTHER)
    assert api_client.get(path).status_code == 403

    # Owner/admin resolve the incident's run and pass the gate (not 403).
    login_as(api_client, user_id=OWNER)
    assert api_client.get(path).status_code != 403

    login_as(api_client, user_id=ADMIN)
    assert api_client.get(path).status_code != 403


def test_cross_router_null_owner_is_admin_only(api_client: TestClient) -> None:
    run_id = _create_run(api_client, seed=2105, key="own-create-2105")["run"]["id"]
    _null_run_owner(run_id)
    versions_path = f"/api/v1/runs/{run_id}/after-action-report/versions"
    snapshots_path = f"/api/v1/replay/runs/{run_id}/snapshots"

    # The original creator is now a non-admin against an ownerless run -> 403.
    login_as(api_client, user_id=OWNER)
    assert api_client.get(versions_path).status_code == 403
    assert api_client.get(snapshots_path).status_code == 403

    # Admin still reaches ownerless runs.
    login_as(api_client, user_id=ADMIN)
    assert api_client.get(versions_path).status_code == 200
    assert api_client.get(snapshots_path).status_code == 200
