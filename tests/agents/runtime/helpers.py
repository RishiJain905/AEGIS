"""Shared helpers for agent runtime tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import IncidentState, IncidentV1, RunV1, ScenarioV1, ScenarioVersionV1
from aegis_contracts.entities import EvidenceV1
from aegis_contracts.versioning import (
    EVIDENCE_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import EvidenceRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork

_SCENARIO_ID = "scenario:agent-runtime-test"
_SCENARIO_VERSION_ID = "scenario-version:agent-runtime-test-v1"


async def _seed_scenario_version(uow: PostgresUnitOfWork) -> str:
    if await uow.scenario_versions.get_by_id(_SCENARIO_VERSION_ID) is None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        scenario = ScenarioV1(
            schema_version=SCENARIO_SCHEMA_VERSION,
            id=_SCENARIO_ID,
            name="Agent Runtime Test",
            created_at=now,
        )
        version = ScenarioVersionV1(
            schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
            id=_SCENARIO_VERSION_ID,
            scenario_id=scenario.id,
            version="1.0.0",
            required_platform_version="0.0.0-phase19",
            published_at=now,
        )
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
    return _SCENARIO_VERSION_ID


async def seed_incident_with_evidence(uow: PostgresUnitOfWork) -> tuple[str, str, str]:
    scenario_version_id = await _seed_scenario_version(uow)
    now = datetime.now(UTC)
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=new_runtime_id("run"),
        scenario_version_id=scenario_version_id,
        seed=42,
        status="running",
        started_at=now,
        sim_time=now,
        revision=1,
    )
    await uow.runs.add(run)
    incident = IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id="incident:inc_runtime_test_001",
        run_id=run.id,
        title="Runtime test incident",
        state=IncidentState.OPEN,
        alert_ids=[],
        revision=0,
        created_at=now,
        updated_at=now,
    )
    await uow.incidents.add(incident)
    evidence = EvidenceV1(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        id="evidence:evd_runtime_test_001",
        run_id=run.id,
        source_event_id=new_runtime_id("evt"),
        summary="Suspicious authentication pattern",
        asset_id="asset:device-workstation-01",
        created_at=now,
    )
    row = EvidenceRow(
        id=evidence.id,
        run_id=evidence.run_id,
        payload=domain_to_payload(evidence),
        created_at=evidence.created_at,
    )
    uow.session.add(row)
    await uow.session.flush()
    return incident.id, run.id, evidence.id
