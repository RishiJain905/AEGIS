"""Simulation helpers for offline detection calibration and evaluation."""

from __future__ import annotations

from pathlib import Path

from aegis_contracts import DomainEventEnvelopeV1
from aegis_ml.baselines.splits import GOLDEN_STEPS, SILENT_RELAY_SCENARIO_PATH
from aegis_simulation_domain import SimulationEngine


def run_scenario_events(
    *,
    scenario_path: Path | str = SILENT_RELAY_SCENARIO_PATH,
    seed: int,
    steps: int = GOLDEN_STEPS,
) -> tuple[str, list[DomainEventEnvelopeV1]]:
    package_dir = Path(scenario_path)
    manifest = SimulationEngine.load_manifest(package_dir)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(steps)
    return runtime.run_id, list(runtime.events)
