"""Incremental vs full recompute parity."""

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
from aegis_graph_risk import (
    DEFAULT_RISK_ENGINE_CONFIG_V1,
    compute_risk_scores,
    recompute_incremental,
)

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAZ"


def test_incremental_matches_full() -> None:
    snapshot = GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=datetime.now(tz=UTC),
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:x",
                entity_type="asset",
                asset_type="service",
                label="X",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.5,
                status="normal",
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:y",
                entity_type="asset",
                asset_type="service",
                label="Y",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.8,
                status="normal",
                revision=1,
            ),
        ],
        edges=[
            GraphEdgeV1(
                schema_version=GRAPH_EDGE_SCHEMA_VERSION,
                id="edge:xy",
                source="asset:x",
                target="asset:y",
                relationship_type="DEPENDS_ON",
                directed=True,
                confidence=1.0,
                risk_contribution=0.4,
                first_seen_at=datetime.now(tz=UTC),
                last_seen_at=datetime.now(tz=UTC),
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )
    signals = [
        RiskInputV1(
            schema_version=RISK_INPUT_SCHEMA_VERSION,
            signal_id="sig-1",
            run_id=RUN_ID,
            source_type=RiskSignalSourceType.RULE,
            asset_id="asset:x",
            strength=0.7,
            confidence=1.0,
            sim_time=datetime.now(tz=UTC),
            deduplication_key="k1",
            status=RiskSignalStatus.ACTIVE,
            provenance_ref="a1",
        )
    ]
    now = datetime.now(tz=UTC)
    full = compute_risk_scores(
        snapshot,
        signals,
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    incremental = recompute_incremental(
        snapshot,
        [],
        signals,
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    assert full.checksum == incremental.checksum
