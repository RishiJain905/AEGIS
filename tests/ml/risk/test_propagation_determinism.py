"""Deterministic propagation checksum tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1
from aegis_contracts.risk import RiskInputV1, RiskSignalSourceType, RiskSignalStatus
from aegis_contracts.versioning import (
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    RISK_INPUT_SCHEMA_VERSION,
)
from aegis_graph_risk import DEFAULT_RISK_ENGINE_CONFIG_V1, compute_risk_scores

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAX"


def _mini_snapshot() -> GraphSnapshotV1:
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=10,
        captured_at=datetime.now(tz=UTC),
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:a",
                entity_type="asset",
                asset_type="service",
                label="A",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.5,
                status="normal",
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:b",
                entity_type="asset",
                asset_type="service",
                label="B",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.9,
                status="normal",
                revision=1,
            ),
        ],
        edges=[
            GraphEdgeV1(
                schema_version=GRAPH_EDGE_SCHEMA_VERSION,
                id="edge:ab",
                source="asset:a",
                target="asset:b",
                relationship_type="DEPENDS_ON",
                directed=True,
                confidence=1.0,
                risk_contribution=0.5,
                first_seen_at=datetime.now(tz=UTC),
                last_seen_at=datetime.now(tz=UTC),
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )


def _signal(asset_id: str, strength: float = 0.8) -> RiskInputV1:
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id=f"sig-{asset_id}",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id=asset_id,
        strength=strength,
        confidence=0.9,
        sim_time=datetime.now(tz=UTC),
        deduplication_key=f"{RUN_ID}:{asset_id}",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:test",
    )


def test_identical_inputs_produce_identical_checksum() -> None:
    snapshot = _mini_snapshot()
    signals = [_signal("asset:a")]
    now = datetime.now(tz=UTC)
    first = compute_risk_scores(
        snapshot,
        signals,
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=11,
    )
    second = compute_risk_scores(
        snapshot,
        signals,
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=11,
    )
    assert first.checksum == second.checksum
    assert first.scores[0].total == second.scores[0].total
