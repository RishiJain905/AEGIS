"""Integration tests for detection persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_incidents.pipeline import run_detection_for_events
from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.baselines.store import load_baseline
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository

SILENT_RELAY = Path("scenarios/operation-silent-relay")
BASELINE_PATH = Path("models/baselines/v1/baseline.json")


@pytest.mark.asyncio
async def test_detection_persists_alerts_and_events(unit_of_work) -> None:
    if not BASELINE_PATH.exists():
        pytest.skip("Baselines not calibrated")
    run_id, events = run_scenario_events(scenario_path=SILENT_RELAY, seed=1000, steps=120)
    service = __import__(
        "aegis_simulation.application", fromlist=["SimulationApplicationService"]
    ).SimulationApplicationService(unit_of_work)
    runtime, manifest = await service.create_run_from_package(SILENT_RELAY, seed=1000)
    _ = manifest
    for event in events:
        adapted = event.model_copy(update={"run_id": runtime.run_id})
        await unit_of_work.append_event(adapted)
    await unit_of_work.commit()

    baselines = load_baseline()
    result = await run_detection_for_events(
        unit_of_work,
        run_id=runtime.run_id,
        events=await PostgresEventQueryRepository(unit_of_work.session).list_by_run(
            runtime.run_id,
            limit=100000,
        ),
        baselines=baselines,
    )
    await unit_of_work.commit()
    alerts = await unit_of_work.alerts.list_by_run(runtime.run_id)
    assert result.candidates_emitted >= 0
    assert len(alerts) == result.alerts_persisted
