"""Cycle amplification bounds."""

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

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAY"


def test_cycle_scores_remain_bounded() -> None:
    nodes = [
        GraphNodeV1(
            schema_version=GRAPH_NODE_SCHEMA_VERSION,
            id=f"asset:n{i}",
            entity_type="asset",
            asset_type="service",
            label=f"N{i}",
            cluster_id="business-unit:bu",
            risk_score=0.1,
            criticality=0.5,
            status="normal",
            revision=1,
        )
        for i in range(3)
    ]
    edges = [
        GraphEdgeV1(
            schema_version=GRAPH_EDGE_SCHEMA_VERSION,
            id="edge:01",
            source="asset:n0",
            target="asset:n1",
            relationship_type="DEPENDS_ON",
            directed=True,
            confidence=1.0,
            risk_contribution=0.9,
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            event_count=1,
            revision=1,
        ),
        GraphEdgeV1(
            schema_version=GRAPH_EDGE_SCHEMA_VERSION,
            id="edge:12",
            source="asset:n1",
            target="asset:n2",
            relationship_type="DEPENDS_ON",
            directed=True,
            confidence=1.0,
            risk_contribution=0.9,
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            event_count=1,
            revision=1,
        ),
        GraphEdgeV1(
            schema_version=GRAPH_EDGE_SCHEMA_VERSION,
            id="edge:20",
            source="asset:n2",
            target="asset:n0",
            relationship_type="DEPENDS_ON",
            directed=True,
            confidence=1.0,
            risk_contribution=0.9,
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            event_count=1,
            revision=1,
        ),
    ]
    snapshot = GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=datetime.now(tz=UTC),
        nodes=nodes,
        edges=edges,
        clusters=[],
        revision=1,
    )
    signal = RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-cycle",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:n0",
        strength=1.0,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="cycle",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:cycle",
    )
    result = compute_risk_scores(
        snapshot,
        [signal],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=datetime.now(tz=UTC),
        computed_at_sequence=2,
    )
    for score in result.scores:
        assert score.total <= 1.0
