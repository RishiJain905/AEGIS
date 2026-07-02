"""Medium-graph performance budget for graph-risk-v1."""

from __future__ import annotations

import time
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
NODE_COUNT = 2500
EDGES_PER_NODE = 2
BUDGET_SECONDS = 30.0


def _pad_id(index: int) -> str:
    return str(index).zfill(5)


def _build_medium_snapshot() -> GraphSnapshotV1:
    nodes: list[GraphNodeV1] = []
    edges: list[GraphEdgeV1] = []
    now = datetime.now(tz=UTC)

    for i in range(NODE_COUNT):
        node_id = f"asset:node-{_pad_id(i)}"
        nodes.append(
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id=node_id,
                entity_type="asset",
                asset_type="service" if i % 3 == 0 else "device" if i % 3 == 1 else "database",
                label=f"Node {i}",
                cluster_id=f"business-unit:cluster-{str(i % 20).zfill(2)}",
                risk_score=(i % 100) / 100,
                criticality=((i + 7) % 100) / 100,
                status="suspicious" if i % 17 == 0 else "normal",
                revision=1,
            )
        )

    for i in range(NODE_COUNT):
        for j in range(1, EDGES_PER_NODE + 1):
            target_index = (i + j * 37) % NODE_COUNT
            if target_index == i:
                continue
            edges.append(
                GraphEdgeV1(
                    schema_version=GRAPH_EDGE_SCHEMA_VERSION,
                    id=f"edge:medium-{_pad_id(i)}-{_pad_id(target_index)}-{j}",
                    source=f"asset:node-{_pad_id(i)}",
                    target=f"asset:node-{_pad_id(target_index)}",
                    relationship_type="COMMUNICATED_WITH" if j % 2 == 0 else "DEPENDS_ON",
                    directed=True,
                    confidence=0.9,
                    risk_contribution=0.1,
                    first_seen_at=now,
                    last_seen_at=now,
                    event_count=10 if i % 5 == 0 else 0,
                    revision=1,
                )
            )

    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=RUN_ID,
        sequence=1000,
        captured_at=now,
        nodes=nodes,
        edges=edges,
        clusters=[],
        revision=1,
    )


def test_medium_graph_recompute_within_budget() -> None:
    snapshot = _build_medium_snapshot()
    signal = RiskInputV1(
        schema_version=RISK_INPUT_SCHEMA_VERSION,
        signal_id="sig-medium",
        run_id=RUN_ID,
        source_type=RiskSignalSourceType.RULE,
        asset_id="asset:node-00000",
        strength=0.9,
        confidence=1.0,
        sim_time=datetime.now(tz=UTC),
        deduplication_key="medium",
        status=RiskSignalStatus.ACTIVE,
        provenance_ref="alert:medium",
    )
    started = time.perf_counter()
    result = compute_risk_scores(
        snapshot,
        [signal],
        DEFAULT_RISK_ENGINE_CONFIG_V1,
        current_sim_time=datetime.now(tz=UTC),
        computed_at_sequence=1001,
    )
    elapsed = time.perf_counter() - started
    assert elapsed < BUDGET_SECONDS
    assert len(result.scores) > 0
    assert all(score.total <= 1.0 for score in result.scores)
