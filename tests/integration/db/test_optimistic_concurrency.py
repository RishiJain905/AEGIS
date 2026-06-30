"""Integration tests for optimistic concurrency."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import IncidentState, IncidentV1, RunV1, ScenarioV1, ScenarioVersionV1
from aegis_contracts.errors import ContractErrorCode
from aegis_contracts.versioning import (
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.errors import StaleRevisionError
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_stale_run_revision_rejected(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:stale-test",
        name="Stale Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:stale-test-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FBB",
        scenario_version_id=version.id,
        seed=9,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
        await uow.runs.add(run)

    with pytest.raises(StaleRevisionError) as exc_info:
        async with PostgresUnitOfWork(session_maker) as uow:
            updated = run.model_copy(update={"revision": 2, "status": "paused"})
            await uow.runs.update_with_revision(updated, expected_revision=99)

    assert exc_info.value.code == ContractErrorCode.STALE_REVISION


@pytest.mark.asyncio
async def test_stale_incident_revision_rejected(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:stale-incident",
        name="Stale Incident",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:stale-incident-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FBC",
        scenario_version_id=version.id,
        seed=11,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )
    now = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    incident = IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id="incident:inc_stale_test_001",
        run_id=run.id,
        title="Stale incident",
        state=IncidentState.OPEN,
        alert_ids=[],
        created_at=now,
        updated_at=now,
        revision=0,
    )

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
        await uow.runs.add(run)
        await uow.incidents.add(incident)

    with pytest.raises(StaleRevisionError) as exc_info:
        async with PostgresUnitOfWork(session_maker) as uow:
            updated = incident.model_copy(
                update={
                    "revision": 3,
                    "state": IncidentState.INVESTIGATING,
                    "updated_at": datetime(2026, 1, 1, 12, 10, tzinfo=UTC),
                }
            )
            await uow.incidents.update_with_revision(updated, expected_revision=99)

    assert exc_info.value.code == ContractErrorCode.STALE_REVISION
