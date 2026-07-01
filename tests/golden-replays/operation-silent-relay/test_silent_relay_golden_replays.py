"""Golden deterministic replay tests for Operation Silent Relay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION

FIXTURE = Path("scenarios/operation-silent-relay")
GOLDEN_DIR = Path(__file__).parent
REGISTRY = FIXTURE / "golden-seeds.yaml"
STEPS = 300


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


@pytest.mark.parametrize(
    "seed",
    [entry["seed"] for entry in yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["seeds"]],
)
def test_golden_hash_matches_recorded_artifact(seed: int) -> None:
    golden_path = GOLDEN_DIR / f"expected_hash_seed_{seed}.json"
    actual = _run_hash(seed, STEPS)
    if not golden_path.exists():
        golden_path.write_text(
            json.dumps(
                {
                    "scenario": str(FIXTURE),
                    "seed": seed,
                    "steps": STEPS,
                    "engineVersion": SIMULATION_ENGINE_VERSION,
                    "normalizedHash": actual,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert expected["engineVersion"] == SIMULATION_ENGINE_VERSION
    assert actual == expected["normalizedHash"]


def test_different_seed_changes_golden_hash() -> None:
    assert _run_hash(1000, STEPS) != _run_hash(1006, STEPS)
