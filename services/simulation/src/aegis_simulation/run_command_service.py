"""Run command orchestration with runtime cache and graph projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aegis_contracts import (
    IdempotencyMetadataV1,
    RunCommandResponseV1,
    RunCreateRequestV1,
    SimulationCommandType,
    SnapshotBootstrapPayloadV1,
)
from aegis_contracts.versioning import (
    RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
    SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION,
)
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
from aegis_simulation_domain.runtime import SimulationRuntime

from aegis_simulation.application import SIMULATION_COMMAND_SCOPE, SimulationApplicationService
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime

SCENARIO_PACKAGE_BY_VERSION: dict[str, str] = {
    "scenario-version:1.0.0-silent-relay": "scenarios/operation-silent-relay",
    "scenario-version:1.0.0-fixture": "scenarios/_fixtures/valid-minimal",
    "scenario-version:synthetic-dev-v1": "scenarios/_fixtures/valid-minimal",
}


@dataclass
class RuntimeCacheEntry:
    runtime: SimulationRuntime
    package_dir: Path


@dataclass
class RunCommandService:
    workspace_root: Path
    runtime_cache: dict[str, RuntimeCacheEntry] = field(default_factory=dict)

    def resolve_package_dir(self, *, package_path: str | None, scenario_version_id: str) -> Path:
        relative = package_path or SCENARIO_PACKAGE_BY_VERSION.get(scenario_version_id)
        if relative is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"No scenario package mapping for {scenario_version_id}",
            )
        package_dir = (self.workspace_root / relative).resolve()
        if not package_dir.exists():
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Scenario package not found: {relative}",
            )
        return package_dir

    async def create_run(
        self,
        uow: PostgresUnitOfWork,
        request: RunCreateRequestV1,
        *,
        idempotency_key: str | None = None,
    ) -> RunCommandResponseV1:
        if idempotency_key is not None:
            existing = await uow.idempotency.get(
                scope=SIMULATION_COMMAND_SCOPE,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                run = await uow.runs.get_by_id(existing.response_ref or "")
                if run is None:
                    raise SimulationError(
                        code=SimulationErrorCode.VALIDATION_FAILED,
                        message="Idempotency record references missing run",
                    )
                return RunCommandResponseV1(
                    schema_version=RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
                    run=run,
                    events_emitted=0,
                    idempotency=IdempotencyMetadataV1(
                        schema_version=1,
                        idempotency_key=idempotency_key,
                        replayed=True,
                    ),
                )

        package_dir = (self.workspace_root / request.scenario_package_path).resolve()
        if not package_dir.exists():
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Scenario package not found: {request.scenario_package_path}",
            )

        service = SimulationApplicationService(uow)
        runtime, manifest = await service.create_run_from_package(
            package_dir,
            seed=request.seed,
            run_id=request.run_id,
        )
        _ = manifest

        command = service.build_command(
            command_id=idempotency_key or f"cmd-start-{request.seed}-{runtime.run_id}",
            command_type=SimulationCommandType.START,
            run_id=runtime.run_id,
        )
        try:
            emitted = await service.execute_command(runtime, command)
        except SimulationError as exc:
            if exc.code != SimulationErrorCode.DUPLICATE_COMMAND:
                raise
            emitted = []

        snapshot = build_graph_snapshot_from_runtime(runtime, sequence=0, revision=0)
        await PostgresGraphSnapshotRepository(uow.session).add(snapshot)

        self.runtime_cache[runtime.run_id] = RuntimeCacheEntry(
            runtime=runtime,
            package_dir=package_dir,
        )

        run = await uow.runs.get_by_id(runtime.run_id)
        if run is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message="Run not found after creation",
            )
        return RunCommandResponseV1(
            schema_version=RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
            run=run,
            events_emitted=len(emitted),
            idempotency=(
                IdempotencyMetadataV1(
                    schema_version=1,
                    idempotency_key=idempotency_key,
                    replayed=False,
                )
                if idempotency_key
                else None
            ),
        )

    async def execute_lifecycle_command(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
        command_type: SimulationCommandType,
        *,
        idempotency_key: str,
    ) -> RunCommandResponseV1:
        existing = await uow.idempotency.get(
            scope=SIMULATION_COMMAND_SCOPE,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            run = await uow.runs.get_by_id(run_id)
            if run is None:
                raise SimulationError(
                    code=SimulationErrorCode.VALIDATION_FAILED,
                    message=f"Run not found: {run_id}",
                )
            return RunCommandResponseV1(
                schema_version=RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
                run=run,
                events_emitted=0,
                idempotency=IdempotencyMetadataV1(
                    schema_version=1,
                    idempotency_key=idempotency_key,
                    replayed=True,
                ),
            )

        runtime = await self._get_or_restore_runtime(uow, run_id)
        service = SimulationApplicationService(uow)
        command = service.build_command(
            command_id=idempotency_key,
            command_type=command_type,
            run_id=run_id,
        )
        emitted = await service.execute_command(runtime, command)

        if command_type in {
            SimulationCommandType.STEP,
            SimulationCommandType.START,
            SimulationCommandType.RESUME,
        }:
            last_sequence = emitted[-1].sequence if emitted else runtime.world.next_sequence - 1
            snapshot = build_graph_snapshot_from_runtime(runtime, sequence=last_sequence)
            await PostgresGraphSnapshotRepository(uow.session).add(snapshot)

        run = await uow.runs.get_by_id(run_id)
        if run is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Run not found: {run_id}",
            )
        return RunCommandResponseV1(
            schema_version=RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
            run=run,
            events_emitted=len(emitted),
            idempotency=IdempotencyMetadataV1(
                schema_version=1,
                idempotency_key=idempotency_key,
                replayed=False,
            ),
        )

    async def get_bootstrap_payload(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> SnapshotBootstrapPayloadV1:
        run = await uow.runs.get_by_id(run_id)
        if run is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Run not found: {run_id}",
            )
        snapshot_repo = PostgresGraphSnapshotRepository(uow.session)
        snapshot = await snapshot_repo.get_latest_for_run(run_id)
        if snapshot is None:
            runtime = await self._get_or_restore_runtime(uow, run_id)
            snapshot = build_graph_snapshot_from_runtime(runtime, sequence=0, revision=0)
            await snapshot_repo.add(snapshot)

        events = await PostgresEventQueryRepository(uow.session).list_by_run(run_id)
        last_sequence = events[-1].sequence if events else 0

        return SnapshotBootstrapPayloadV1(
            schema_version=SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION,
            run=run,
            graph_snapshot=snapshot,
            last_applied_sequence=last_sequence,
        )

    async def _get_or_restore_runtime(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> SimulationRuntime:
        cached = self.runtime_cache.get(run_id)
        if cached is not None:
            return cached.runtime

        run = await uow.runs.get_by_id(run_id)
        if run is None:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Run not found: {run_id}",
            )
        package_dir = self.resolve_package_dir(
            package_path=None,
            scenario_version_id=run.scenario_version_id,
        )
        manifest = SimulationEngine.load_manifest(package_dir)
        runtime = SimulationEngine.create_runtime(
            manifest=manifest,
            seed=run.seed,
            scenario_version_id=run.scenario_version_id,
            run_id=run_id,
        )
        runtime.start()
        db_events = await PostgresEventQueryRepository(uow.session).list_by_run(run_id)
        target_count = len(db_events)
        guard = 0
        while len(runtime.events) < target_count and guard < target_count + 1000:
            runtime.step()
            guard += 1
        if len(runtime.events) < target_count:
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message="Failed to restore runtime from persisted events",
                details={
                    "expectedEvents": target_count,
                    "restoredEvents": len(runtime.events),
                },
            )

        self.runtime_cache[run_id] = RuntimeCacheEntry(runtime=runtime, package_dir=package_dir)
        return runtime
