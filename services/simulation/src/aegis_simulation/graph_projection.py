"""Build GraphSnapshotV1 projections from simulation world state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import GraphSnapshotV1
from aegis_contracts.versioning import GRAPH_SNAPSHOT_SCHEMA_VERSION
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_simulation_domain.disclosure import redact_graph_snapshot
from aegis_simulation_domain.runtime import SimulationRuntime

from aegis_simulation.disclosure_resolver import RunDisclosure


def _asset_label(manifest: ScenarioManifestV1, asset_id: str) -> str:
    for asset in manifest.assets:
        if asset.id == asset_id:
            return asset.label
    return asset_id


def build_graph_snapshot_from_runtime(
    runtime: SimulationRuntime,
    *,
    sequence: int | None = None,
    revision: int | None = None,
    captured_at: datetime | None = None,
) -> GraphSnapshotV1:
    manifest = runtime.manifest
    captured = captured_at or datetime.now(tz=UTC)
    captured_at_str = captured.isoformat().replace("+00:00", "Z")
    snapshot_sequence = (
        sequence if sequence is not None else max(runtime.world.next_sequence - 1, 0)
    )
    snapshot_revision = revision if revision is not None else runtime.world.next_sequence

    nodes: list[dict[str, Any]] = [
        {
            "schemaVersion": 1,
            "id": asset.id,
            "entityType": "asset",
            "assetType": asset.asset_type,
            "label": _asset_label(manifest, asset.id),
            "clusterId": asset.zone_id,
            "riskScore": asset.risk_score,
            "criticality": asset.criticality,
            "status": asset.status,
            "revision": asset.revision,
        }
        for asset in sorted(runtime.world.assets.values(), key=lambda item: item.id)
    ]
    edges: list[dict[str, Any]] = [
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
            "lastSeenAt": captured_at_str,
            "eventCount": 1,
            "revision": relationship.revision,
        }
        for relationship in sorted(runtime.world.relationships.values(), key=lambda item: item.id)
    ]

    return GraphSnapshotV1.model_validate(
        {
            "schemaVersion": GRAPH_SNAPSHOT_SCHEMA_VERSION,
            "runId": runtime.run_id,
            "sequence": snapshot_sequence,
            "capturedAt": captured_at_str,
            "nodes": nodes,
            "edges": edges,
            "clusters": [],
            "revision": snapshot_revision,
        }
    )


def redact_snapshot_for_disclosure(
    snapshot: GraphSnapshotV1,
    disclosure: RunDisclosure,
) -> GraphSnapshotV1:
    """Return a fog-redacted copy of a graph snapshot for operator-facing transport.

    The persisted snapshot is always the truth (source of truth, replay-from-snapshot, and
    post-run debrief depend on it); redaction is applied only when *serving* to the operator
    while a run is still active. Undisclosed governed nodes are shown at their baseline
    status with ``disclosed=false`` and their risk soft-pedalled to the manifest baseline so
    an attacker-driven spike never leaks. Everything else passes through unchanged with
    ``disclosed=true``.
    """
    return redact_graph_snapshot(snapshot, disclosure.governing_map, disclosure.inputs)
