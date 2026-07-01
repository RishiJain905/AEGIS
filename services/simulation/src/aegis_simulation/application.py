"""Simulation application service with persistence integration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts import (
    ActorRef,
    ActorType,
    DomainEventEnvelopeV1,
    IdempotencyRecordV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCheckpointV1,
    SimulationCommandType,
    SimulationCommandV1,
)
from aegis_contracts.versioning import (
    IDEMPOTENCY_RECORD_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
    SIMULATION_COMMAND_SCHEMA_VERSION,
)
from aegis_persistence.protocols import UnitOfWork
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
from aegis_simulation_domain.runtime import SimulationRuntime

SIMULATION_COMMAND_SCOPE = "simulation-command"


class SimulationApplicationService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._uow = unit_of_work

    async def create_run_from_package(
        self,
        package_dir: Path,
        *,
        seed: int,
        run_id: str | None = None,
    ) -> tuple[SimulationRuntime, ScenarioManifestV1]:
        manifest = SimulationEngine.load_manifest(package_dir)
        scenario_id = manifest.metadata.scenario_id
        scenario_version_id = f"scenario-version:{manifest.metadata.version}"
        now = datetime(2026, 1, 1, tzinfo=UTC)

        scenario = ScenarioV1(
            schema_version=SCENARIO_SCHEMA_VERSION,
            id=scenario_id,
            name=manifest.metadata.name,
            description=manifest.metadata.description,
            created_at=now,
        )
        scenario_version = ScenarioVersionV1(
            schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
            id=scenario_version_id,
            scenario_id=scenario_id,
            version=manifest.metadata.version,
            required_platform_version=manifest.metadata.required_platform_version,
            published_at=now,
        )
        runtime = SimulationEngine.create_runtime(
            manifest=manifest,
            seed=seed,
            scenario_version_id=scenario_version_id,
            run_id=run_id,
        )
        run = RunV1(
            schema_version=RUN_SCHEMA_VERSION,
            id=runtime.run_id,
            scenario_version_id=scenario_version_id,
            seed=seed,
            status="created",
            started_at=now,
            sim_time=runtime.configuration.initial_sim_time,
            revision=0,
        )

        existing = await self._uow.scenarios.get_by_id(scenario_id)
        if existing is None:
            await self._uow.scenarios.add(scenario)
        existing_version = await self._uow.scenario_versions.get_by_id(scenario_version_id)
        if existing_version is None:
            await self._uow.scenario_versions.add(scenario_version)
        await self._uow.runs.add(run)
        return runtime, manifest

    async def persist_events(
        self, runtime: SimulationRuntime, events: list[DomainEventEnvelopeV1]
    ) -> None:
        for event in events:
            await self._uow.append_event(event)
        if events:
            run = await self._uow.runs.get_by_id(runtime.run_id)
            if run is not None:
                updated = run.model_copy(
                    update={
                        "status": runtime.world.status.value,
                        "sim_time": runtime.clock.sim_time,
                        "revision": run.revision + 1,
                    }
                )
                await self._uow.runs.update_with_revision(updated, expected_revision=run.revision)

    async def execute_command(
        self,
        runtime: SimulationRuntime,
        command: SimulationCommandV1,
    ) -> list[DomainEventEnvelopeV1]:
        existing = await self._uow.idempotency.get(
            scope=SIMULATION_COMMAND_SCOPE,
            idempotency_key=command.command_id,
        )
        if existing is not None:
            raise SimulationError(
                code=SimulationErrorCode.DUPLICATE_COMMAND,
                message="Duplicate simulation command",
                details={"commandId": command.command_id},
            )
        emitted = SimulationEngine.handle_command(runtime, command)
        await self.persist_events(runtime, emitted)
        record = IdempotencyRecordV1(
            schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
            scope=SIMULATION_COMMAND_SCOPE,
            idempotency_key=command.command_id,
            request_hash=None,
            response_ref=runtime.run_id,
            replayed=False,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        await self._uow.idempotency.add(record)
        return emitted

    async def save_checkpoint(self, runtime: SimulationRuntime) -> SimulationCheckpointV1:
        checkpoint = runtime.checkpoint()
        await self._uow.checkpoints.add(checkpoint)
        if runtime.events:
            await self._uow.append_event(runtime.events[-1])
        return checkpoint

    async def restore_checkpoint(
        self,
        runtime: SimulationRuntime,
        checkpoint_id: str,
    ) -> SimulationCheckpointV1:
        checkpoint = await self._uow.checkpoints.get_by_id(checkpoint_id)
        if checkpoint is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Checkpoint not found: {checkpoint_id}",
            )
        SimulationEngine.restore_checkpoint(runtime, checkpoint)
        return checkpoint

    @staticmethod
    def build_command(
        *,
        command_id: str,
        command_type: SimulationCommandType,
        run_id: str,
        payload: dict[str, object] | None = None,
        actor: ActorRef | None = None,
        authorization_token: str | None = "synthetic-operator-token",
    ) -> SimulationCommandV1:
        return SimulationCommandV1(
            schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
            command_id=command_id,
            command_type=command_type,
            run_id=run_id,
            actor=actor or ActorRef(type=ActorType.OPERATOR, id="asset:operator-console"),
            authorization_token=authorization_token,
            payload=dict(payload or {}),
        )
