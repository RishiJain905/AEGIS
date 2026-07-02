"""Target criticality amplifies propagated risk within cap."""

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


def _snapshot(target_criticality: float) -> GraphSnapshotV1:
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
                criticality=0.2,
                status="normal",
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:b",
                entity_type="asset",
                asset_type="database",
                label="B",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=target_criticality,
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
        signal_id="sig-crit",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:a",
        strength=0.8,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="crit",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:crit",
    )


def test_higher_criticality_increases_propagated_risk() -> None:
    now = datetime.now(tz=UTC)
    low = compute_risk_scores(
        _snapshot(0.2),
        [_signal()],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    high = compute_risk_scores(
        _snapshot(0.95),
        [_signal()],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    low_b = next(score for score in low.scores if score.asset_id == "asset:b")
    high_b = next(score for score in high.scores if score.asset_id == "asset:b")
    assert high_b.propagated > low_b.propagated
    assert high_b.total <= 1.0
