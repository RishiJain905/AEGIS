"""Deterministic local seed data for development and integration tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from aegis_contracts import (
    ActorRef,
    ActorType,
    DomainEventEnvelopeV1,
    IncidentState,
    IncidentV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    load_settings,
)
from aegis_contracts.versioning import (
    DOMAIN_EVENT_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)

from aegis_persistence.engine import get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork

SYNTHETIC_SCENARIO_ID = "scenario:synthetic-dev"
SYNTHETIC_SCENARIO_VERSION_ID = "scenario-version:synthetic-dev-v1"
SYNTHETIC_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAX"
SYNTHETIC_INCIDENT_ID = "incident:inc_synthetic_seed_001"
SYNTHETIC_EVENT_ID = "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW"
SYNTHETIC_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX"


def build_seed_scenario() -> ScenarioV1:
    return ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id=SYNTHETIC_SCENARIO_ID,
        name="Synthetic Development Scenario",
        description="Deterministic seed scenario for local development",
        created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
    )


def build_seed_scenario_version() -> ScenarioVersionV1:
    return ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id=SYNTHETIC_SCENARIO_VERSION_ID,
        scenario_id=SYNTHETIC_SCENARIO_ID,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
    )


def build_seed_run() -> RunV1:
    return RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=SYNTHETIC_RUN_ID,
        scenario_version_id=SYNTHETIC_SCENARIO_VERSION_ID,
        seed=42,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        revision=0,
    )


def build_seed_incident() -> IncidentV1:
    now = datetime(2026, 1, 1, 12, 5, 0, tzinfo=UTC)
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=SYNTHETIC_INCIDENT_ID,
        run_id=SYNTHETIC_RUN_ID,
        title="Synthetic seed incident",
        state=IncidentState.OPEN,
        alert_ids=[],
        created_at=now,
        updated_at=now,
        revision=0,
    )


def build_seed_event() -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=SYNTHETIC_EVENT_ID,
        run_id=SYNTHETIC_RUN_ID,
        sequence=1,
        type="incident.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=datetime(2026, 1, 1, 12, 5, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC),
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:system-seed"),
        subject=ActorRef(type=ActorType.ASSET, id="asset:device-workstation-01"),
        payload={"schemaVersion": 1, "incidentId": SYNTHETIC_INCIDENT_ID},
        trace_id=SYNTHETIC_TRACE_ID,
        causation_id=None,
        correlation_id=None,
    )


async def seed_database(*, skip_if_exists: bool = True) -> None:
    settings = load_settings()
    session_maker = get_session_maker(settings)
    async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
        if skip_if_exists and await uow.runs.get_by_id(SYNTHETIC_RUN_ID) is not None:
            return
        await uow.scenarios.add(build_seed_scenario())
        await uow.scenario_versions.add(build_seed_scenario_version())
        await uow.runs.add(build_seed_run())
        await uow.incidents.add(build_seed_incident())
        await uow.append_event(build_seed_event())


def main() -> None:
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
