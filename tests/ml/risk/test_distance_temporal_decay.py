"""Distance and temporal decay behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def _chain_snapshot() -> GraphSnapshotV1:
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
            id=f"edge:{i}",
            source=f"asset:n{i}",
            target=f"asset:n{i + 1}",
            relationship_type="DEPENDS_ON",
            directed=True,
            confidence=1.0,
            risk_contribution=0.8,
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            event_count=1,
            revision=1,
        )
        for i in range(2)
    ]
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1,
        captured_at=datetime.now(tz=UTC),
        nodes=nodes,
        edges=edges,
        clusters=[],
        revision=1,
    )


def _signal(
    *,
    sim_time: datetime,
    status: RiskSignalStatus = RiskSignalStatus.ACTIVE,
) -> RiskInputV1:
    return RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-decay",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:n0",
        strength=1.0,
        confidence=1.0,
        sim_time=sim_time,
        deduplication_key="decay",
        status=status,
        provenance_ref="alert:decay",
    )


def test_farther_hops_reduce_propagated_risk() -> None:
    snapshot = _chain_snapshot()
    now = datetime.now(tz=UTC)
    result = compute_risk_scores(
        snapshot,
        [_signal(sim_time=now)],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    by_asset = {score.asset_id: score for score in result.scores}
    assert by_asset["asset:n1"].propagated > by_asset["asset:n2"].propagated


def test_older_signals_decay_temporally() -> None:
    snapshot = _chain_snapshot()
    now = datetime.now(tz=UTC)
    fresh = compute_risk_scores(
        snapshot,
        [_signal(sim_time=now)],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    aged = compute_risk_scores(
        snapshot,
        [_signal(sim_time=now - timedelta(hours=4))],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    fresh_n1 = next(score for score in fresh.scores if score.asset_id == "asset:n1")
    aged_n1 = next(score for score in aged.scores if score.asset_id == "asset:n1")
    assert aged_n1.propagated < fresh_n1.propagated


def test_resolved_signals_contribute_zero() -> None:
    snapshot = _chain_snapshot()
    now = datetime.now(tz=UTC)
    result = compute_risk_scores(
        snapshot,
        [_signal(sim_time=now, status=RiskSignalStatus.RESOLVED)],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=now,
        computed_at_sequence=2,
    )
    for score in result.scores:
        assert score.propagated == 0.0
