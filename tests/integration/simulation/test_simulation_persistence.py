"""Integration tests for simulation persistence against PostgreSQL."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import SimulationCommandType
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation_domain import SimulationEngine

FIXTURE = Path("scenarios/_fixtures/valid-minimal")


@pytest.mark.asyncio
async def test_create_run_and_persist_events(unit_of_work) -> None:
    service = SimulationApplicationService(unit_of_work)
    runtime, manifest = await service.create_run_from_package(FIXTURE, seed=42)
    start = service.build_command(
        command_id="cmd-start-integration",
        command_type=SimulationCommandType.START,
        run_id=runtime.run_id,
    )
    emitted = await service.execute_command(runtime, start)
    assert emitted
    step = service.build_command(
        command_id="cmd-step-integration",
        command_type=SimulationCommandType.STEP,
        run_id=runtime.run_id,
    )
    await service.execute_command(runtime, step)
    await unit_of_work.commit()

    stored_run = await unit_of_work.runs.get_by_id(runtime.run_id)
    assert stored_run is not None
    assert stored_run.seed == 42
    assert stored_run.scenario_version_id == f"scenario-version:{manifest.metadata.version}"


@pytest.mark.asyncio
async def test_checkpoint_persist_and_restore(unit_of_work) -> None:
    service = SimulationApplicationService(unit_of_work)
    runtime, _manifest = await service.create_run_from_package(FIXTURE, seed=7)
    await service.execute_command(
        runtime,
        service.build_command(
            command_id="cmd-start-ckpt",
            command_type=SimulationCommandType.START,
            run_id=runtime.run_id,
        ),
    )
    for index in range(5):
        await service.execute_command(
            runtime,
            service.build_command(
                command_id=f"cmd-step-{index}",
                command_type=SimulationCommandType.STEP,
                run_id=runtime.run_id,
            ),
        )
    checkpoint = await service.save_checkpoint(runtime)
    await unit_of_work.commit()

    loaded = await unit_of_work.checkpoints.get_by_id(checkpoint.id)
    assert loaded is not None
    assert loaded.checksum == checkpoint.checksum

    restored_runtime = SimulationEngine.create_runtime(
        manifest=SimulationEngine.load_manifest(FIXTURE),
        seed=7,
        scenario_version_id=runtime.configuration.scenario_version_id,
        run_id=runtime.run_id,
    )
    await service.restore_checkpoint(restored_runtime, checkpoint.id)
    assert restored_runtime.world.next_sequence == runtime.world.next_sequence


@pytest.mark.asyncio
async def test_duplicate_command_is_rejected(unit_of_work) -> None:
    service = SimulationApplicationService(unit_of_work)
    runtime, _manifest = await service.create_run_from_package(FIXTURE, seed=3)
    command = service.build_command(
        command_id="cmd-dup",
        command_type=SimulationCommandType.START,
        run_id=runtime.run_id,
    )
    await service.execute_command(runtime, command)
    from aegis_simulation_domain import SimulationError

    with pytest.raises(SimulationError):
        await service.execute_command(runtime, command)
