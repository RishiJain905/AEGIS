"""Explanation path coverage."""

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

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FB0"


def test_propagated_score_has_explanation_path() -> None:
    snapshot = GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=datetime.now(tz=UTC),
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:origin",
                entity_type="asset",
                asset_type="service",
                label="Origin",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.5,
                status="normal",
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:target",
                entity_type="asset",
                asset_type="database",
                label="Target",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.95,
                status="normal",
                revision=1,
            ),
        ],
        edges=[
            GraphEdgeV1(
                schema_version=GRAPH_EDGE_SCHEMA_VERSION,
                id="edge:ot",
                source="asset:origin",
                target="asset:target",
                relationship_type="DEPENDS_ON",
                directed=True,
                confidence=1.0,
                risk_contribution=0.8,
                first_seen_at=datetime.now(tz=UTC),
                last_seen_at=datetime.now(tz=UTC),
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )
    signal = RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-origin",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:origin",
        strength=0.9,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="explain",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:origin",
    )
    result = compute_risk_scores(
        snapshot,
        [signal],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=datetime.now(tz=UTC),
        computed_at_sequence=2,
    )
    target = next(score for score in result.scores if score.asset_id == "asset:target")
    assert target.propagated > 0.0
    assert target.top_contributions
    assert target.top_contributions[0].explanation_path.node_ids[0] == "asset:origin"
