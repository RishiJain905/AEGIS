"""Run command orchestration with runtime cache and graph projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aegis_contracts import (
    DomainEventEnvelopeV1,
    IdempotencyMetadataV1,
    RunCommandResponseV1,
    RunCreateRequestV1,
    SimulationCommandType,
    SnapshotBootstrapPayloadV1,
)
from aegis_contracts.simulation import SimulationRunStatus
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

# Events produced by the deterministic simulation engine (as opposed to approval/agent
# domain events that merely share the run's sequence stream). Only these drive runtime
# reconstruction during restart recovery.
_SIM_EVENT_PREFIXES: tuple[str, ...] = ("sim.", "telemetry.")

# Lifecycle events map back to the runtime transition that produced them, so recovery can
# re-apply the exact authoritative status (paused/stopped/running) instead of guessing.
_LIFECYCLE_REPLAY: dict[str, str] = {
    "sim.run.started": "start",
    "sim.run.paused": "pause",
    "sim.run.resumed": "resume",
    "sim.run.stopped": "stop",
}

# World-mutating effect events an EXECUTE command can emit. These carry executed-action
# state (e.g. an approved containment isolating an asset) that stepping never reproduces.
_EXECUTE_EFFECT_TYPES: frozenset[str] = frozenset(
    {"sim.asset.status_changed", "sim.branch.selected"}
)


def _is_sim_event(event: DomainEventEnvelopeV1) -> bool:
    return event.type.startswith(_SIM_EVENT_PREFIXES)


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
        owner_user_id: str | None = None,
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
            owner_user_id=owner_user_id,
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
        await self._persist_runtime_checkpoint(uow, runtime)

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

        await self._persist_runtime_checkpoint(uow, runtime)

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

    async def _persist_runtime_checkpoint(
        self, uow: PostgresUnitOfWork, runtime: SimulationRuntime
    ) -> None:
        """Persist a non-emitting runtime checkpoint so a restart can restore faithfully.

        Captured after each command inside the command's own transaction. The checkpoint
        records lifecycle status + RNG streams + clock + world without touching the
        authoritative (determinism-golden) event stream. A no-op command that emits no
        events leaves ``next_sequence`` unchanged and reuses an existing checkpoint id;
        we skip the duplicate rather than violate the ``(run_id, sequence)`` uniqueness.
        """
        checkpoint = runtime.snapshot_checkpoint()
        existing = await uow.checkpoints.get_by_id(checkpoint.id)
        if existing is None:
            await uow.checkpoints.add(checkpoint)

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

        db_events = await PostgresEventQueryRepository(uow.session).list_by_run(run_id)
        sim_events = [event for event in db_events if _is_sim_event(event)]

        checkpoint = await uow.checkpoints.get_latest_for_run(run_id)
        if checkpoint is not None:
            # Restore authoritative status/RNG/clock/world/queue from the checkpoint, then
            # re-apply only the events that were appended after it (e.g. an approved
            # containment executed by the approvals service, which does not checkpoint).
            runtime.restore(checkpoint)
            pending = [
                event for event in sim_events if event.sequence >= runtime.world.next_sequence
            ]
            self._replay_events(runtime, pending)
        else:
            # Legacy run created before checkpointing existed: deterministically replay the
            # full recorded operation stream from a fresh runtime. Reproduces lifecycle
            # transitions and executed-action effects rather than advancing by event count.
            self._replay_events(runtime, sim_events)

        # Keep sequence monotonic across mixed sim + approval/agent event streams.
        next_persisted = await uow.events.next_sequence(run_id)
        if next_persisted > runtime.world.next_sequence:
            runtime.world.next_sequence = next_persisted

        self.runtime_cache[run_id] = RuntimeCacheEntry(runtime=runtime, package_dir=package_dir)
        return runtime

    def _replay_events(
        self, runtime: SimulationRuntime, events: list[DomainEventEnvelopeV1]
    ) -> None:
        """Deterministically reconstruct runtime state from persisted sim events.

        ``events`` are simulation-produced events (``sim.*`` / ``telemetry.*``) in ascending
        sequence order, all at or after the runtime's current position. Lifecycle
        transitions and out-of-band executed-action effects are re-applied directly; every
        other event is reproduced by stepping the deterministic engine. This never mutates
        authoritative (persisted) state — it only rebuilds the in-memory runtime.
        """
        index = 0
        total = len(events)
        while index < total:
            event = events[index]
            transition = _LIFECYCLE_REPLAY.get(event.type)
            if transition is not None:
                getattr(runtime, transition)()
                index += 1
                continue
            if event.type == "sim.checkpoint.created":
                # Checkpoint markers do not change world/RNG/queue state.
                runtime.world.next_sequence = max(
                    runtime.world.next_sequence, event.sequence + 1
                )
                index += 1
                continue
            block_end = self._execute_block_end(events, index)
            if block_end is not None:
                for effect in events[index:block_end]:
                    self._apply_executed_effect(runtime, effect)
                index = block_end
                continue
            if runtime.world.status == SimulationRunStatus.RUNNING:
                produced = runtime.step()
                if produced:
                    index += len(produced)
                    continue
            # Could not reproduce by stepping (queue exhausted or not running); apply the
            # persisted event's effect directly so status/world stay faithful.
            self._apply_executed_effect(runtime, event)
            index += 1

    @staticmethod
    def _execute_block_end(events: list[DomainEventEnvelopeV1], start: int) -> int | None:
        """Return the exclusive end of an EXECUTE block starting at ``start``, else None.

        An EXECUTE command appends its effect event(s) immediately followed by a single
        ``sim.command.executed`` at the same ``sim_time``; stepping never produces that
        terminator, so this contiguous same-time run uniquely identifies executed-action
        output that must be applied out of band.
        """
        base_time = events[start].sim_time
        cursor = start
        total = len(events)
        while cursor < total and events[cursor].sim_time == base_time:
            etype = events[cursor].type
            if etype == "sim.command.executed":
                return cursor + 1
            if etype in _EXECUTE_EFFECT_TYPES:
                cursor += 1
                continue
            break
        return None

    @staticmethod
    def _apply_executed_effect(
        runtime: SimulationRuntime, event: DomainEventEnvelopeV1
    ) -> None:
        """Apply a persisted sim effect event's world mutation without consuming RNG/queue.

        Executed-action effects (``effect.*`` plugins) are deterministic and touch neither
        the RNG streams, the event queue, nor the clock, so replaying them as direct world
        writes keeps the stepping timeline exact while restoring executed-action state.
        """
        if event.type == "sim.asset.status_changed":
            asset_id = str(event.payload.get("assetId", ""))
            status = str(event.payload.get("status", ""))
            asset = runtime.world.assets.get(asset_id)
            if asset is not None and status:
                asset.status = status
                asset.revision += 1
        elif event.type == "sim.branch.selected":
            group = str(event.payload.get("branchGroup", ""))
            branch_id = str(event.payload.get("branchId", ""))
            if group:
                runtime.world.selected_branches[group] = branch_id
        runtime.world.next_sequence = max(runtime.world.next_sequence, event.sequence + 1)
