"""Integration helpers for WATCHTOWER and TRACE flow tests."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import (
    DETECTION_ENGINE_ACTOR_ID,
    ActorRef,
    ActorType,
    IncidentState,
    IncidentV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    build_incident_created_event,
    deterministic_incident_id,
)
from aegis_contracts.entities import AlertV1, EvidenceV1
from aegis_contracts.versioning import (
    ALERT_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import EvidenceRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork

_SCENARIO_ID = "scenario:watchtower-trace-test"
_SCENARIO_VERSION_ID = "scenario-version:watchtower-trace-test-v1"
#: The asset both seeded alerts fire on, and therefore the one whose case correlation
#: would open. Exported so autonomy tests can assert the enrichment lookup finds it.
SEEDED_ASSET_ID = "asset:device-workstation-01"


async def _seed_scenario_version(uow: PostgresUnitOfWork) -> str:
    if await uow.scenario_versions.get_by_id(_SCENARIO_VERSION_ID) is None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        scenario = ScenarioV1(
            schema_version=SCENARIO_SCHEMA_VERSION,
            id=_SCENARIO_ID,
            name="Watchtower Trace Test",
            created_at=now,
        )
        version = ScenarioVersionV1(
            schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
            id=_SCENARIO_VERSION_ID,
            scenario_id=scenario.id,
            version="1.0.0",
            required_platform_version="0.0.0-phase20",
            published_at=now,
        )
        await uow.scenarios.add(scenario)
        await uow.scenario_versions.add(version)
    return _SCENARIO_VERSION_ID


async def seed_investigation_run(
    uow: PostgresUnitOfWork,
    *,
    seed: int | None = None,
) -> tuple[str, str, list[str], str]:
    scenario_version_id = await _seed_scenario_version(uow)
    now = datetime(2026, 6, 30, 2, 0, 0, tzinfo=UTC)
    # Unique seed avoids deterministic sim event_id collisions across integration runs
    # (domain_events.event_id is globally unique).
    run_seed = seed if seed is not None else secrets.randbelow(1_000_000_000) + 1
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=new_runtime_id("run"),
        scenario_version_id=scenario_version_id,
        seed=run_seed,
        status="running",
        started_at=now,
        sim_time=now,
        revision=1,
    )
    await uow.runs.add(run)

    alert_ids: list[str] = []
    alerts = [
        AlertV1(
            schema_version=ALERT_SCHEMA_VERSION,
            id=f"alert:alt_{new_runtime_id('alt')[4:].lower()}",
            run_id=run.id,
            title="Repeated authentication failures",
            severity="high",
            source_event_id=new_runtime_id("evt"),
            asset_id=SEEDED_ASSET_ID,
            created_at=now,
        ),
        AlertV1(
            schema_version=ALERT_SCHEMA_VERSION,
            id=f"alert:alt_{new_runtime_id('alt')[4:].lower()}",
            run_id=run.id,
            title="Lateral movement attempt",
            severity="high",
            source_event_id=new_runtime_id("evt"),
            asset_id=SEEDED_ASSET_ID,
            created_at=now + timedelta(minutes=5),
        ),
    ]
    for alert in alerts:
        await uow.alerts.add(alert)
        alert_ids.append(alert.id)

    # The case carries the id deterministic correlation derives from (run, asset), and it
    # lands with its ``incident.created`` event — i.e. exactly the state the detection
    # engine produces in a live run (ADR 0037). A hand-minted id here would seed a world no
    # production path can reach, and would silently hide the enrichment lookup that keys
    # autonomy triage to an asset's open case.
    incident = IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=deterministic_incident_id(run.id, SEEDED_ASSET_ID),
        run_id=run.id,
        title="Watchtower trace integration incident",
        state=IncidentState.OPEN,
        alert_ids=alert_ids,
        revision=0,
        created_at=now,
        updated_at=now,
    )
    created = await uow.incidents.add(incident)
    await uow.append_event(
        build_incident_created_event(
            created,
            event_id=new_runtime_id("evt"),
            sequence=await uow.events.next_sequence(run.id),
            actor=ActorRef(type=ActorType.SYSTEM, id=DETECTION_ENGINE_ACTOR_ID),
            trace_id=new_runtime_id("trc"),
        )
    )

    evidence = EvidenceV1(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        id=f"evidence:evd_{new_runtime_id('evd')[4:].lower()}",
        run_id=run.id,
        source_event_id=new_runtime_id("evt"),
        summary="Suspicious authentication pattern",
        asset_id=SEEDED_ASSET_ID,
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
    return incident.id, run.id, alert_ids, evidence.id
