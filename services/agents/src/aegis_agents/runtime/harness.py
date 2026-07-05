"""Harness seed data for observability and demo scripts."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import IncidentState, IncidentV1, RunV1
from aegis_contracts.entities import EvidenceV1
from aegis_contracts.versioning import (
    EVIDENCE_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import EvidenceRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork

HARNESS_INCIDENT_ID = "incident:inc_runtime_harness_001"
HARNESS_EVIDENCE_ID = "evidence:evd_runtime_harness_001"


async def seed_harness_incident(uow: PostgresUnitOfWork) -> str:
    existing = await uow.incidents.get_by_id(HARNESS_INCIDENT_ID)
    if existing is not None:
        return HARNESS_INCIDENT_ID

    now = datetime.now(UTC)
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=new_runtime_id("run"),
        scenario_version_id="scenario-version:v1.0.0-synthetic",
        seed=42,
        status="running",
        started_at=now,
        sim_time=now,
        revision=1,
    )
    await uow.runs.add(run)
    incident = IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=HARNESS_INCIDENT_ID,
        run_id=run.id,
        title="Agent runtime harness incident",
        state=IncidentState.OPEN,
        alert_ids=[],
        revision=0,
        created_at=now,
        updated_at=now,
    )
    await uow.incidents.add(incident)
    evidence = EvidenceV1(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        id=HARNESS_EVIDENCE_ID,
        run_id=run.id,
        source_event_id=new_runtime_id("evt"),
        summary="Harness suspicious authentication pattern",
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
    return incident.id
