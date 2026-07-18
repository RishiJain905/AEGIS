"""Regression tests for restart recovery (AEGIS-BUG-005).

Recovery must reconstruct the *authoritative* runtime state — lifecycle status and
executed-action world effects — rather than advancing a fresh seeded runtime until its
event count matches PostgreSQL. These tests exercise the real reconstruction helpers on
``RunCommandService`` (checkpoint restore + post-checkpoint replay, and the from-scratch
replay fallback) and assert a golden-style determinism property: recovery reproduces the
identical normalized world state, byte for byte.
"""

from __future__ import annotations

from pathlib import Path

from aegis_contracts.simulation import SimulationCommandType, SimulationRunStatus
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation.run_command_service import RunCommandService, _is_sim_event
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.normalized_hash import checkpoint_checksum
from aegis_simulation_domain.runtime import SimulationRuntime

FIXTURE = Path("scenarios/_fixtures/valid-minimal")
SCENARIO_VERSION_ID = "scenario-version:1.0.0-fixture"
SEED = 4242
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69TEST0"
CONTAINED_STATUS = "isolated"


def _new_runtime() -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    return SimulationEngine.create_runtime(
        manifest=manifest,
        seed=SEED,
        scenario_version_id=SCENARIO_VERSION_ID,
        run_id=RUN_ID,
    )


def _world_digest(runtime: SimulationRuntime) -> str:
    snapshot = runtime.world.to_snapshot(
        clock=runtime.clock, queue=runtime.queue, rng=runtime.rng
    )
    return checkpoint_checksum(snapshot.model_dump(mode="json", by_alias=True))


def _execute_containment(runtime: SimulationRuntime, asset_id: str) -> None:
    """Apply an approved containment (isolate an asset) via the EXECUTE command path."""
    command = SimulationApplicationService.build_command(
        command_id=f"cmd-contain-{asset_id}",
        command_type=SimulationCommandType.EXECUTE,
        run_id=runtime.run_id,
        payload={
            "pluginId": "effect.set_asset_status",
            "config": {"assetId": asset_id, "status": CONTAINED_STATUS},
            "targetAssetId": asset_id,
        },
    )
    runtime.execute_command(command)


def _sim_events(runtime: SimulationRuntime) -> list:
    return [event for event in runtime.events if _is_sim_event(event)]


def test_recovery_restores_paused_status_and_contained_asset() -> None:
    """Checkpoint restore + post-checkpoint replay of an approved containment.

    Mirrors the production hot path: lifecycle commands checkpoint (here: PAUSE), the
    approvals service then executes a containment without checkpointing, and a restart
    must restore the paused status AND re-apply the containment from the post-checkpoint
    event.
    """
    service = RunCommandService(workspace_root=Path("."))

    reference = _new_runtime()
    reference.start()
    reference.run_steps(4)
    reference.pause()
    checkpoint = reference.snapshot_checkpoint()  # paused, pre-containment
    asset_id = next(iter(sorted(reference.world.assets)))
    _execute_containment(reference, asset_id)  # post-checkpoint, no new checkpoint

    assert reference.world.status is SimulationRunStatus.PAUSED
    assert reference.world.assets[asset_id].status == CONTAINED_STATUS

    post_checkpoint = [
        event
        for event in _sim_events(reference)
        if event.sequence >= checkpoint.world_state.next_sequence
    ]
    assert post_checkpoint, "containment must produce a post-checkpoint event"

    restored = _new_runtime()
    restored.restore(checkpoint)
    service._replay_events(restored, post_checkpoint)

    # Authoritative lifecycle status is preserved (never silently RUNNING).
    assert restored.world.status is SimulationRunStatus.PAUSED
    # Executed-action world effect is faithfully reconstructed.
    assert restored.world.assets[asset_id].status == CONTAINED_STATUS
    # Golden-style determinism: identical normalized world state (status, assets, RNG,
    # queue, clock, sequence) as the live runtime.
    assert _world_digest(restored) == _world_digest(reference)


def test_recovery_from_scratch_reproduces_identical_state() -> None:
    """No checkpoint (legacy run): full deterministic replay reproduces exact state."""
    service = RunCommandService(workspace_root=Path("."))

    reference = _new_runtime()
    reference.start()
    reference.run_steps(6)
    asset_id = next(iter(sorted(reference.world.assets)))
    _execute_containment(reference, asset_id)
    reference.pause()

    restored = _new_runtime()
    service._replay_events(restored, _sim_events(reference))

    assert restored.world.status is SimulationRunStatus.PAUSED
    assert restored.world.assets[asset_id].status == CONTAINED_STATUS
    # Re-stepping is deterministic, so RNG/queue/clock match exactly too.
    assert _world_digest(restored) == _world_digest(reference)


def test_recovery_is_deterministic_across_runs() -> None:
    """Two independent recoveries produce byte-identical normalized state (golden)."""
    service = RunCommandService(workspace_root=Path("."))

    reference = _new_runtime()
    reference.start()
    reference.run_steps(5)
    asset_id = next(iter(sorted(reference.world.assets)))
    _execute_containment(reference, asset_id)
    reference.stop()
    events = _sim_events(reference)

    first = _new_runtime()
    service._replay_events(first, events)
    second = _new_runtime()
    service._replay_events(second, events)

    assert _world_digest(first) == _world_digest(second) == _world_digest(reference)


def test_recovery_preserves_stopped_status_not_running() -> None:
    """The core BUG-005 defect: a stopped run must never restore as RUNNING."""
    service = RunCommandService(workspace_root=Path("."))

    reference = _new_runtime()
    reference.start()
    reference.run_steps(3)
    reference.stop()

    restored = _new_runtime()
    service._replay_events(restored, _sim_events(reference))

    assert restored.world.status is SimulationRunStatus.STOPPED
    assert restored.world.status is not SimulationRunStatus.RUNNING


def test_snapshot_checkpoint_does_not_emit_event() -> None:
    """The recovery checkpoint must not perturb the determinism-golden event stream."""
    runtime = _new_runtime()
    runtime.start()
    runtime.run_steps(2)
    before = list(runtime.events)
    before_sequence = runtime.world.next_sequence

    checkpoint = runtime.snapshot_checkpoint()

    assert runtime.events == before
    assert runtime.world.next_sequence == before_sequence
    assert checkpoint.sequence_at_checkpoint == before_sequence
    assert checkpoint.world_state.next_sequence == before_sequence
