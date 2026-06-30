"""Integration tests for transactional unit-of-work semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import RunV1, ScenarioV1, ScenarioVersionV1
from aegis_contracts.versioning import (
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.orm.tables import DomainEventRow, OutboxRow, RunRow
from aegis_persistence.seed import build_seed_event
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _scenario() -> ScenarioV1:
    return ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:txn-test",
        name="Txn Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _scenario_version() -> ScenarioVersionV1:
    return ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:txn-test-v1",
        scenario_id="scenario:txn-test",
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _run() -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FAY",
        scenario_version_id="scenario-version:txn-test-v1",
        seed=7,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )


@pytest.mark.asyncio
async def test_failed_transaction_leaves_no_partial_state_or_outbox(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    scenario = _scenario()
    version = _scenario_version()
    run = _run()
    event = build_seed_event()
    event = event.model_copy(
        update={"run_id": run.id, "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV"}
    )

    with pytest.raises(RuntimeError, match="forced rollback"):
        async with PostgresUnitOfWork(session_maker) as uow:
            await uow.scenarios.add(scenario)
            await uow.scenario_versions.add(version)
            await uow.runs.add(run)
            await uow.append_event(event)
            raise RuntimeError("forced rollback")

    async with session_maker() as session:
        assert await session.scalar(select(func.count()).select_from(RunRow)) == 0
        assert await session.scalar(select(func.count()).select_from(DomainEventRow)) == 0
        assert await session.scalar(select(func.count()).select_from(OutboxRow)) == 0


@pytest.mark.asyncio
async def test_successful_transaction_commits_state_event_and_outbox(
    unit_of_work: PostgresUnitOfWork,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    scenario = _scenario()
    version = _scenario_version()
    run = _run()
    event = build_seed_event()
    event = event.model_copy(update={"run_id": run.id})

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
        await uow.runs.add(run)
        await uow.append_event(event)

    async with session_maker() as session:
        assert await session.scalar(select(func.count()).select_from(RunRow)) == 1
        assert await session.scalar(select(func.count()).select_from(DomainEventRow)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxRow)) == 1
