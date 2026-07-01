"""Runtime lifecycle and determinism unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import ActorRef, ActorType, SimulationCommandType
from aegis_contracts.versioning import SIMULATION_COMMAND_SCHEMA_VERSION
from aegis_simulation_domain import SimulationEngine, SimulationError
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION, SimulationRuntime

FIXTURE = Path("scenarios/_fixtures/valid-minimal")


def _runtime(seed: int = 42) -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id="scenario-version:1.0.0-fixture",
    )
    runtime.start()
    return runtime


def test_same_seed_produces_identical_normalized_hash() -> None:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    scenario_version_id = "scenario-version:1.0.0-fixture"
    first = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    second = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    first.start()
    second.start()
    first.run_steps(30)
    second.run_steps(30)
    assert SimulationEngine.normalized_hash(
        first, scenario_version_id=scenario_version_id
    ).hash_value == (
        SimulationEngine.normalized_hash(second, scenario_version_id=scenario_version_id).hash_value
    )


def test_different_seed_produces_different_hash() -> None:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    scenario_version_id = "scenario-version:1.0.0-fixture"
    a = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    b = SimulationEngine.create_runtime(
        manifest=manifest, seed=99, scenario_version_id=scenario_version_id
    )
    a.start()
    b.start()
    a.run_steps(30)
    b.run_steps(30)
    assert SimulationEngine.normalized_hash(
        a, scenario_version_id=scenario_version_id
    ).hash_value != (
        SimulationEngine.normalized_hash(b, scenario_version_id=scenario_version_id).hash_value
    )


def test_checkpoint_restore_matches_uninterrupted_run() -> None:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    scenario_version_id = "scenario-version:1.0.0-fixture"
    uninterrupted = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    uninterrupted.start()
    uninterrupted.run_steps(10)
    uninterrupted.checkpoint()
    uninterrupted.run_steps(20)
    uninterrupted_hash = SimulationEngine.normalized_hash(
        uninterrupted,
        scenario_version_id=scenario_version_id,
    ).hash_value

    checkpoint_runtime = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    checkpoint_runtime.start()
    checkpoint_runtime.run_steps(10)
    checkpoint = checkpoint_runtime.checkpoint()
    events_before_checkpoint = list(checkpoint_runtime.events)

    restored = SimulationEngine.create_runtime(
        manifest=manifest, seed=42, scenario_version_id=scenario_version_id
    )
    restored.restore(checkpoint)
    restored.run_steps(20)
    from aegis_simulation_domain.normalized_hash import compute_normalized_event_hash

    restored_hash = compute_normalized_event_hash(
        events=events_before_checkpoint + restored.events,
        scenario_version_id=scenario_version_id,
        seed=42,
        engine_version=SIMULATION_ENGINE_VERSION,
    ).hash_value
    assert restored_hash == uninterrupted_hash


def test_agent_command_is_rejected() -> None:
    runtime = _runtime()
    from aegis_contracts import SimulationCommandV1

    command = SimulationCommandV1(
        schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
        command_id="cmd-agent",
        command_type=SimulationCommandType.EXECUTE,
        run_id=runtime.run_id,
        actor=ActorRef(type=ActorType.AGENT, id="agent-session:test"),
        authorization_token="token",
        payload={"pluginId": "effect.set_asset_status", "config": {"status": "suspicious"}},
    )
    with pytest.raises(SimulationError):
        runtime.execute_command(command)


def test_incompatible_checkpoint_is_rejected() -> None:
    runtime = _runtime()
    runtime.run_steps(5)
    checkpoint = runtime.checkpoint()
    bad = checkpoint.model_copy(update={"engine_version": "0.0.0-legacy"})
    with pytest.raises(SimulationError):
        runtime.restore(bad)
