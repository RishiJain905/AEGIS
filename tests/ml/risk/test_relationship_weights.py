"""Relationship type weights affect propagation."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1
from aegis_contracts.risk import (
    RiskEngineConfigV1,
    RiskInputV1,
    RiskSignalSourceType,
    RiskSignalStatus,
)
from aegis_contracts.versioning import (
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    RISK_ENGINE_CONFIG_SCHEMA_VERSION,
    RISK_INPUT_SCHEMA_VERSION,
)
from aegis_graph_risk import compute_risk_scores
from aegis_graph_risk.version import GRAPH_RISK_ALGORITHM_VERSION

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAX"


def _snapshot() -> GraphSnapshotV1:
    now = datetime.now(tz=UTC)
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=now,
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
                criticality=0.5,
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
                confidence=0.8,
                risk_contribution=0.6,
                first_seen_at=now,
                last_seen_at=now,
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )


def _signal() -> RiskInputV1:
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-weight",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:a",
        strength=1.0,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="weight",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:weight",
    )


def _config(type_weight: float) -> RiskEngineConfigV1:
    return RiskEngineConfigV1(
        schema_version=RISK_ENGINE_CONFIG_SCHEMA_VERSION,
        algorithm_version=GRAPH_RISK_ALGORITHM_VERSION,
        global_cap=1.0,
        max_hops=2,
        distance_decay_factor=0.65,
        temporal_decay_factor=0.5,
        temporal_half_life_seconds=3600.0,
        criticality_amplifier=0.0,
        min_explanation_contribution=0.01,
        relationship_type_weights={"DEPENDS_ON": type_weight},
        eligible_relationship_types=["DEPENDS_ON"],
        top_explanation_paths=3,
    )


def test_higher_relationship_weight_increases_propagation() -> None:
    snapshot = _snapshot()
    now = datetime.now(tz=UTC)
    low = compute_risk_scores(
        snapshot,
        [_signal()],
        _config(0.2),
        current_sim_time=now,
        computed_at_sequence=2,
    )
    high = compute_risk_scores(
        snapshot,
        [_signal()],
        _config(1.0),
        current_sim_time=now,
        computed_at_sequence=2,
    )
    low_b = next(score for score in low.scores if score.asset_id == "asset:b")
    high_b = next(score for score in high.scores if score.asset_id == "asset:b")
    assert high_b.propagated > low_b.propagated
