"""Integration tests for domain event uniqueness constraints."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import RunV1, ScenarioV1, ScenarioVersionV1
from aegis_contracts.versioning import (
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.errors import DuplicateEventError
from aegis_persistence.seed import build_seed_event
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _seed_run(uow: PostgresUnitOfWork) -> RunV1:
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:unique-test",
        name="Unique Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:unique-test-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FAZ",
        scenario_version_id=version.id,
        seed=3,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )
    await uow.scenarios.add(scenario)
    await uow.scenario_versions.add(version)
    await uow.runs.add(run)
    return run


@pytest.mark.asyncio
async def test_duplicate_run_sequence_rejected(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run = await _seed_run(uow)
        event_a = build_seed_event().model_copy(
            update={
                "run_id": run.id,
                "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
                "sequence": 10,
            }
        )
        await uow.append_event(event_a)

    with pytest.raises(DuplicateEventError):
        async with PostgresUnitOfWork(session_maker) as uow:
            event_b = build_seed_event().model_copy(
                update={
                    "run_id": run.id,
                    "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAX",
                    "sequence": 10,
                }
            )
            await uow.append_event(event_b)


@pytest.mark.asyncio
async def test_duplicate_event_id_rejected(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run = await _seed_run(uow)
        event_a = build_seed_event().model_copy(
            update={
                "run_id": run.id,
                "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
                "sequence": 1,
            }
        )
        await uow.append_event(event_a)

    with pytest.raises(DuplicateEventError):
        async with PostgresUnitOfWork(session_maker) as uow:
            event_b = build_seed_event().model_copy(
                update={
                    "run_id": run.id,
                    "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
                    "sequence": 2,
                }
            )
            await uow.append_event(event_b)
