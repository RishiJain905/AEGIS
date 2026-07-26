"""Regression tests for the two faults that wedged live runs on the shared tick loop.

Both made a run fail *identically* on every subsequent tick, so neither self-healed:

1. A command that emitted no events still wrote a graph snapshot, stamped with
   ``next_sequence - 1`` — the sequence the previous emitting command had already
   snapshotted — violating ``uq_graph_snapshots_run_sequence`` and failing the tick.
2. A checkpoint written before ``WorldStateSnapshotV1`` gained fields recomputes to a
   different checksum, so ``restore`` rejected it and the runtime could never be rebuilt.

Fully offline: the unit of work and the snapshot repository are faked, and the runtime is
the real deterministic engine on the minimal fixture scenario.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aegis_simulation.run_command_service as rcs
import pytest
from aegis_contracts import RunV1, SimulationCommandType
from aegis_contracts.simulation import SimulationRunStatus
from aegis_contracts.versioning import RUN_SCHEMA_VERSION
from aegis_simulation.run_command_service import RunCommandService, RuntimeCacheEntry
from aegis_simulation_domain import SimulationEngine, SimulationError, SimulationErrorCode
from aegis_simulation_domain.runtime import SimulationRuntime

FIXTURE = Path("scenarios/_fixtures/valid-minimal")
SCENARIO_VERSION_ID = "scenario-version:1.0.0-fixture"
SEED = 4242
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69TEST0"


def _new_runtime() -> SimulationRuntime:
    manifest = SimulationEngine.load_manifest(FIXTURE)
    return SimulationEngine.create_runtime(
        manifest=manifest,
        seed=SEED,
        scenario_version_id=SCENARIO_VERSION_ID,
        run_id=RUN_ID,
    )


class _FakeUow:
    """Minimal in-memory stand-in for the pieces ``execute_lifecycle_command`` touches."""

    def __init__(self, run_id: str) -> None:
        self.appended: list[object] = []
        self._checkpoints: dict[str, object] = {}
        self._idempotency: dict[tuple[str, str], object] = {}
        self._run = RunV1(
            schemaVersion=RUN_SCHEMA_VERSION,
            id=run_id,
            scenarioVersionId=SCENARIO_VERSION_ID,
            seed=SEED,
            status="running",
            startedAt=datetime(2026, 1, 1, tzinfo=UTC),
            simTime=datetime(2026, 1, 1, tzinfo=UTC),
            revision=0,
        )
        self.session = object()
        outer = self

        class _Idempotency:
            async def get(self, *, scope: str, idempotency_key: str) -> object | None:
                return outer._idempotency.get((scope, idempotency_key))

            async def add(self, record: object) -> object:
                key = (record.scope, record.idempotency_key)  # type: ignore[attr-defined]
                outer._idempotency[key] = record
                return record

        class _Runs:
            async def get_by_id(self, run_id: str) -> object:
                return outer._run

            async def update_with_revision(
                self, run: RunV1, *, expected_revision: int
            ) -> RunV1:
                outer._run = run
                return run

        class _Events:
            async def next_sequence(self, run_id: str) -> int:
                return max((event.sequence for event in outer.appended), default=-1) + 1

        class _Checkpoints:
            async def get_by_id(self, checkpoint_id: str) -> object | None:
                return outer._checkpoints.get(checkpoint_id)

            async def add(self, checkpoint: object) -> object:
                outer._checkpoints[checkpoint.id] = checkpoint  # type: ignore[attr-defined]
                return checkpoint

        self.idempotency = _Idempotency()
        self.runs = _Runs()
        self.events = _Events()
        self.checkpoints = _Checkpoints()

    async def append_event(self, event: object) -> object:
        self.appended.append(event)
        return event


class _RecordingSnapshotRepo:
    """Records every snapshot written, and rejects a repeated (run_id, sequence).

    The rejection mirrors ``uq_graph_snapshots_run_sequence`` so a test that writes a
    colliding snapshot fails here the way production failed against PostgreSQL.
    """

    written: list[tuple[str, int]] = []

    def __init__(self, session: object) -> None:
        self._session = session

    async def add(self, snapshot: object) -> object:
        key = (snapshot.run_id, snapshot.sequence)  # type: ignore[attr-defined]
        if key in type(self).written:
            raise AssertionError(f"duplicate graph snapshot for {key}")
        type(self).written.append(key)
        return snapshot


@pytest.fixture
def snapshot_writes(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    _RecordingSnapshotRepo.written = []
    monkeypatch.setattr(rcs, "PostgresGraphSnapshotRepository", _RecordingSnapshotRepo)
    return _RecordingSnapshotRepo.written


async def _step(service: RunCommandService, uow: _FakeUow, key: str) -> int:
    response = await service.execute_lifecycle_command(
        uow,  # type: ignore[arg-type]
        RUN_ID,
        SimulationCommandType.STEP,
        idempotency_key=key,
    )
    return response.events_emitted


@pytest.mark.asyncio
async def test_step_emitting_no_events_writes_no_snapshot(
    snapshot_writes: list[tuple[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wedge itself: an empty STEP must not re-stamp the previous step's sequence."""
    service = RunCommandService(workspace_root=Path("."))
    runtime = _new_runtime()
    runtime.start()
    service.runtime_cache[RUN_ID] = RuntimeCacheEntry(runtime=runtime, package_dir=FIXTURE)
    uow = _FakeUow(RUN_ID)

    # One real emitting step first, so a colliding re-stamp has something to collide with.
    assert await _step(service, uow, "emitting-step") > 0
    assert snapshot_writes, "an emitting step must snapshot"
    snapshots_before = list(snapshot_writes)

    # Force the next steps to emit nothing at the service seam. (The engine reaches this
    # state live whenever a kill-chain advance is superseded or disrupted, or scheduled
    # work sits behind an unselected branch gate — but the current engine also perpetually
    # reschedules, so the queue never drains naturally in a bounded test.)
    async def _emit_nothing(self: object, _runtime: object, _command: object) -> list[object]:
        return []

    monkeypatch.setattr(
        rcs.SimulationApplicationService, "execute_command", _emit_nothing
    )

    assert await _step(service, uow, "empty-step") == 0
    assert snapshot_writes == snapshots_before

    # And the tick after it must still not collide (this is what looped forever).
    assert await _step(service, uow, "empty-step-again") == 0
    assert snapshot_writes == snapshots_before


@pytest.mark.asyncio
async def test_emitting_step_snapshots_at_the_sequence_it_claimed(
    snapshot_writes: list[tuple[str, int]],
) -> None:
    service = RunCommandService(workspace_root=Path("."))
    runtime = _new_runtime()
    runtime.start()
    service.runtime_cache[RUN_ID] = RuntimeCacheEntry(runtime=runtime, package_dir=FIXTURE)
    uow = _FakeUow(RUN_ID)

    assert await _step(service, uow, "step-1") > 0

    assert snapshot_writes == [(RUN_ID, uow.appended[-1].sequence)]  # type: ignore[attr-defined]


def test_checkpoint_from_an_older_world_state_shape_falls_back_to_replay() -> None:
    """A checksum that no longer matches downgrades to replay instead of raising."""
    service = RunCommandService(workspace_root=Path("."))
    reference = _new_runtime()
    reference.start()
    reference.run_steps(3)
    checkpoint = reference.snapshot_checkpoint()

    # Exactly what a pre-Phase-2 checkpoint looks like today: a digest taken over a
    # world-state payload that was missing the fields the model has since grown.
    drifted = checkpoint.model_copy(update={"checksum": "sha256:" + "0" * 64})

    pristine = _new_runtime().world.next_sequence
    target = _new_runtime()
    assert service._checkpoint_is_usable(target, drifted) is False
    # Rejected before ``restore`` touched anything, so the caller can still replay into it.
    assert target.world.next_sequence == pristine
    assert target.world.status is SimulationRunStatus.CREATED

    assert service._checkpoint_is_usable(target, checkpoint) is True
    assert target.world.next_sequence == checkpoint.world_state.next_sequence


def test_unrelated_checkpoint_errors_still_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only unreadable-checkpoint codes downgrade; real failures must not be swallowed."""
    service = RunCommandService(workspace_root=Path("."))
    runtime = _new_runtime()
    runtime.start()
    checkpoint = runtime.snapshot_checkpoint()

    def _boom(_checkpoint: object) -> None:
        raise SimulationError(
            code=SimulationErrorCode.VALIDATION_FAILED,
            message="something genuinely wrong",
        )

    monkeypatch.setattr(runtime, "restore", _boom)

    with pytest.raises(SimulationError) as excinfo:
        service._checkpoint_is_usable(runtime, checkpoint)
    assert excinfo.value.code is SimulationErrorCode.VALIDATION_FAILED
