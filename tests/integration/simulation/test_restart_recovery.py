"""Integration regression for restart recovery (AEGIS-BUG-005) against PostgreSQL.

Drives the full persistence path — create/step/pause via ``RunCommandService`` (which now
checkpoints each command) plus an approvals-style EXECUTE containment that does NOT
checkpoint — then simulates a process restart with a fresh service (empty runtime cache)
and asserts recovery restores the authoritative lifecycle status and executed-action world
effects exactly, not merely a matching event count.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import RunCreateRequestV1, SimulationCommandType
from aegis_contracts.simulation import SimulationRunStatus
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain.normalized_hash import checkpoint_checksum
from aegis_simulation_domain.runtime import SimulationRuntime

PACKAGE_PATH = "scenarios/_fixtures/valid-minimal"
SEED = 90210
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FD0"
CONTAINED_STATUS = "isolated"


def _world_digest(runtime: SimulationRuntime) -> str:
    snapshot = runtime.world.to_snapshot(
        clock=runtime.clock, queue=runtime.queue, rng=runtime.rng
    )
    return checkpoint_checksum(snapshot.model_dump(mode="json", by_alias=True))


@pytest.mark.asyncio
async def test_restart_recovery_restores_paused_and_contained(unit_of_work) -> None:
    service = RunCommandService(workspace_root=Path("."))

    await service.create_run(
        unit_of_work,
        RunCreateRequestV1(
            schema_version=1,
            scenario_package_path=PACKAGE_PATH,
            seed=SEED,
            run_id=RUN_ID,
        ),
    )
    for index in range(4):
        await service.execute_lifecycle_command(
            unit_of_work,
            RUN_ID,
            SimulationCommandType.STEP,
            idempotency_key=f"cmd-step-{index}",
        )
    await service.execute_lifecycle_command(
        unit_of_work,
        RUN_ID,
        SimulationCommandType.PAUSE,
        idempotency_key="cmd-pause",
    )

    # Approved containment executes through the shared runtime WITHOUT a checkpoint,
    # exactly as the approvals service does — so it lands after the latest checkpoint.
    live_runtime = service.runtime_cache[RUN_ID].runtime
    asset_id = next(iter(sorted(live_runtime.world.assets)))
    sim_service = SimulationApplicationService(unit_of_work)
    containment = SimulationApplicationService.build_command(
        command_id="cmd-contain",
        command_type=SimulationCommandType.EXECUTE,
        run_id=RUN_ID,
        payload={
            "pluginId": "effect.set_asset_status",
            "config": {"assetId": asset_id, "status": CONTAINED_STATUS},
            "targetAssetId": asset_id,
        },
    )
    await sim_service.execute_command(live_runtime, containment)
    await unit_of_work.commit()

    reference_digest = _world_digest(live_runtime)
    assert live_runtime.world.status is SimulationRunStatus.PAUSED
    assert live_runtime.world.assets[asset_id].status == CONTAINED_STATUS

    # Simulate a process restart: a brand-new service with an empty runtime cache.
    restarted = RunCommandService(workspace_root=Path("."))
    restored = await restarted._get_or_restore_runtime(unit_of_work, RUN_ID)

    assert restored.world.status is SimulationRunStatus.PAUSED
    assert restored.world.status is not SimulationRunStatus.RUNNING
    assert restored.world.assets[asset_id].status == CONTAINED_STATUS
    assert _world_digest(restored) == reference_digest

    # Determinism: a second independent recovery reproduces the identical world state.
    again = RunCommandService(workspace_root=Path("."))
    restored_again = await again._get_or_restore_runtime(unit_of_work, RUN_ID)
    assert _world_digest(restored_again) == reference_digest


@pytest.mark.asyncio
async def test_replay_context_write_fails_closed(unit_of_work) -> None:
    """OITB-006: a replay-scoped context must mechanically reject a live event append."""
    from aegis_persistence.object_storage import InMemoryObjectStorage
    from aegis_replay.errors import ReplayEngineError
    from aegis_replay.service import ReplayService

    service = ReplayService(InMemoryObjectStorage.create())
    service.assert_read_only(unit_of_work)

    before = await unit_of_work.events.next_sequence(RUN_ID)
    from tests.replay.helpers import make_event

    with pytest.raises(ReplayEngineError):
        await unit_of_work.append_event(
            make_event(sequence=0, event_type="sim.run.started")
        )

    after = await unit_of_work.events.next_sequence(RUN_ID)
    assert after == before
