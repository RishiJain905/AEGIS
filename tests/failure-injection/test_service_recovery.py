"""Simulator and API process restart recovery against durable PostgreSQL state."""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import pytest
from aegis_contracts import SimulationCommandType
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation_domain import SimulationEngine

pytestmark = [pytest.mark.failure_injection, pytest.mark.asyncio]

FIXTURE = Path("scenarios/_fixtures/valid-minimal")


def _api_is_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


async def test_simulator_and_api_restart_restore_or_fail_closed(
    unit_of_work,
    compose_controller,
    settings,
) -> None:
    service = SimulationApplicationService(unit_of_work)
    runtime, _ = await service.create_run_from_package(FIXTURE, seed=42)
    await service.execute_command(
        runtime,
        service.build_command(
            command_id="cmd-phase34-restart-start",
            command_type=SimulationCommandType.START,
            run_id=runtime.run_id,
        ),
    )
    checkpoint = await service.save_checkpoint(runtime)
    await unit_of_work.commit()

    compose_controller.restart("simulator")
    restored = SimulationEngine.create_runtime(
        manifest=SimulationEngine.load_manifest(FIXTURE),
        seed=42,
        scenario_version_id=runtime.configuration.scenario_version_id,
        run_id=runtime.run_id,
    )
    await SimulationApplicationService(unit_of_work).restore_checkpoint(restored, checkpoint.id)
    assert restored.world.next_sequence == runtime.world.next_sequence

    compose_controller.restart("api")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not _api_is_healthy(settings.API_PORT):
        import asyncio

        await asyncio.sleep(0.25)
    assert _api_is_healthy(settings.API_PORT)
    stored_run = await unit_of_work.runs.get_by_id(runtime.run_id)
    assert stored_run is not None
    assert stored_run.status in {"running", "paused"}
