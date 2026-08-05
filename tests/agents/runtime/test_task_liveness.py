"""A claimed task must always reach a terminal state, and say so while it works.

Covers the two halves of the orphaned-task defect: the executor's own liveness
signal (``updated_at`` heartbeat, and a terminal write when an inline run is
abandoned), and the sweep that guarantees a stranded task is failed rather than
left spinning. All offline — the unit of work is a fake.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aegis_agents.runtime.errors import AgentRuntimeErrorCode
from aegis_agents.runtime.executor import TaskExecutor, _PreparedTask
from aegis_agents.runtime.recovery import recover_orphaned_tasks
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
    AgentArtifactV1,
    AgentTaskStatus,
    AgentTaskV1,
)
from aegis_contracts.entities import AgentRole, AgentSessionState, AgentSessionV1, RunV1
from aegis_contracts.versioning import (
    AGENT_SESSION_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TASK_ID = "atk_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_SESSION_ID = "agent-session:ags_liveness"


def _task(
    *,
    status: AgentTaskStatus = AgentTaskStatus.RUNNING,
    updated_at: datetime = _NOW,
    attempt: int = 1,
    incident_id: str | None = None,
) -> AgentTaskV1:
    return AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id=_TASK_ID,
        session_id=_SESSION_ID,
        run_id=_RUN_ID,
        incident_id=incident_id,
        status=status,
        attempt=attempt,
        idempotency_key="liveness-1",
        trace_id=_TRACE_ID,
        provider_id="mock",
        created_at=_NOW,
        updated_at=updated_at,
        started_at=_NOW,
    )


class _FakeTaskRepo:
    def __init__(self, tasks: list[AgentTaskV1]) -> None:
        self.tasks = tasks
        self.transitions: list[tuple[AgentTaskV1, tuple[str, ...]]] = []
        #: Set to make the CAS lose, as it does when another writer got there first.
        self.claim_result = True

    async def list_running(self) -> list[AgentTaskV1]:
        return [t for t in self.tasks if t.status == AgentTaskStatus.RUNNING]

    async def claim_transition(
        self,
        task: AgentTaskV1,
        *,
        from_statuses: tuple[str, ...],
    ) -> bool:
        self.transitions.append((task, from_statuses))
        return self.claim_result


def _uow(tasks: list[AgentTaskV1], *, session: AgentSessionV1 | None = None) -> Any:
    """The slice of the unit of work the sweep and the heartbeat actually touch."""

    class _Uow:
        pass

    uow = _Uow()
    uow.agent_tasks = _FakeTaskRepo(tasks)
    uow.artifacts = []
    uow.appended = []
    uow.commits = 0

    class _Artifacts:
        async def add(self, artifact: AgentArtifactV1) -> AgentArtifactV1:
            uow.artifacts.append(artifact)
            return artifact

    class _Sessions:
        async def get_by_id(self, session_id: str) -> AgentSessionV1 | None:
            return session

        async def update(self, *args: Any, **kwargs: Any) -> Any:
            return None

    class _Events:
        async def next_sequence(self, run_id: str) -> int:
            return len(uow.appended) + 1

    class _Runs:
        async def get_by_id(self, run_id: str) -> RunV1:
            return RunV1(
                schema_version=RUN_SCHEMA_VERSION,
                id=_RUN_ID,
                scenario_version_id="scenario-version:test-v1",
                seed=42,
                status="running",
                started_at=_NOW,
                sim_time=_NOW,
                revision=1,
            )

    async def append_event(envelope: Any) -> Any:
        uow.appended.append(envelope)
        return envelope

    async def commit() -> None:
        uow.commits += 1

    uow.agent_artifacts = _Artifacts()
    uow.agent_sessions = _Sessions()
    uow.events = _Events()
    uow.runs = _Runs()
    uow.append_event = append_event
    uow.commit = commit
    return uow


# --- the sweep ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_heartbeating_task_is_left_alone() -> None:
    """Liveness is what the sweep reads. A task whose heartbeat landed a moment
    ago is working, however long ago it was claimed."""
    fresh = _task(updated_at=datetime.now(UTC))
    uow = _uow([fresh])
    reclaimed = await recover_orphaned_tasks(uow, older_than_seconds=60.0)
    assert reclaimed == 0
    assert uow.agent_tasks.transitions == []


@pytest.mark.asyncio
async def test_a_task_whose_heartbeat_stopped_is_reclaimed() -> None:
    stale = _task(updated_at=datetime.now(UTC) - timedelta(minutes=10))
    uow = _uow([stale])
    reclaimed = await recover_orphaned_tasks(uow, older_than_seconds=60.0)
    assert reclaimed == 1
    requeued, from_statuses = uow.agent_tasks.transitions[0]
    assert requeued.status == AgentTaskStatus.QUEUED
    assert requeued.attempt == 2
    assert from_statuses == (AgentTaskStatus.RUNNING.value,)


@pytest.mark.asyncio
async def test_an_exhausted_orphan_is_failed_with_an_artifact_the_operator_can_read() -> None:
    """The chip must stop spinning AND say why. A swept task that left nothing
    behind looks identical to one still thinking, which is the whole confusion."""
    stale = _task(updated_at=datetime.now(UTC) - timedelta(minutes=10), attempt=2)
    uow = _uow([stale])
    reclaimed = await recover_orphaned_tasks(uow, older_than_seconds=60.0)

    assert reclaimed == 1
    failed, _ = uow.agent_tasks.transitions[0]
    assert failed.status == AgentTaskStatus.TIMED_OUT
    assert failed.error_code == AgentRuntimeErrorCode.TASK_TIMEOUT.value

    assert len(uow.artifacts) == 1
    artifact = uow.artifacts[0]
    assert artifact.artifact_type == AgentArtifactType.AUDIT
    assert artifact.task_id == stale.id
    assert artifact.payload["outcome"] == "task_timeout"
    assert artifact.payload["staleForSeconds"] > 60.0


@pytest.mark.asyncio
async def test_losing_the_cas_writes_no_artifact() -> None:
    """Idempotency rides on the status-guarded CAS: a second sweep, or a racing
    worker, finds no row and must leave no second audit trail behind."""
    stale = _task(updated_at=datetime.now(UTC) - timedelta(minutes=10), attempt=2)
    uow = _uow([stale])
    uow.agent_tasks.claim_result = False
    reclaimed = await recover_orphaned_tasks(uow, older_than_seconds=60.0)
    assert reclaimed == 0
    assert uow.artifacts == []
    assert uow.appended == []


# --- the executor's own liveness -------------------------------------------------


def _prepared() -> _PreparedTask:
    session = AgentSessionV1(
        schema_version=AGENT_SESSION_SCHEMA_VERSION,
        id=_SESSION_ID,
        run_id=_RUN_ID,
        role=AgentRole.WATCHTOWER,
        state=AgentSessionState.GATHERING,
        trace_id=_TRACE_ID,
        created_at=_NOW,
        updated_at=_NOW,
    )
    return _PreparedTask(
        task=_task(),
        session=session,
        run_id=_RUN_ID,
        agent_name="WATCHTOWER",
        definition=None,
        budget=None,
        incident_title=None,
        run_scoped=True,
        visible_ids=set(),
        role_handler=None,
        request=None,  # type: ignore[arg-type]
        evidence_catalogue={"total": 0, "shown": 0, "truncated": False, "items": []},
    )


@pytest.mark.asyncio
async def test_heartbeat_refreshes_updated_at_while_the_task_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aegis_agents.runtime.executor as executor_module

    prepared = _prepared()
    uow = _uow([prepared.task])

    class _Ctx:
        async def __aenter__(self) -> Any:
            return uow

        async def __aexit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(executor_module, "PostgresUnitOfWork", lambda maker: _Ctx())
    monkeypatch.setattr(executor_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)

    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    beat = asyncio.ensure_future(executor._heartbeat(None, prepared))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)
    beat.cancel()

    assert uow.agent_tasks.transitions, "heartbeat never wrote a liveness update"
    written, from_statuses = uow.agent_tasks.transitions[0]
    assert from_statuses == (AgentTaskStatus.RUNNING.value,)
    assert written.status == AgentTaskStatus.RUNNING
    assert written.updated_at > prepared.task.updated_at


@pytest.mark.asyncio
async def test_heartbeat_stops_once_the_task_is_no_longer_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CAS is the stop signal: a heartbeat that outlived its task must not
    keep writing, and must never resurrect a row another writer finished."""
    import aegis_agents.runtime.executor as executor_module

    prepared = _prepared()
    uow = _uow([prepared.task])
    uow.agent_tasks.claim_result = False

    class _Ctx:
        async def __aenter__(self) -> Any:
            return uow

        async def __aexit__(self, *args: Any) -> None:
            return None

    monkeypatch.setattr(executor_module, "PostgresUnitOfWork", lambda maker: _Ctx())
    monkeypatch.setattr(executor_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)

    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    await asyncio.wait_for(executor._heartbeat(None, prepared), timeout=1.0)  # type: ignore[arg-type]
    assert len(uow.agent_tasks.transitions) == 1


@pytest.mark.asyncio
async def test_a_heartbeat_that_cannot_write_never_fails_the_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aegis_agents.runtime.executor as executor_module

    def _explode(maker: Any) -> Any:
        msg = "database is unreachable"
        raise RuntimeError(msg)

    monkeypatch.setattr(executor_module, "PostgresUnitOfWork", _explode)
    monkeypatch.setattr(executor_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)

    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    await asyncio.wait_for(executor._heartbeat(None, _prepared()), timeout=1.0)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_an_abandoned_inline_run_still_persists_a_terminal_task() -> None:
    """A cancelled HTTP request must not strand a claimed task in 'running'.

    ``CancelledError`` is a ``BaseException``, so it used to fly straight through
    the executor's ``except Exception`` failure handling — the task kept its
    committed RUNNING claim and never reached a terminal state.
    """
    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    prepared = _prepared()
    failures: list[AgentRuntimeErrorCode] = []

    async def _claim(uow: Any, task_id: str) -> _PreparedTask:
        return prepared

    async def _claimed(uow: Any, prep: _PreparedTask) -> None:
        raise asyncio.CancelledError

    async def _fail(uow: Any, prep: _PreparedTask, *, code: Any, message: str) -> None:
        failures.append(code)

    executor._claim_and_prepare = _claim  # type: ignore[method-assign]
    executor._execute_claimed = _claimed  # type: ignore[method-assign]
    executor._fail_and_commit = _fail  # type: ignore[method-assign]

    class _Uow:
        session_maker = None

    with pytest.raises(asyncio.CancelledError):
        await executor.execute(_Uow(), _TASK_ID)  # type: ignore[arg-type]

    assert failures == [AgentRuntimeErrorCode.TASK_CANCELLED]


@pytest.mark.asyncio
async def test_grounding_repair_sits_between_generation_and_persistence() -> None:
    """Wiring check. The repair is only useful where it actually runs: after the
    tool loop, before the persist phase validates grounding — and outside any
    transaction, which is the reason it cannot live in the persist phase."""
    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    prepared = _prepared()
    order: list[str] = []
    sentinel = object()

    async def _loop(uow: Any, prep: _PreparedTask) -> Any:
        order.append("loop")
        return sentinel

    async def _repair(prep: _PreparedTask, outcome: Any) -> Any:
        order.append("repair")
        assert outcome is sentinel
        return outcome

    async def _persist(uow: Any, prep: _PreparedTask, outcome: Any) -> None:
        order.append("persist")
        assert outcome is sentinel

    executor._run_tool_loop = _loop  # type: ignore[method-assign]
    executor._repair_grounding = _repair  # type: ignore[method-assign]
    executor._persist_result = _persist  # type: ignore[method-assign]

    class _Uow:
        async def commit(self) -> None:
            order.append("commit")

    await executor._execute_claimed(_Uow(), prepared)  # type: ignore[arg-type]
    assert order == ["loop", "repair", "persist", "commit"]
