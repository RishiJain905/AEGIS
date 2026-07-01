"""Acceptance criteria mapping for Phase 09."""

from __future__ import annotations

from pathlib import Path

from aegis_simulation_domain import SimulationEngine


def test_ac1_fixed_inputs_produce_stable_histories() -> None:
    fixture = Path("scenarios/_fixtures/valid-minimal")
    manifest = SimulationEngine.load_manifest(fixture)
    scenario_version_id = "scenario-version:1.0.0-fixture"
    runs = []
    for _ in range(2):
        runtime = SimulationEngine.create_runtime(
            manifest=manifest,
            seed=42,
            scenario_version_id=scenario_version_id,
        )
        runtime.start()
        runtime.run_steps(25)
        runs.append(
            SimulationEngine.normalized_hash(runtime, scenario_version_id=scenario_version_id)
        )
    assert runs[0].hash_value == runs[1].hash_value


def test_ac2_checkpoint_restore_matches_uninterrupted() -> None:
    from aegis_simulation_domain.normalized_hash import compute_normalized_event_hash
    from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION

    fixture = Path("scenarios/_fixtures/valid-minimal")
    manifest = SimulationEngine.load_manifest(fixture)
    scenario_version_id = "scenario-version:1.0.0-fixture"
    full = SimulationEngine.create_runtime(
        manifest=manifest, seed=7, scenario_version_id=scenario_version_id
    )
    full.start()
    full.run_steps(8)
    full.checkpoint()
    full.run_steps(12)
    full_hash = SimulationEngine.normalized_hash(
        full, scenario_version_id=scenario_version_id
    ).hash_value

    partial = SimulationEngine.create_runtime(
        manifest=manifest, seed=7, scenario_version_id=scenario_version_id
    )
    partial.start()
    partial.run_steps(8)
    checkpoint = partial.checkpoint()
    events_before = list(partial.events)
    recovered = SimulationEngine.create_runtime(
        manifest=manifest, seed=7, scenario_version_id=scenario_version_id
    )
    recovered.restore(checkpoint)
    recovered.run_steps(12)
    recovered_hash = compute_normalized_event_hash(
        events=events_before + recovered.events,
        scenario_version_id=scenario_version_id,
        seed=7,
        engine_version=SIMULATION_ENGINE_VERSION,
    ).hash_value
    assert recovered_hash == full_hash


def test_ac3_commands_require_authorization_context() -> None:
    from aegis_contracts import ActorRef, ActorType, SimulationCommandType, SimulationCommandV1
    from aegis_contracts.versioning import SIMULATION_COMMAND_SCHEMA_VERSION
    from aegis_simulation_domain import SimulationError

    fixture = Path("scenarios/_fixtures/valid-minimal")
    manifest = SimulationEngine.load_manifest(fixture)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=1,
        scenario_version_id="scenario-version:1.0.0-fixture",
    )
    runtime.start()
    command = SimulationCommandV1(
        schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
        command_id="cmd-no-auth",
        command_type=SimulationCommandType.STOP,
        run_id=runtime.run_id,
        actor=ActorRef(type=ActorType.OPERATOR, id="asset:operator-console"),
        authorization_token=None,
        payload={},
    )
    try:
        runtime.execute_command(command)
        rejected = False
    except SimulationError:
        rejected = True
    assert rejected


def test_ac4_simulator_owns_truth_independently() -> None:
    fixture = Path("scenarios/_fixtures/valid-minimal")
    manifest = SimulationEngine.load_manifest(fixture)
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=42,
        scenario_version_id="scenario-version:1.0.0-fixture",
    )
    runtime.start()
    runtime.run_steps(15)
    assert runtime.events
    assert all(event.run_id == runtime.run_id for event in runtime.events)
    assert runtime.world.assets
