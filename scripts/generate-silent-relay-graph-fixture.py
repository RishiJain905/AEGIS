#!/usr/bin/env python3
"""Generate GraphSnapshotV1 fixtures from Operation Silent Relay manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from aegis_simulation_domain import SimulationEngine

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "operation-silent-relay"
MANIFEST_PATH = SCENARIO / "manifest.yaml"
OUTPUT_DIR = ROOT / "apps" / "web" / "fixtures" / "silent-relay"
STEPS = 300

RUNS = [
    {
        "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB0",
        "seed": 1000,
        "scenarioVersionId": "scenario-version:1.0.0-silent-relay",
    },
    {
        "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB1",
        "seed": 1007,
        "scenarioVersionId": "scenario-version:1.0.0-silent-relay",
    },
]


def build_snapshot(run_id: str, seed: int) -> dict:
    manifest_data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = SimulationEngine.load_manifest(SCENARIO)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id="scenario-version:1.0.0-silent-relay",
    )
    runtime.start()
    runtime.run_steps(STEPS)
    captured_at = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
    nodes = [
        {
            "schemaVersion": 1,
            "id": asset.id,
            "entityType": "asset",
            "assetType": asset.asset_type,
            "label": next(
                (item["label"] for item in manifest_data["assets"] if item["id"] == asset.id),
                asset.id,
            ),
            "clusterId": asset.zone_id,
            "riskScore": asset.risk_score,
            "criticality": asset.criticality,
            "status": asset.status,
            "revision": asset.revision,
        }
        for asset in sorted(runtime.world.assets.values(), key=lambda item: item.id)
    ]
    edges = [
        {
            "schemaVersion": 1,
            "id": relationship.id,
            "source": relationship.source_id,
            "target": relationship.target_id,
            "relationshipType": relationship.relationship_type,
            "directed": True,
            "confidence": relationship.confidence,
            "riskContribution": relationship.risk_contribution,
            "firstSeenAt": "2026-01-01T00:00:00.000Z",
            "lastSeenAt": captured_at,
            "eventCount": 1,
            "revision": relationship.revision,
        }
        for relationship in sorted(runtime.world.relationships.values(), key=lambda item: item.id)
    ]
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "sequence": runtime.world.next_sequence,
        "capturedAt": captured_at,
        "revision": 1,
        "nodes": nodes,
        "edges": edges,
    }


def build_shell_patch() -> dict:
    manifest_data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "scenarios": [
            {
                "schemaVersion": 1,
                "id": "scenario:operation-silent-relay",
                "name": "Operation Silent Relay",
                "description": manifest_data["metadata"]["description"],
                "createdAt": "2026-01-01T00:00:00.000Z",
            }
        ],
        "scenarioVersions": [
            {
                "schemaVersion": 1,
                "id": "scenario-version:1.0.0-silent-relay",
                "scenarioId": "scenario:operation-silent-relay",
                "version": "1.0.0",
                "requiredPlatformVersion": "0.0.0-phase10",
                "publishedAt": "2026-06-30T12:00:00.000Z",
            }
        ],
        "runs": [
            {
                "schemaVersion": 1,
                "id": item["runId"],
                "scenarioVersionId": item["scenarioVersionId"],
                "seed": item["seed"],
                "status": "running",
                "startedAt": "2026-06-30T12:00:00.000Z",
                "simTime": "2026-01-01T00:05:52.000Z",
                "revision": 1,
            }
            for item in RUNS
        ],
        "incidents": [
            {
                "schemaVersion": 1,
                "id": "incident:inc_silent_relay_001",
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                "title": "Silent Relay — authentication anomaly cluster",
                "state": "investigating",
                "alertIds": ["alert:alt_silent_relay_001", "alert:alt_silent_relay_002"],
                "createdAt": "2026-06-30T12:05:00.000Z",
                "updatedAt": "2026-06-30T12:10:00.000Z",
                "revision": 2,
            },
            {
                "schemaVersion": 1,
                "id": "incident:inc_silent_relay_002",
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB1",
                "title": "Silent Relay — data access anomaly cluster",
                "state": "investigating",
                "alertIds": ["alert:alt_silent_relay_003"],
                "createdAt": "2026-06-30T12:05:00.000Z",
                "updatedAt": "2026-06-30T12:10:00.000Z",
                "revision": 2,
            },
        ],
        "alerts": [
            {
                "schemaVersion": 1,
                "id": "alert:alt_silent_relay_001",
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                "title": "Elevated authentication failures on identity broker",
                "severity": "high",
                "sourceEventId": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC0",
                "assetId": "asset:svc-identity-broker",
                "createdAt": "2026-06-30T12:01:00.000Z",
            },
            {
                "schemaVersion": 1,
                "id": "alert:alt_silent_relay_002",
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                "title": "Lateral authentication success on logistics API",
                "severity": "medium",
                "sourceEventId": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC1",
                "assetId": "asset:svc-logistics-api",
                "createdAt": "2026-06-30T12:02:00.000Z",
            },
            {
                "schemaVersion": 1,
                "id": "alert:alt_silent_relay_003",
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FB1",
                "title": "Anomalous PII database query volume",
                "severity": "critical",
                "sourceEventId": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC2",
                "assetId": "asset:database-customer-pii",
                "createdAt": "2026-06-30T12:01:30.000Z",
            },
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = [build_snapshot(item["runId"], item["seed"]) for item in RUNS]
    for snapshot in snapshots:
        path = OUTPUT_DIR / f"graph-snapshot-{snapshot['runId']}.json"
        path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {path}")
    patch = build_shell_patch()
    patch["graphSnapshots"] = snapshots
    patch_path = OUTPUT_DIR / "shell-dataset-patch.json"
    patch_path.write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {patch_path}")


if __name__ == "__main__":
    main()
