"""Helpers for streaming integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import (
    ActorRef,
    ActorType,
    DomainEventEnvelopeV1,
    EventTypeRegistry,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
)
from aegis_contracts.versioning import (
    DOMAIN_EVENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork

_VALID_EVENT_IDS = (
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB0",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB1",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB2",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB3",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB4",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB5",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB6",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB7",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB8",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB9",
)


def sample_event_id(index: int) -> str:
    return _VALID_EVENT_IDS[index % len(_VALID_EVENT_IDS)]


def make_test_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    event_type: str = "sim.run.started",
) -> DomainEventEnvelopeV1:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        payload={"schemaVersion": EventTypeRegistry.payload_schema_version(event_type)},
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
    )


async def seed_run(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    seed: int = 42,
) -> RunV1:
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:streaming-test",
        name="Streaming Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:streaming-test-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase11",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=run_id,
        scenario_version_id=version.id,
        seed=seed,
        status="running",
        started_at=now,
        sim_time=now,
        revision=0,
    )
    if await uow.scenarios.get_by_id(scenario.id) is None:
        await uow.scenarios.add(scenario)
    if await uow.scenario_versions.get_by_id(version.id) is None:
        await uow.scenario_versions.add(version)
    await uow.runs.add(run)
    return run
