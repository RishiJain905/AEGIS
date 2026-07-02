"""Signal lifecycle updates propagated risk."""

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


def _snapshot() -> GraphSnapshotV1:
    return GraphSnapshotV1(
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
                criticality=0.8,
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
                risk_contribution=0.7,
                first_seen_at=datetime.now(tz=UTC),
                last_seen_at=datetime.now(tz=UTC),
                event_count=1,
                revision=1,
            ),
        ],
        clusters=[],
        revision=1,
    )


def _signal(status: RiskSignalStatus) -> RiskInputV1:
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-life",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:origin",
        strength=0.9,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="life",
        status=status,
        provenance_ref="alert:life",
    )


def test_resolving_signal_clears_propagation() -> None:
    snapshot = _snapshot()
    now = datetime.now(tz=UTC)
    active = compute_risk_scores(
        snapshot,
        [_signal(RiskSignalStatus.ACTIVE)],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    resolved = compute_risk_scores(
        snapshot,
        [_signal(RiskSignalStatus.RESOLVED)],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=3,
    )
    active_target = next(score for score in active.scores if score.asset_id == "asset:target")
    resolved_by_asset = {score.asset_id: score for score in resolved.scores}
    resolved_target = resolved_by_asset.get("asset:target")
    assert active_target.propagated > 0.0
    assert resolved_target is None or resolved_target.propagated == 0.0
