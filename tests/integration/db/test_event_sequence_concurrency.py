"""Regression tests for AEGIS-BUG-001 — atomic per-run event sequence assignment.

Two transactions that each append an event for the same run must receive
distinct, consecutive sequence numbers. Without the per-run advisory lock in
``next_sequence`` both readers see the same max and collide on the unique
``(run_id, sequence)`` constraint, rolling back one otherwise-valid command.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aegis_contracts import RunV1, ScenarioV1, ScenarioVersionV1
from aegis_contracts.versioning import (
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.seed import build_seed_event
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _seed_run(session_maker: async_sessionmaker[AsyncSession]) -> RunV1:
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:seq-concurrency",
        name="Sequence Concurrency",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:seq-concurrency-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FBZ",
        scenario_version_id=version.id,
        seed=7,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )
    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
        await uow.runs.add(run)
    return run


async def _append_one(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    event_id: str,
) -> int:
    async with PostgresUnitOfWork(session_maker) as uow:
        sequence = await uow.events.next_sequence(run_id)
        # Widen the read->commit window so a non-atomic implementation would let
        # the sibling transaction read the same max before this one commits.
        await asyncio.sleep(0.05)
        event = build_seed_event().model_copy(
            update={"run_id": run_id, "event_id": event_id, "sequence": sequence}
        )
        await uow.append_event(event)
        return sequence


@pytest.mark.asyncio
async def test_concurrent_same_run_append_no_collision(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    run = await _seed_run(session_maker)

    sequences = await asyncio.gather(
        _append_one(session_maker, run_id=run.id, event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FB1"),
        _append_one(session_maker, run_id=run.id, event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FB2"),
    )

    # Both transactions committed with distinct, consecutive sequences.
    assert sorted(sequences) == [0, 1]

    async with PostgresUnitOfWork(session_maker) as uow:
        events = await uow.events.list_by_run(run.id)
    persisted = sorted(event.sequence for event in events)
    assert persisted == [0, 1]
