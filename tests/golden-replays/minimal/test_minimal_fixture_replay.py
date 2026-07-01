"""Golden deterministic replay tests for minimal fixture."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION

FIXTURE = Path("scenarios/_fixtures/valid-minimal")
GOLDEN_PATH = Path(__file__).parent / "expected_hash_seed_42.json"


def _run_hash(seed: int, steps: int) -> str:
    manifest = SimulationEngine.load_manifest(FIXTURE)
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
    return normalized.hash_value


def test_golden_hash_seed_42_matches_recorded_artifact() -> None:
    actual = _run_hash(42, 30)
    if not GOLDEN_PATH.exists():
        GOLDEN_PATH.write_text(
            json.dumps(
                {
                    "scenario": str(FIXTURE),
                    "seed": 42,
                    "steps": 30,
                    "engineVersion": SIMULATION_ENGINE_VERSION,
                    "normalizedHash": actual,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert expected["engineVersion"] == SIMULATION_ENGINE_VERSION
    assert actual == expected["normalizedHash"]


def test_different_seed_changes_golden_hash() -> None:
    assert _run_hash(42, 30) != _run_hash(99, 30)
