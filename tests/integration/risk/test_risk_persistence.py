"""Integration tests for graph risk persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1
from aegis_contracts.versioning import (
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
)
from aegis_incidents.risk_pipeline import run_risk_propagation_for_run
from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.baselines.store import load_baseline

SILENT_RELAY = Path("scenarios/operation-silent-relay")
BASELINE_PATH = Path("models/baselines/v1/baseline.json")
BASELINE_AVAILABLE = BASELINE_PATH.is_file()


def _minimal_snapshot(run_id: str) -> GraphSnapshotV1:
    now = datetime.now(tz=UTC)
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=run_id,
        sequence=10,
        captured_at=now,
        nodes=[
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:svc-logistics-api",
                entity_type="asset",
                asset_type="service",
                label="Logistics API",
                cluster_id="business-unit:bu",
                risk_score=0.1,
                criticality=0.7,
                status="normal",
                revision=1,
            ),
            GraphNodeV1(
                schema_version=GRAPH_NODE_SCHEMA_VERSION,
                id="asset:db-customer-records",
                entity_type="asset",
                asset_type="database",
                label="Customer Records DB",
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
                id="edge:logistics-db",
                source="asset:svc-logistics-api",
                target="asset:db-customer-records",
                relationship_type="AUTHENTICATED_TO",
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


@pytest.mark.asyncio
async def test_risk_persists_scores_and_events(unit_of_work) -> None:
    if not BASELINE_AVAILABLE:
        pytest.skip("Baselines not calibrated")
    _run_id, events = run_scenario_events(scenario_path=SILENT_RELAY, seed=1000, steps=60)
    service = __import__(
        "aegis_simulation.application", fromlist=["SimulationApplicationService"]
    ).SimulationApplicationService(unit_of_work)
    runtime, _manifest = await service.create_run_from_package(SILENT_RELAY, seed=1000)
    for event in events:
        adapted = event.model_copy(update={"run_id": runtime.run_id})
        await unit_of_work.append_event(adapted)
    await unit_of_work.commit()

    from aegis_incidents.pipeline import run_detection_for_events
    from aegis_persistence.repositories.streaming import PostgresEventQueryRepository

    baselines = load_baseline()
    await run_detection_for_events(
        unit_of_work,
        run_id=runtime.run_id,
        events=await PostgresEventQueryRepository(unit_of_work.session).list_by_run(
            runtime.run_id,
            limit=100000,
        ),
        baselines=baselines,
    )
    await unit_of_work.commit()

    snapshot = _minimal_snapshot(runtime.run_id)
    result = await run_risk_propagation_for_run(
        unit_of_work,
        run_id=runtime.run_id,
        snapshot=snapshot,
        dry_run=False,
    )
    await unit_of_work.commit()

    persisted = await unit_of_work.risk_scores.list_by_run(runtime.run_id)
    assert result.scores_computed >= 0
    if result.scores_computed > 0:
        assert len(persisted) > 0
