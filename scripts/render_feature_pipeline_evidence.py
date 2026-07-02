#!/usr/bin/env python3
"""Render Phase 14 feature pipeline evidence HTML from real engine output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path("/opt/cursor/artifacts/feature-pipeline-evidence.html")

from aegis_contracts import DomainEventEnvelopeV1
from aegis_ml.features import (
    FEATURE_SCHEMA_MANIFEST_V1,
    build_compute_response,
    compute_features_from_events,
    run_offline_online_parity,
)
from aegis_ml.features.dataset_builder import build_dataset_from_events
from aegis_contracts.entities import RunV1
from aegis_contracts.versioning import RUN_SCHEMA_VERSION
from aegis_simulation_domain import SimulationEngine
from tests.ml.features.helpers import (
    RUN_ID,
    make_telemetry_event,
    sample_auth_failed,
    sample_auth_succeeded,
    sample_hidden_condition,
    unique_event_id,
)

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


def main() -> None:
    events = silent_relay_events()
    telemetry = [event for event in events if event.type.startswith("telemetry.")]
    result = compute_features_from_events(run_id=RUN_ID, events=telemetry)
    response = build_compute_response(result)
    parity = run_offline_online_parity(run_id=RUN_ID, events=telemetry)
    repeat = compute_features_from_events(run_id=RUN_ID, events=telemetry)
    determinism = {
        "firstChecksum": response.output_checksum,
        "secondChecksum": build_compute_response(repeat).output_checksum,
        "deterministic": response.output_checksum
        == build_compute_response(repeat).output_checksum,
    }
    rejection_demo = compute_features_from_events(
        run_id=RUN_ID,
        events=[
            sample_auth_failed(),
            sample_auth_failed(sequence=2, sim_offset_seconds=11),
            sample_hidden_condition(sequence=3),
            make_telemetry_event(
                sequence=4,
                event_type="sim.run.started",
                payload={},
                sim_offset_seconds=12,
                event_id_override=unique_event_id(4),
            ),
        ],
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id=RUN_ID,
        scenario_version_id="scenario-version:1.0.0",
        seed=1000,
        status="completed",
        started_at=telemetry[0].sim_time if telemetry else sample_auth_failed().sim_time,
        sim_time=telemetry[-1].sim_time if telemetry else sample_auth_failed().sim_time,
        revision=1,
    )
    manifest = build_dataset_from_events(
        run=run,
        events=telemetry[:50],
        output_dir=Path("/tmp/aegis-phase14-dataset"),
    )
    sample_vector = result.vectors[0].model_dump(mode="json", by_alias=True) if result.vectors else {}
    sections = {
        "events": {
            "source": "Operation Silent Relay simulator output (telemetry subset)",
            "telemetryCount": len(telemetry),
            "sampleEvents": [event.model_dump(mode="json", by_alias=True) for event in telemetry[:8]],
        },
        "feature-row": {
            "schemaVersion": FEATURE_SCHEMA_MANIFEST_V1.feature_schema_version,
            "sampleVector": sample_vector,
            "vectorCount": len(result.vectors),
        },
        "parity": parity.model_dump(mode="json", by_alias=True),
        "determinism": determinism,
        "rejections": [item.model_dump(mode="json", by_alias=True) for item in rejection_demo.rejections],
        "dataset": manifest.model_dump(mode="json", by_alias=True),
    }
    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Phase 14 Feature Evidence</title>",
        "<style>body{font-family:system-ui;background:#0b1220;color:#e8eefc;padding:2rem}",
        "section{margin:1.5rem 0;padding:1rem;border:1px solid #2a3a5c;border-radius:8px}",
        "pre{background:#111a2e;padding:1rem;overflow:auto;max-height:32rem}</style></head><body>",
        "<h1>Phase 14 Feature Pipeline Evidence</h1>",
        "<p>Computed by shared <code>aegis_ml.features</code> engine — not detection/model code.</p>",
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
