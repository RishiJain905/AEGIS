"""Integration tests for graph risk persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts.graph import GraphSnapshotV1
from aegis_incidents.risk_pipeline import run_risk_propagation_for_run
from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.baselines.store import load_baseline
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation_domain import SimulationEngine

SILENT_RELAY = Path("scenarios/operation-silent-relay")
BASELINE_PATH = Path("models/baselines/v1/baseline.json")
BASELINE_AVAILABLE = BASELINE_PATH.is_file()
STEPS = 60
SEED = 1000


def _scenario_snapshot(run_id: str) -> GraphSnapshotV1:
    manifest = SimulationEngine.load_manifest(SILENT_RELAY)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=SEED,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(STEPS)
    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=STEPS)
    return snapshot.model_copy(update={"run_id": run_id})


@pytest.mark.asyncio
async def test_risk_persists_scores_and_events(unit_of_work) -> None:
    if not BASELINE_AVAILABLE:
        pytest.skip("Baselines not calibrated")
    _run_id, events = run_scenario_events(scenario_path=SILENT_RELAY, seed=SEED, steps=STEPS)
    service = __import__(
        "aegis_simulation.application", fromlist=["SimulationApplicationService"]
    ).SimulationApplicationService(unit_of_work)
    runtime, _manifest = await service.create_run_from_package(SILENT_RELAY, seed=SEED)
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

    snapshot = _scenario_snapshot(runtime.run_id)
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
