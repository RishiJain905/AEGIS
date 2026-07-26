"""Integration tests for the ``restartExisting`` reset-and-replay relaunch.

Run ids are derived from (seed, scenarioVersionId), so a pinned-seed scenario — the guided
tutorial launches at a fixed seed — resolves to exactly one run id for the lifetime of a
database. Relaunching used to return that first run, by then finished at the scenario
horizon. ``restartExisting`` deletes it instead and recreates it under the same id, relying
on the ``ON DELETE CASCADE`` every run-scoped foreign key already declares.

Each test seeds a marker incident on the run before relaunching: the simulation never
recreates it, so its presence afterwards is an unambiguous, ticker-proof signal of whether
the run's history was destroyed. The decision logic itself (who may reset, what in-process
state a reset drops) is pinned offline in ``tests/unit/simulation/test_run_restart.py``.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from aegis_api.main import create_app
from aegis_contracts import IncidentState, IncidentV1, PlatformRoleV1, load_settings
from aegis_contracts.versioning import INCIDENT_SCHEMA_VERSION
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.integration.auth_helpers import auth_headers, login_as

# The tutorial's package: a pinned seed against it reproduces the real launch path.
TUTORIAL_PACKAGE = "scenarios/synthetic-training"

OWNER = "user:operator-alpha"
ADMIN = "user:admin-alpha"
# A second operator: `runs:write` (so the create route's RBAC gate passes) but not the
# owner, which is the only actor that can exercise the reset's ownership check.
OTHER_OPERATOR = "user:operator-bravo"


@pytest.fixture
def api_client(migrated_database: None, db_session) -> TestClient:  # noqa: ARG001
    _ = db_session
    app = create_app(load_settings())
    with TestClient(app) as client:
        yield client


@pytest.fixture
def still_api_client(migrated_database: None, db_session) -> Iterator[TestClient]:  # noqa: ARG001
    """An API with the tick engine disabled, so row counts do not move under the test.

    The cascade assertions below compare exact per-table counts before and after a reset;
    a live ticker would append events mid-assertion and make them race. Every other test in
    this file runs against the default (ticking) app, which is what proves the reset holds
    up against the concurrent single writer.
    """
    _ = db_session
    previous = os.environ.get("AEGIS_SIM_TICK_ENABLED")
    os.environ["AEGIS_SIM_TICK_ENABLED"] = "false"
    try:
        app = create_app(load_settings())
        with TestClient(app) as client:
            yield client
    finally:
        if previous is None:
            os.environ.pop("AEGIS_SIM_TICK_ENABLED", None)
        else:
            os.environ["AEGIS_SIM_TICK_ENABLED"] = previous


# The run-scoped tables the reset must empty, and how each is counted for a single run.
# `outbox` has no run_id of its own — it cascades one level further out, through
# domain_events — which is exactly the transitive case worth pinning.
_RUN_SCOPED_COUNTS: dict[str, str] = {
    "domain_events": "SELECT count(*) FROM domain_events WHERE run_id = :rid",
    "outbox": (
        "SELECT count(*) FROM outbox o "
        "JOIN domain_events e ON o.event_id = e.event_id WHERE e.run_id = :rid"
    ),
    "simulation_checkpoints": (
        "SELECT count(*) FROM simulation_checkpoints WHERE run_id = :rid"
    ),
    "graph_snapshots": "SELECT count(*) FROM graph_snapshots WHERE run_id = :rid",
    "incidents": "SELECT count(*) FROM incidents WHERE run_id = :rid",
    "agent_sessions": "SELECT count(*) FROM agent_sessions WHERE run_id = :rid",
}


def _run_scoped_counts(run_id: str) -> dict[str, int]:
    """Count the rows every run-scoped table holds for ``run_id``, straight from SQL."""
    counts: dict[str, int] = {}

    async def _count() -> None:
        settings = load_settings()
        engine = create_engine(settings)
        try:
            async with engine.connect() as conn:
                for table, sql in _RUN_SCOPED_COUNTS.items():
                    result = await conn.execute(text(sql), {"rid": run_id})
                    counts[table] = int(result.scalar_one())
        finally:
            await dispose_engine(engine)

    asyncio.run(_count())
    return counts


def _seed_marker_agent_session(run_id: str, session_id: str) -> None:
    """Insert a bare agent_sessions row — a table with no simulation path that recreates it."""

    async def _seed() -> None:
        settings = load_settings()
        engine = create_engine(settings)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO agent_sessions "
                        "(id, run_id, incident_id, trace_id, payload, created_at, updated_at) "
                        "VALUES (:sid, :rid, NULL, :tid, '{}'::jsonb, now(), now())"
                    ),
                    {"sid": session_id, "rid": run_id, "tid": "trace_restart_probe"},
                )
        finally:
            await dispose_engine(engine)

    asyncio.run(_seed())


def _run_async(coroutine) -> None:
    """Run a coroutine against a dedicated engine, off the TestClient's event loop."""

    async def _wrapped() -> None:
        settings = load_settings()
        engine = create_engine(settings)
        try:
            session_maker = get_session_maker(settings, engine=engine)
            async with PostgresUnitOfWork(session_maker) as uow:
                await coroutine(uow)
        finally:
            await dispose_engine(engine)

    asyncio.run(_wrapped())


def _seed_other_operator() -> None:
    async def _seed(uow: PostgresUnitOfWork) -> None:
        await uow.auth.upsert_user(
            user_id=OTHER_OPERATOR,
            display_name="Operator Bravo",
            roles=[PlatformRoleV1.OPERATOR],
            now=datetime.now(tz=UTC),
        )

    _run_async(_seed)


def _seed_marker_incident(run_id: str, incident_id: str) -> None:
    async def _seed(uow: PostgresUnitOfWork) -> None:
        now = datetime.now(tz=UTC)
        await uow.incidents.add(
            IncidentV1(
                schema_version=INCIDENT_SCHEMA_VERSION,
                id=incident_id,
                run_id=run_id,
                title="restart probe incident",
                state=IncidentState.OPEN,
                alert_ids=[],
                revision=0,
                created_at=now,
                updated_at=now,
            )
        )

    _run_async(_seed)


def _marker_incident_exists(incident_id: str) -> bool:
    found: list[bool] = []

    async def _check(uow: PostgresUnitOfWork) -> None:
        found.append(await uow.incidents.get_by_id(incident_id) is not None)

    _run_async(_check)
    return found[0]


def _launch(
    client: TestClient,
    *,
    seed: int,
    key: str,
    user_id: str = OWNER,
    restart_existing: bool | None = None,
) -> dict:
    csrf = login_as(client, user_id=user_id)
    body: dict[str, object] = {
        "schemaVersion": 1,
        "scenarioPackagePath": TUTORIAL_PACKAGE,
        "seed": seed,
    }
    if restart_existing is not None:
        body["restartExisting"] = restart_existing
    response = client.post(
        "/api/v1/runs",
        json=body,
        headers={"Idempotency-Key": key, **auth_headers(csrf)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_relaunch_without_the_flag_returns_the_existing_run(api_client: TestClient) -> None:
    """The default is unchanged: a pinned-seed relaunch resumes, and destroys nothing."""
    first = _launch(api_client, seed=7101, key="restart-7101-a")
    run_id = first["run"]["id"]
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7101")

    second = _launch(api_client, seed=7101, key="restart-7101-b")

    assert second["run"]["id"] == run_id
    assert second["eventsEmitted"] == 0
    assert _marker_incident_exists("incident:inc_restart_probe_7101")


def test_restart_deletes_the_run_and_recreates_it(api_client: TestClient) -> None:
    """The owner's restart cascades the run's whole history away and rebuilds the run."""
    first = _launch(api_client, seed=7102, key="restart-7102-a")
    run_id = first["run"]["id"]
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7102")

    second = _launch(api_client, seed=7102, key="restart-7102-b", restart_existing=True)

    # Same derived id — the point of the reset is that the id is reused, not replaced.
    assert second["run"]["id"] == run_id
    # A genuine creation: START ran again, rather than an existing run being handed back.
    assert second["eventsEmitted"] >= 1
    assert second["idempotency"]["replayed"] is False
    # Everything hanging off the run went with it via ON DELETE CASCADE.
    assert not _marker_incident_exists("incident:inc_restart_probe_7102")

    # The recreated run is coherent and readable: it has a fresh graph snapshot to boot from.
    login_as(api_client, user_id=OWNER)
    bootstrap = api_client.get(f"/api/v1/runs/{run_id}/bootstrap")
    assert bootstrap.status_code == 200, bootstrap.text
    assert bootstrap.json()["run"]["id"] == run_id


def test_restart_cascades_every_run_scoped_table(still_api_client: TestClient) -> None:
    """The reset's whole mechanism: deleting the runs row empties every run-scoped table.

    Offline tests cannot prove this — it is the database's ``ON DELETE CASCADE``, not any
    application code, that removes the events, outbox rows, checkpoints, graph snapshots,
    incidents and agent sessions. So count them for real, on both sides of the reset.
    """
    first = _launch(still_api_client, seed=7106, key="restart-7106-a")
    run_id = first["run"]["id"]

    # Build up history: each STEP appends events (and their outbox rows), a graph snapshot
    # and a checkpoint. Then hang non-simulation rows off the run too.
    csrf = login_as(still_api_client, user_id=OWNER)
    for index in range(5):
        stepped = still_api_client.post(
            f"/api/v1/runs/{run_id}/step",
            headers={"Idempotency-Key": f"restart-7106-step-{index}", **auth_headers(csrf)},
        )
        assert stepped.status_code == 200, stepped.text
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7106")
    _seed_marker_agent_session(run_id, "agentsession_restart_probe_7106")

    before = _run_scoped_counts(run_id)
    # Every table must actually hold something, or the "gone afterwards" assertion is vacuous.
    assert all(count > 0 for count in before.values()), before

    _launch(still_api_client, seed=7106, key="restart-7106-b", restart_existing=True)

    after = _run_scoped_counts(run_id)

    # Rows with no simulation path that recreates them are gone outright. These prove the
    # cascade fired rather than the counts merely coinciding.
    assert after["incidents"] == 0, after
    assert after["agent_sessions"] == 0, after
    # The simulation's own tables were emptied and then rebuilt by the fresh run's START,
    # so they hold strictly less than the five-step history they replaced — and exactly what
    # a brand-new run has.
    assert after["domain_events"] < before["domain_events"], (before, after)
    assert after["outbox"] < before["outbox"], (before, after)
    assert after["graph_snapshots"] < before["graph_snapshots"], (before, after)
    assert after["simulation_checkpoints"] <= before["simulation_checkpoints"], (before, after)
    # The outbox cascades transitively (runs -> domain_events -> outbox), so it must track
    # the event table exactly; a stale outbox row would republish a deleted run's events.
    assert after["outbox"] == after["domain_events"], after


def test_restart_by_a_non_owner_leaves_the_run_intact(api_client: TestClient) -> None:
    """Another operator's restart degrades to a resume; it must not destroy the run."""
    _seed_other_operator()
    first = _launch(api_client, seed=7103, key="restart-7103-a")
    run_id = first["run"]["id"]
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7103")

    second = _launch(
        api_client,
        seed=7103,
        key="restart-7103-b",
        user_id=OTHER_OPERATOR,
        restart_existing=True,
    )

    assert second["run"]["id"] == run_id
    assert second["eventsEmitted"] == 0
    assert _marker_incident_exists("incident:inc_restart_probe_7103")


def test_restart_by_an_admin_resets_another_operators_run(api_client: TestClient) -> None:
    """Admins bypass the owner check, matching every other run-scoped gate (ADR 0034)."""
    first = _launch(api_client, seed=7104, key="restart-7104-a")
    run_id = first["run"]["id"]
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7104")

    second = _launch(
        api_client,
        seed=7104,
        key="restart-7104-b",
        user_id=ADMIN,
        restart_existing=True,
    )

    assert second["run"]["id"] == run_id
    assert not _marker_incident_exists("incident:inc_restart_probe_7104")


def test_repeated_launch_with_the_same_idempotency_key_resets_once(
    api_client: TestClient,
) -> None:
    """A double-clicked launch replays the first response instead of resetting twice."""
    _launch(api_client, seed=7105, key="restart-7105-a")
    first_restart = _launch(api_client, seed=7105, key="restart-7105-b", restart_existing=True)
    run_id = first_restart["run"]["id"]
    _seed_marker_incident(run_id, "incident:inc_restart_probe_7105")

    replayed = _launch(api_client, seed=7105, key="restart-7105-b", restart_existing=True)

    assert replayed["run"]["id"] == run_id
    assert replayed["idempotency"]["replayed"] is True
    assert replayed["eventsEmitted"] == 0
    # The second POST short-circuited on the Idempotency-Key, so the run was never reset
    # again and the marker seeded after the first reset survives.
    assert _marker_incident_exists("incident:inc_restart_probe_7105")
