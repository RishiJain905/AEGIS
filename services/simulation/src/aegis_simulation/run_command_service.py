"""Run command orchestration with runtime cache and graph projection."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aegis_contracts import (
    DomainEventEnvelopeV1,
    IdempotencyMetadataV1,
    RunCommandResponseV1,
    RunCreateRequestV1,
    RunV1,
    SimulationCheckpointV1,
    SimulationCommandType,
    SnapshotBootstrapPayloadV1,
)
from aegis_contracts.entities import RunLoadoutV1
from aegis_contracts.simulation import SimulationRunStatus
from aegis_contracts.versioning import (
    RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
    SNAPSHOT_BOOTSTRAP_SCHEMA_VERSION,
)
from aegis_model_provider.config import CLOUD_PROVIDER_KINDS, ProviderKind
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_scenario_sdk.contracts.manifest import ScenarioManifestV1
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
from aegis_simulation_domain.ids import derive_run_id
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

logger = logging.getLogger(__name__)

SCENARIO_PACKAGE_BY_VERSION: dict[str, str] = {
    # Runs created via an explicit scenarioPackagePath derive their version id from the
    # manifest version (1.0.0), so the bare id must stay restorable too.
    "scenario-version:1.0.0": "scenarios/operation-silent-relay",
    "scenario-version:1.0.0-silent-relay": "scenarios/operation-silent-relay",
    # The guided tutorial's version must be restorable too, or /bootstrap and resume
    # fail with "No scenario package mapping" once the run's runtime is no longer cached
    # (returning to the run, API restart, a different worker) — leaving the tutorial's
    # live view unable to load.
    "scenario-version:1.0.0-synthetic-training": "scenarios/synthetic-training",
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

# A checkpoint this build cannot read: either an engine-version bump or a checksum that no
# longer matches because the world-state snapshot model gained fields since it was written.
# Neither means the run is lost — the event stream rebuilds it — so both fall back to replay.
_UNREADABLE_CHECKPOINT_CODES: frozenset[SimulationErrorCode] = frozenset(
    {
        SimulationErrorCode.CHECKPOINT_INCOMPATIBLE,
        SimulationErrorCode.CHECKPOINT_CHECKSUM_INVALID,
    }
)

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


_MAX_COMMANDER_INTENT_CHARS = 280


def _normalize_commander_intent(intent: str | None) -> str | None:
    """Trim the operator's commander's intent; an empty/whitespace value persists as None.

    The contract already bounds length, but a skipped field may arrive as "" (empty
    field submitted); normalizing to None keeps "no intent" a single representation
    on the run and in the after-action review.
    """
    if intent is None:
        return None
    trimmed = intent.strip()[:_MAX_COMMANDER_INTENT_CHARS]
    return trimmed or None


async def _validate_loadout_provider(
    uow: PostgresUnitOfWork,
    loadout: RunLoadoutV1 | None,
    *,
    owner_user_id: str | None,
) -> None:
    """Refuse a launch whose pinned model provider could never produce a generation.

    The alternative to failing here is a run that starts, looks healthy, and then fails
    every agent turn with a provider error the operator has to decode — so a mistake the
    launch dialog can describe is caught at the launch, in the service layer where every
    caller of ``create_run`` (HTTP, CLI, tests) passes through it.

    Only two things are checked, because only two are knowable now. The provider id must
    name a provider this build has an adapter for; whether a *deployment* offers it
    depends on the egress allowlist, which the API resolves when it lists options and
    the executor resolves again at generation time. And a provider that spends a personal
    subscription must have a key already connected for the run's owner — existence only,
    read through the repository's own owner-scoped path. Nothing is decrypted here: run
    creation has no use for the plaintext, so it does not touch it.
    """
    provider_id = loadout.provider_id if loadout is not None else None
    if provider_id is None:
        return
    if provider_id not in {kind.value for kind in ProviderKind}:
        raise SimulationError(
            code=SimulationErrorCode.VALIDATION_FAILED,
            message=f"Unknown model provider: {provider_id}",
        )
    if provider_id not in {kind.value for kind in CLOUD_PROVIDER_KINDS}:
        return
    if owner_user_id is None:
        raise SimulationError(
            code=SimulationErrorCode.VALIDATION_FAILED,
            message=(
                f"Provider '{provider_id}' runs on an operator's own API key, so the run "
                "must be launched by an authenticated user."
            ),
        )
    if await uow.provider_credentials.get(owner_user_id, provider_id) is None:
        raise SimulationError(
            code=SimulationErrorCode.VALIDATION_FAILED,
            message=(
                f"No API key is connected for '{provider_id}'. Connect one in Configure "
                "Loadout before launching a run on it."
            ),
        )


def may_access_run(
    run: RunV1,
    *,
    requester_user_id: str | None,
    requester_is_admin: bool,
) -> bool:
    """Owner-or-admin gate for an existing run.

    Deliberately mirrors the API's ``has_run_access`` (ADR 0034 / AEGIS-OITB-008) rather
    than importing it — services must not depend on ``apps/api``. Admins always pass; a
    non-admin passes only when the run has an owner and it is them. A null-owner run
    (legacy or seeded demo data) is admin-only.
    """
    if requester_is_admin:
        return True
    return (
        requester_user_id is not None
        and run.owner_user_id is not None
        and run.owner_user_id == requester_user_id
    )


def may_reset_run(
    run: RunV1,
    *,
    requester_user_id: str | None,
    requester_is_admin: bool,
) -> bool:
    """Whether a ``restartExisting`` relaunch may destroy ``run``.

    Same owner-or-admin decision as :func:`may_access_run`: an ordinary operator can never
    destroy someone else's history. That matters more than it looks, because a run's seed
    is visible in the UI and the client chooses it — were this gate relaxed, knowing
    another operator's seed would be enough to delete their run.
    """
    return may_access_run(
        run,
        requester_user_id=requester_user_id,
        requester_is_admin=requester_is_admin,
    )


def scoped_create_idempotency_key(
    *,
    idempotency_key: str,
    owner_user_id: str | None,
    scenario_package_path: str,
) -> str:
    """Namespace a run-creation ``Idempotency-Key`` to the actor and scenario.

    Idempotency records live in one flat ``(scope, key)`` table shared by every simulation
    command, so a key the client picked is enough to replay whatever run it recorded —
    including a run belonging to someone else, which the caller then cannot even read.
    Folding the requester and the scenario into the stored key makes replay possible only
    for the identity that created the record. The client's original key is still what the
    response reports; only the storage key changes.

    Hashed rather than concatenated because ``idempotency_records.idempotency_key`` is
    bounded at 256 characters and user ids and package paths are both unbounded here.
    """
    digest = hashlib.sha256(
        f"{owner_user_id or ''}|{scenario_package_path}|{idempotency_key}".encode()
    ).hexdigest()
    return f"cmd-create-{digest[:40]}"


def _require_run_access(
    run: RunV1,
    *,
    requester_user_id: str | None,
    requester_is_admin: bool,
) -> None:
    """Raise unless the requester may read ``run``.

    ``UNAUTHORIZED`` is rendered by the runs router as HTTP 409 with the
    ``RUN_OWNED_BY_ANOTHER_USER`` code — a conflict rather than a forbidden, because the
    caller is allowed to create runs; what they cannot have is *this* run. Pinned-seed
    scenarios derive one run id per (seed, scenario version) for everybody, so whoever
    launches one first owns it. (The guided tutorial no longer hits this: the web client
    derives a stable per-operator seed, so each operator's training run is their own — but
    the guard stays for any scenario that pins a shared seed.)

    The refused run's id is deliberately *not* in the error. It would be harmless as
    disclosure — the caller supplied the seed the id is derived from — but this is the
    exact failure that produced BUG-001, where a launch handed back a run id the client
    then navigated to and could not read. An id the caller must not follow has no business
    in the response; the server log and trace carry it for support.
    """
    if may_access_run(
        run,
        requester_user_id=requester_user_id,
        requester_is_admin=requester_is_admin,
    ):
        return
    logger.info(
        "Refusing launch: run %s is owned by %s, requested by %s",
        run.id,
        run.owner_user_id,
        requester_user_id,
    )
    raise SimulationError(
        code=SimulationErrorCode.UNAUTHORIZED,
        message=(
            "This run already exists and belongs to another operator. "
            "Ask them or an administrator to restart it."
        ),
    )


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
    # In-process observers notified when a run's durable state is destroyed by a
    # reset-and-replay relaunch. The reset recreates the run under the *same* derived id,
    # so anything else keyed by run id (the tick engine's detection cursor, threat-tempo
    # stamps, failure counter) must be dropped or the fresh run inherits the old one's
    # bookkeeping. Callbacks are synchronous and must not raise.
    _reset_listeners: list[Callable[[str], None]] = field(default_factory=list)

    def add_run_reset_listener(self, listener: Callable[[str], None]) -> None:
        """Register a callback invoked with a run id just before that run is destroyed."""
        if listener not in self._reset_listeners:
            self._reset_listeners.append(listener)

    def remove_run_reset_listener(self, listener: Callable[[str], None]) -> None:
        """Deregister a reset listener; a listener that was never added is ignored."""
        with contextlib.suppress(ValueError):
            self._reset_listeners.remove(listener)

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

        Used after a failed command or a rolled-back transaction, either of which may have
        left the in-memory runtime mutated but unpersisted. Restore replays the checkpoint
        plus post-checkpoint sim events, so eviction is always safe and never loses
        persisted state.

        It is *not* a way to reconcile an executed action applied to some other runtime:
        every command that mutates a run's world — lifecycle steps and authorized action
        execution alike — runs on this cache's runtime under :meth:`lock_for`, because a
        checkpoint written after an unobserved effect event permanently strands that
        effect (restore only replays events at or after the checkpoint's sequence).
        """
        self.runtime_cache.pop(run_id, None)

    async def persist_executed_action_state(
        self,
        uow: PostgresUnitOfWork,
        runtime: SimulationRuntime,
        *,
        sequence: int,
    ) -> None:
        """Make an authorized action's world mutation durable in its own transaction.

        Lifecycle commands checkpoint and snapshot on their way out; an authorized action
        executes through :class:`SimulationApplicationService` directly and so has to do
        the same explicitly. Without it the mutation lives only in the cached runtime until
        the next tick — which never comes for a paused run — and the operator-facing graph
        keeps serving a snapshot that does not know the asset was contained.

        ``sequence`` is the last sequence the execution itself claimed, so the snapshot can
        never collide with a stepping command's on ``uq_graph_snapshots_run_sequence``.
        """
        snapshot = build_graph_snapshot_from_runtime(runtime, sequence=sequence)
        await PostgresGraphSnapshotRepository(uow.session).add(snapshot)
        await self._persist_runtime_checkpoint(uow, runtime)

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
        requester_is_admin: bool = False,
    ) -> RunCommandResponseV1:
        scoped_key = (
            scoped_create_idempotency_key(
                idempotency_key=idempotency_key,
                owner_user_id=owner_user_id,
                scenario_package_path=request.scenario_package_path,
            )
            if idempotency_key is not None
            else None
        )
        if scoped_key is not None:
            existing = await uow.idempotency.get(
                scope=SIMULATION_COMMAND_SCOPE,
                idempotency_key=scoped_key,
            )
            if existing is not None:
                run = await uow.runs.get_by_id(existing.response_ref or "")
                if run is None:
                    raise SimulationError(
                        code=SimulationErrorCode.VALIDATION_FAILED,
                        message="Idempotency record references missing run",
                    )
                # The scoped key already binds the record to this actor. Re-checking access
                # costs one predicate and closes the door on records written before that
                # scoping existed, which are keyed by the raw client key.
                _require_run_access(
                    run,
                    requester_user_id=owner_user_id,
                    requester_is_admin=requester_is_admin,
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

        # After the idempotency replay (a repeat of an already-created run is answered
        # from the record, not re-validated) and before any work: a launch on a provider
        # that cannot generate should cost nothing.
        await _validate_loadout_provider(uow, request.loadout, owner_user_id=owner_user_id)

        package_dir = (self.workspace_root / request.scenario_package_path).resolve()
        if not package_dir.exists():
            raise SimulationError(
                code=SimulationErrorCode.VALIDATION_FAILED,
                message=f"Scenario package not found: {request.scenario_package_path}",
            )

        # Deterministic run ids: the run id is derived from (seed, scenario_version_id), so a
        # pinned-seed scenario (the guided tutorial launches at seed 1000) resolves to the same
        # run id on every launch. Re-launching would otherwise collide on the runs primary key
        # and 500. Detect the existing run and either return it (resume the deterministic run)
        # or, when the caller asked to restart, destroy and recreate it. Seedless scenarios
        # draw a fresh random seed and never take this path.
        if request.seed is not None and request.run_id is None:
            manifest_for_guard = SimulationEngine.load_manifest(package_dir)
            derived_run_id = derive_run_id(
                run_seed=request.seed,
                scenario_version_id=f"scenario-version:{manifest_for_guard.metadata.version}",
            )
            existing_run = await uow.runs.get_by_id(derived_run_id)
            if existing_run is not None:
                # Resolving to a run the caller cannot read is worse than failing: the
                # launch answered 200 with someone else's run id, the client navigated to
                # it, and every follow-up request 403'd into an "unable to load workspace"
                # dead end. Refuse here instead, with a code the launch surface can explain.
                _require_run_access(
                    existing_run,
                    requester_user_id=owner_user_id,
                    requester_is_admin=requester_is_admin,
                )
                may_restart = request.restart_existing and may_reset_run(
                    existing_run,
                    requester_user_id=owner_user_id,
                    requester_is_admin=requester_is_admin,
                )
                if not may_restart:
                    return RunCommandResponseV1(
                        schema_version=RUN_COMMAND_RESPONSE_SCHEMA_VERSION,
                        run=existing_run,
                        events_emitted=0,
                        idempotency=(
                            IdempotencyMetadataV1(
                                schema_version=1,
                                idempotency_key=idempotency_key,
                                replayed=True,
                            )
                            if idempotency_key
                            else None
                        ),
                    )
                # Reset-and-replay. Minting a fresh run id is not an option: event, trace and
                # checkpoint ids are derived from (run_seed, sequence) rather than run id, so
                # two live runs on the same pinned seed would collide on the global
                # ``domain_events.event_id`` primary key. Deleting the run instead frees those
                # ids, and the run is then recreated under the same derived id below.
                #
                # The per-run lock is held across the delete AND the recreation so the tick
                # engine — the single writer for run state, which serializes on the same lock
                # — can neither be mid-tick on the run we are destroying nor repopulate the
                # runtime cache we just evicted. Inside it the delete additionally takes the
                # run's Postgres advisory lock for the rest of this transaction, blocking any
                # out-of-process writer until the reset commits as one unit.
                async with self.lock_for(derived_run_id):
                    await self._reset_run(uow, derived_run_id)
                    return await self._create_and_start_run(
                        uow,
                        package_dir,
                        request=request,
                        seed=request.seed,
                        idempotency_key=idempotency_key,
                        command_key=scoped_key,
                        owner_user_id=owner_user_id,
                    )

        # Server-side RNG: an omitted seed draws a fresh cryptographically random seed
        # that is then persisted like any other, so the run remains fully deterministic
        # for its (now concrete) seed. A supplied seed is used verbatim.
        seed = request.seed if request.seed is not None else draw_random_seed()
        return await self._create_and_start_run(
            uow,
            package_dir,
            request=request,
            seed=seed,
            idempotency_key=idempotency_key,
            command_key=scoped_key,
            owner_user_id=owner_user_id,
        )

    async def _reset_run(self, uow: PostgresUnitOfWork, run_id: str) -> None:
        """Destroy a run's durable and in-memory state so its id can be reused.

        Migration-free: every run-scoped table declares ``ON DELETE CASCADE`` on its
        ``run_id`` foreign key, so deleting the ``runs`` row takes the events (and their
        outbox rows), alerts, incidents, evidence, graph snapshots, checkpoints, agent
        sessions, executed actions, scores and reports with it in one statement, inside the
        caller's transaction. In-process state keyed by the run id is dropped first, because
        the recreated run reuses that id and must not inherit it.

        ``idempotency_records`` is the one exception — a generic command-dedup table with no
        foreign key — so the destroyed run's simulation-command records are removed
        explicitly. Without that, a derived command id (the START fallback
        ``cmd-start-{seed}-{run_id}``, identical across a reset) would read as a duplicate
        and leave the recreated run persisted but never started.

        Called with the run's per-run lock held (see :meth:`create_run`).
        """
        self.evict(run_id)
        self.clear_threat_tempo(run_id)
        for listener in list(self._reset_listeners):
            listener(run_id)
        deleted = await uow.runs.delete(run_id)
        await uow.idempotency.delete_by_response_ref(
            scope=SIMULATION_COMMAND_SCOPE,
            response_ref=run_id,
        )
        if not deleted:
            # Another writer removed the run between the guard read and here. The id is free
            # either way, so creation can proceed; log it rather than failing the relaunch.
            logger.info("Run %s was already gone when the reset ran", run_id)

    async def _create_and_start_run(
        self,
        uow: PostgresUnitOfWork,
        package_dir: Path,
        *,
        request: RunCreateRequestV1,
        seed: int,
        idempotency_key: str | None,
        command_key: str | None,
        owner_user_id: str | None,
    ) -> RunCommandResponseV1:
        """Persist a new run at ``seed``, START it, and project its initial graph snapshot.

        ``idempotency_key`` is what the client sent and what the response reports;
        ``command_key`` is the actor-scoped key the idempotency record is stored under (see
        :func:`scoped_create_idempotency_key`). They are deliberately different values.
        """
        service = SimulationApplicationService(uow)
        runtime, manifest = await service.create_run_from_package(
            package_dir,
            seed=seed,
            run_id=request.run_id,
            owner_user_id=owner_user_id,
            loadout=request.loadout,
            commander_intent=_normalize_commander_intent(request.commander_intent),
        )
        _ = manifest

        command = service.build_command(
            command_id=command_key or f"cmd-start-{seed}-{runtime.run_id}",
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

        # Only an emitting command gets a snapshot, and it is stamped with the sequence it
        # just claimed. A command that emitted nothing (a STEP whose scheduled work was a
        # gated branch, or a kill-chain advance the defender already disrupted) has not
        # advanced the event stream, so there is no new sequence to project onto: stamping
        # such a snapshot with ``next_sequence - 1`` would re-use the sequence the previous
        # emitting command already snapshotted and collide on
        # ``uq_graph_snapshots_run_sequence``, failing the whole tick.
        if emitted and command_type in {
            SimulationCommandType.STEP,
            SimulationCommandType.START,
            SimulationCommandType.RESUME,
        }:
            snapshot = build_graph_snapshot_from_runtime(runtime, sequence=emitted[-1].sequence)
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

        # The run's head sequence, read straight off the sequence counter. Deriving it from
        # ``list_by_run(...)[-1]`` capped it at that query's 1000-row default: past a
        # thousand events the bootstrap kept reporting a stale head, every live frame then
        # arrived beyond ``lastAppliedSequence + 1``, and the client gap-detected into a
        # resync that returned the same stale head — a permanent resync loop with a frozen
        # graph. Silent Relay reaches ~975 events at its horizon, so runs were completing
        # just under the cliff.
        last_sequence = max(await uow.events.next_sequence(run_id) - 1, 0)

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
        if checkpoint is not None and self._checkpoint_is_usable(runtime, checkpoint):
            # Restore authoritative status/RNG/clock/world/queue from the checkpoint, then
            # re-apply only the events that were appended after it (e.g. an approved
            # containment executed by the approvals service, which does not checkpoint).
            pending = [
                event for event in sim_events if event.sequence >= runtime.world.next_sequence
            ]
            self._replay_events(runtime, pending)
        else:
            # No checkpoint (legacy run created before checkpointing existed) or one this
            # build can no longer read: deterministically replay the full recorded operation
            # stream from a fresh runtime. Reproduces lifecycle transitions and
            # executed-action effects rather than advancing by event count.
            self._replay_events(runtime, sim_events)

        # Keep sequence monotonic across mixed sim + approval/agent event streams.
        await self._sync_next_sequence(uow, runtime)

        self.runtime_cache[run_id] = RuntimeCacheEntry(runtime=runtime, package_dir=package_dir)
        return runtime

    @staticmethod
    def _checkpoint_is_usable(
        runtime: SimulationRuntime, checkpoint: SimulationCheckpointV1
    ) -> bool:
        """Restore ``checkpoint`` into ``runtime``; return False if this build cannot read it.

        The checksum is taken over the *whole* ``WorldStateSnapshotV1`` dump, so any additive
        field on that model (Phase 2 added campaign progression, run outcome and peak
        disruption cost) makes every checkpoint written by an earlier build recompute to a
        different digest and fail validation. That is not corruption: the event stream is the
        source of truth and can rebuild the runtime exactly, so an unreadable checkpoint is
        downgraded to a full deterministic replay instead of wedging the run forever. The next
        command writes a checkpoint in the current shape, so a run self-heals after one replay.

        Both rejections are raised before ``restore`` mutates anything, so the caller's runtime
        is still pristine when this returns False.
        """
        try:
            runtime.restore(checkpoint)
        except SimulationError as exc:
            if exc.code not in _UNREADABLE_CHECKPOINT_CODES:
                raise
            logger.warning(
                "Checkpoint %s for run %s is unreadable by this build (%s); rebuilding the "
                "runtime by replaying the event stream instead",
                checkpoint.id,
                runtime.run_id,
                exc.code.value,
            )
            return False
        return True

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
                # Same composition the live handler applies, so a rebuilt runtime and a
                # live one hold identical postures and controls for the same stream.
                asset.apply_status(status)
        elif event.type == "sim.branch.selected":
            group = str(event.payload.get("branchGroup", ""))
            branch_id = str(event.payload.get("branchId", ""))
            if group:
                runtime.world.selected_branches[group] = branch_id
        runtime.world.next_sequence = max(runtime.world.next_sequence, event.sequence + 1)
