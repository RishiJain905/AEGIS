#!/usr/bin/env python3
"""Render Phase 14 feature pipeline evidence HTML from real engine output."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.entities import RunV1
from aegis_contracts.events import EventTypeRegistry
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION, RUN_SCHEMA_VERSION
from aegis_ml.features import (
    FEATURE_SCHEMA_MANIFEST_V1,
    build_compute_response,
    compute_features_from_events,
    run_offline_online_parity,
)
from aegis_ml.features.dataset_builder import build_dataset_from_events
from aegis_simulation_domain import SimulationEngine

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/opt/cursor/artifacts/feature-pipeline-evidence.html")
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def silent_relay_events() -> list[DomainEventEnvelopeV1]:
    scenario = ROOT / "scenarios" / "operation-silent-relay"
    manifest = SimulationEngine.load_manifest(scenario)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1000,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(120)
    return list(runtime.events)


def rejection_demo_events(
    telemetry: list[DomainEventEnvelopeV1],
) -> list[DomainEventEnvelopeV1]:
    if not telemetry:
        return []
    auth_event = next(
        event for event in telemetry if event.type == "telemetry.authentication.failed"
    )
    duplicate_auth = auth_event.model_copy(
        update={"sequence": auth_event.sequence + 100, "event_id": auth_event.event_id}
    )
    base_time = auth_event.sim_time
    hidden_event = DomainEventEnvelopeV1(
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FB3",
        run_id=RUN_ID,
        sequence=auth_event.sequence + 101,
        type="sim.hidden_condition.triggered",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=base_time,
        recorded_at=auth_event.recorded_at,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        payload={
            "schemaVersion": EventTypeRegistry.payload_schema_version(
                "sim.hidden_condition.triggered"
            ),
            "conditionId": "hidden-cause-compromised-credentials",
        },
        trace_id=auth_event.trace_id,
    )
    unsupported = auth_event.model_copy(
        update={
            "sequence": auth_event.sequence + 102,
            "event_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB4",
            "type": "sim.run.started",
            "payload": {
                "schemaVersion": EventTypeRegistry.payload_schema_version("sim.run.started"),
            },
        }
    )
    return [auth_event, duplicate_auth, hidden_event, unsupported]


def main() -> None:
    events = silent_relay_events()
    telemetry = [event for event in events if event.type.startswith("telemetry.")]
    result = compute_features_from_events(run_id=RUN_ID, events=telemetry)
    response = build_compute_response(result)
    parity = run_offline_online_parity(run_id=RUN_ID, events=telemetry)
    repeat = compute_features_from_events(run_id=RUN_ID, events=telemetry)
    repeat_response = build_compute_response(repeat)
    determinism = {
        "firstChecksum": response.output_checksum,
        "secondChecksum": repeat_response.output_checksum,
        "deterministic": response.output_checksum == repeat_response.output_checksum,
    }
    rejection_demo = compute_features_from_events(
        run_id=RUN_ID,
        events=rejection_demo_events(events),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=RUN_ID,
        scenario_version_id="scenario-version:1.0.0",
        seed=1000,
        status="completed",
        started_at=telemetry[0].sim_time,
        sim_time=telemetry[-1].sim_time,
        revision=1,
    )
    manifest = build_dataset_from_events(
        run=run,
        events=telemetry[:50],
        output_dir=Path("/tmp/aegis-phase14-dataset"),
    )
    sample_vector = (
        result.vectors[0].model_dump(mode="json", by_alias=True) if result.vectors else {}
    )
    sample_events = [
        event.model_dump(mode="json", by_alias=True) for event in telemetry[:8]
    ]
    rejection_payload = [
        item.model_dump(mode="json", by_alias=True) for item in rejection_demo.rejections
    ]
    sections = {
        "events": {
            "source": "Operation Silent Relay simulator output (telemetry subset)",
            "telemetryCount": len(telemetry),
            "sampleEvents": sample_events,
        },
        "feature-row": {
            "schemaVersion": FEATURE_SCHEMA_MANIFEST_V1.feature_schema_version,
            "sampleVector": sample_vector,
            "vectorCount": len(result.vectors),
        },
        "parity": parity.model_dump(mode="json", by_alias=True),
        "determinism": determinism,
        "rejections": rejection_payload,
        "dataset": manifest.model_dump(mode="json", by_alias=True),
    }
    intro = (
        "<p>Computed by shared <code>aegis_ml.features</code> engine; "
        "not detection/model code.</p>"
    )
    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Phase 14 Feature Evidence</title>",
        "<style>body{font-family:system-ui;background:#0b1220;color:#e8eefc;padding:2rem}",
        "section{margin:1.5rem 0;padding:1rem;border:1px solid #2a3a5c;border-radius:8px}",
        "pre{background:#111a2e;padding:1rem;overflow:auto;max-height:32rem}</style>",
        "</head><body>",
        "<h1>Phase 14 Feature Pipeline Evidence</h1>",
        intro,
    ]
    for section_id, payload in sections.items():
        html_parts.append(f"<section id='{section_id}'><h2>{section_id}</h2>")
        html_parts.append(
            f"<pre>{json.dumps(payload, indent=2).replace('<', '&lt;')}</pre></section>"
        )
    html_parts.append("</body></html>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(html_parts), encoding="utf-8")
    print(str(OUT))


if __name__ == "__main__":
    main()
