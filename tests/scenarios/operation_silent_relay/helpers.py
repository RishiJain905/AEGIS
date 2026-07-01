"""Shared helpers for Operation Silent Relay tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from aegis_simulation_domain import SimulationEngine

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = ROOT / "scenarios" / "operation-silent-relay"
GOLDEN_SEEDS_PATH = SCENARIO / "golden-seeds.yaml"
EVIDENCE_PATH = SCENARIO / "expected-evidence.yaml"
STEPS = 300


def load_golden_seeds() -> dict:
    return yaml.safe_load(GOLDEN_SEEDS_PATH.read_text(encoding="utf-8"))


def run_scenario(seed: int, steps: int = STEPS) -> tuple[object, str]:
    manifest = SimulationEngine.load_manifest(SCENARIO)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(steps)
    normalized = SimulationEngine.normalized_hash(
        runtime,
        scenario_version_id=scenario_version_id,
    )
    return runtime, normalized.hash_value


def event_types_for_run(seed: int) -> set[str]:
    manifest = SimulationEngine.load_manifest(SCENARIO)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(STEPS)
    return {event.type for event in runtime.events}
