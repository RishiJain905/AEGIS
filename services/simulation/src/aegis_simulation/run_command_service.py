"""Run command orchestration with runtime cache and graph projection."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
from aegis_simulation_domain.runtime import SimulationRuntime
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_simulation.application import SIMULATION_COMMAND_SCOPE, SimulationApplicationService
from aegis_simulation.disclosure_resolver import (
    ACTIVE_RUN_STATUSES,
    RunDisclosure,
    resolve_run_disclosure,
)
from aegis_simulation.graph_projection import (
    build_graph_snapshot_from_runtime,
    redact_snapshot_for_disclosure,
)

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


# Cryptographically random seed range: 1..2^31-1. Kept within a signed 32-bit range so
# the value round-trips cleanly through the `runs.seed` BIGINT column and every downstream
# consumer (RNG streams, id derivation) that treats the seed as a positive integer.
_MAX_RANDOM_SEED = 2**31 - 1


def draw_random_seed() -> int:
    """Draw a cryptographically random simulation seed in [1, 2^31-1]."""
    return secrets.randbelow(_MAX_RANDOM_SEED) + 1


@dataclass
class RunCommandService:
    workspace_root: Path
    runtime_cache: dict[str, RuntimeCacheEntry] = field(default_factory=dict)
    # Per-run asyncio locks serialize every writer that touches a run's cached runtime:
    # the tick engine, the manual lifecycle routes (step/pause/resume/stop), and approved
    # action execution. A single cached ``SimulationRuntime`` is not safe under interleaved
    # awaits, so all of them acquire ``lock_for(run_id)`` before mutating it.
    _run_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    # Fog of war: latest per-run threat-tempo scalar (0..1), refreshed by the tick engine
    # each post-step and read by the operator-facing bootstrap payload. In-process only
    # (single API writer); never persisted to the authoritative event stream so it cannot
    # perturb determinism/golden replays. Absent until the first tick computes it.
    _threat_tempo: dict[str, float] = field(default_factory=dict)
    # Manifests are immutable per scenario version; cache to avoid re-reading the package
    # from disk on every disclosure resolution.
    _manifest_cache: dict[str, ScenarioManifestV1] = field(default_factory=dict)

    def set_threat_tempo(self, run_id: str, value: float) -> None:
        self._threat_tempo[run_id] = max(0.0, min(1.0, value))

    def get_threat_tempo(self, run_id: str) -> float | None:
        return self._threat_tempo.get(run_id)

    def clear_threat_tempo(self, run_id: str) -> None:
        self._threat_tempo.pop(run_id, None)

    def manifest_for_scenario_version(self, scenario_version_id: str) -> ScenarioManifestV1:
        """Public manifest accessor (cached) for operator-facing fog resolution."""
        return self._manifest_for_run(scenario_version_id)

    def _manifest_for_run(self, scenario_version_id: str) -> ScenarioManifestV1:
        manifest = self._manifest_cache.get(scenario_version_id)
        if manifest is None:
            package_dir = self.resolve_package_dir(
                package_path=None,
                scenario_version_id=scenario_version_id,
            )
            manifest = SimulationEngine.load_manifest(package_dir)
            self._manifest_cache[scenario_version_id] = manifest
        return manifest

    async def resolve_disclosure(
        self,
        session: AsyncSession,
        run: Any,
    ) -> RunDisclosure:
        """Resolve current fog-of-war disclosure for a run's operator-facing projection.

        Prefers reveal state from a live cached runtime when present (no checkpoint read);
        alerted assets always come from persisted rows.
        """
        manifest = self._manifest_for_run(run.scenario_version_id)
        revealed: frozenset[str] | None = None
        cached = self.runtime_cache.get(run.id)
        if cached is not None:
            revealed = frozenset(
                condition.condition_id
                for condition in cached.runtime.world.hidden_conditions.values()
                if condition.revealed
            )
        return await resolve_run_disclosure(
            session,
            run_id=run.id,
            manifest=manifest,
            revealed_condition_ids=revealed,
        )

    def lock_for(self, run_id: str) -> asyncio.Lock:
        """Return the per-run serialization lock, creating it on first use.

        Lazily constructed inside the running event loop (this service is instantiated at
        import time, before any loop exists).
        """
        lock = self._run_locks.get(run_id)
        if lock is None:
            lock = asyncio.Lock()
            self._run_locks[run_id] = lock
        return lock

    def evict(self, run_id: str) -> None:
        """Drop a run's cached runtime so the next access re-restores from durable state.

        Used after a failed command (which may have left the in-memory runtime mutated but
        unpersisted) and by the tick engine when an out-of-band writer — e.g. an approved
        action executed on an isolated runtime — has appended effect events the cached
        runtime has not observed. Restore replays the checkpoint plus post-checkpoint sim
        events, so eviction is always safe and never loses persisted state.
        """
        self.runtime_cache.pop(run_id, None)

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

        # Server-side RNG: an omitted seed draws a fresh cryptographically random seed
        # that is then persisted like any other, so the run remains fully deterministic
        # for its (now concrete) seed. A supplied seed is used verbatim.
        seed = request.seed if request.seed is not None else draw_random_seed()

        service = SimulationApplicationService(uow)
        runtime, manifest = await service.create_run_from_package(
            package_dir,
            seed=seed,
            run_id=request.run_id,
            owner_user_id=owner_user_id,
            loadout=request.loadout,
        )
        _ = manifest

        command = service.build_command(
            command_id=idempotency_key or f"cmd-start-{seed}-{runtime.run_id}",
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

        # Fog of war: while the run is active, the operator sees only disclosed truth. Once
        # terminal (stopped/completed), the graph switches to full ground truth for debrief.
        threat_tempo: float | None = None
        if run.status in ACTIVE_RUN_STATUSES:
            disclosure = await self.resolve_disclosure(uow.session, run)
            snapshot = redact_snapshot_for_disclosure(snapshot, disclosure)
            threat_tempo = self.get_threat_tempo(run_id)

        return SnapshotBootstrapPayloadV1(
            schema_version=SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION,
            run=run,
            graph_snapshot=snapshot,
            last_applied_sequence=last_sequence,
            threat_tempo=threat_tempo,
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
            # Out-of-band writers (detection alerts, approvals, reports) append events to
            # this run's sequence stream without touching the cached runtime. Re-sync the
            # next sequence so the next STEP never collides with an already-persisted event.
            await self._sync_next_sequence(uow, cached.runtime)
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
        await self._sync_next_sequence(uow, runtime)

        self.runtime_cache[run_id] = RuntimeCacheEntry(runtime=runtime, package_dir=package_dir)
        return runtime

    @staticmethod
    async def _sync_next_sequence(
        uow: PostgresUnitOfWork, runtime: SimulationRuntime
    ) -> None:
        """Advance the runtime's next sequence past any persisted out-of-band events.

        Alerts, approvals, and report events append to the run's ``(run_id, sequence)``
        stream without going through the cached runtime; skipping the runtime forward keeps
        the next stepped event's sequence unique. The determinism-golden *normalized* hash
        is unaffected — it is computed over sim event content, not raw sequence numbers.
        """
        next_persisted = await uow.events.next_sequence(runtime.run_id)
        if next_persisted > runtime.world.next_sequence:
            runtime.world.next_sequence = next_persisted

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
