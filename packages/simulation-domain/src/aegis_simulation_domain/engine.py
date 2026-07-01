"""High-level simulation engine orchestrating runtime execution."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts.simulation import (
    NormalizedEventHashV1,
    RunConfigurationV1,
    SimulationCheckpointV1,
    SimulationCommandV1,
)
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_scenario_sdk.validation.pipeline import validate_package

from aegis_simulation_domain.ids import derive_run_id
from aegis_simulation_domain.normalized_hash import compute_normalized_event_hash
from aegis_simulation_domain.runtime import SIMULATION_ENGINE_VERSION, SimulationRuntime


class SimulationEngine:
    @staticmethod
    def load_manifest(package_dir: Path) -> ScenarioManifestV1:
        outcome = validate_package(package_dir, verify_existing_manifest=False)
        if not outcome.valid or outcome.manifest is None:
            messages = "; ".join(d.message for d in outcome.diagnostics)
            msg = f"Invalid scenario package: {messages}"
            raise ValueError(msg)
        return outcome.manifest

    @staticmethod
    def create_runtime(
        *,
        manifest: ScenarioManifestV1,
        seed: int,
        scenario_version_id: str,
        initial_sim_time: datetime | None = None,
        recorded_at_epoch: datetime | None = None,
        run_id: str | None = None,
        max_steps: int | None = None,
    ) -> SimulationRuntime:
        epoch = (recorded_at_epoch or datetime(2026, 1, 1, tzinfo=UTC)).astimezone(UTC)
        start_time = (initial_sim_time or epoch).astimezone(UTC)
        configuration = RunConfigurationV1(
            schema_version=1,
            scenario_version_id=scenario_version_id,
            seed=seed,
            engine_version=SIMULATION_ENGINE_VERSION,
            initial_sim_time=start_time,
            recorded_at_epoch=epoch,
            max_steps=max_steps,
        )
        resolved_run_id = run_id or derive_run_id(
            run_seed=seed,
            scenario_version_id=scenario_version_id,
        )
        return SimulationRuntime(
            run_id=resolved_run_id,
            configuration=configuration,
            manifest=manifest,
        )

    @staticmethod
    def run_to_completion(runtime: SimulationRuntime, *, max_steps: int) -> list:
        runtime.start()
        return runtime.run_steps(max_steps)

    @staticmethod
    def normalized_hash(
        runtime: SimulationRuntime,
        *,
        scenario_version_id: str,
    ) -> NormalizedEventHashV1:
        return compute_normalized_event_hash(
            events=runtime.events,
            scenario_version_id=scenario_version_id,
            seed=runtime.configuration.seed,
            engine_version=SIMULATION_ENGINE_VERSION,
        )

    @staticmethod
    def restore_checkpoint(runtime: SimulationRuntime, checkpoint: SimulationCheckpointV1) -> None:
        runtime.restore(checkpoint)

    @staticmethod
    def clone_runtime(runtime: SimulationRuntime) -> SimulationRuntime:
        return deepcopy(runtime)

    @staticmethod
    def handle_command(runtime: SimulationRuntime, command: SimulationCommandV1) -> list:
        emitted = runtime.execute_command(command)
        return emitted
