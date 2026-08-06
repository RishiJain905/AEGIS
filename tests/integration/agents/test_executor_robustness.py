"""Robustness of the split executor: no orphaned 'running' tasks, timeout fires,
run-scoped lanes survive a failed turn, and orphan recovery requeues/fails.

Regression cover for the split's failure modes: a failed autonomy/copilot turn
must not terminate the shared run-scoped session (which would strand its sibling
queued tasks), a claimed task must always reach a terminal state (never orphan in
'running'), the per-task timeout must still fire, and a task stranded in 'running'
by a worker crash must be reclaimed.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.recovery import (
    finalize_tasks_for_stopped_run,
    recover_orphaned_tasks,
)
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import (
    AgentTaskStatus,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole, AgentSessionState
from aegis_contracts.generation import GenerationRequestV1, ProviderGenerateResponseV1
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_workers.agent_runtime_runner import _poll_once
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.agents.runtime.helpers import seed_incident_with_evidence, seed_run_with_evidence

_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _service() -> GenerationService:
    settings = load_provider_settings()
    return GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )


class _FailFirstFacade(AgentGenerationFacade):
    """Raises on the first generate() (turn fails), then delegates to the mock."""

    def __init__(self, service: GenerationService) -> None:
        super().__init__(service)
        self.calls = 0

    async def generate(
        self, request: GenerationRequestV1, *, dry_run: bool = False
    ) -> ProviderGenerateResponseV1:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("simulated provider blowup")
        return await super().generate(request, dry_run=dry_run)


class _HangingFacade(AgentGenerationFacade):
    """generate() blocks longer than the task timeout."""

    async def generate(
        self, request: GenerationRequestV1, *, dry_run: bool = False
    ) -> ProviderGenerateResponseV1:
        await asyncio.sleep(30)
        return await super().generate(request, dry_run=dry_run)


def _session_req() -> CreateAgentSessionRequestV1:
    return CreateAgentSessionRequestV1(
        schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
        role=AgentRole.TRACE,
        trace_id=_TRACE,
        enqueue_initial_task=False,
        provider_id="mock",
    )


def _task_req(key: str) -> CreateAgentTaskRequestV1:
    return CreateAgentTaskRequestV1(
        schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
        idempotency_key=key,
        provider_id="mock",
    )


@pytest.mark.asyncio
async def test_run_scoped_lane_survives_failed_turn_and_sibling_runs(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """A failed run-scoped turn must NOT terminate the session (lane), and a
    subsequent task in the same session must still execute to completion — the
    exact shared-autonomy-lane cascade that orphaned sibling tasks."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        session = await AgentSessionService().create_run_session(
            uow, run_id=run_id, request=_session_req()
        )
        first = await AgentTaskService().create_task(
            uow, session=session, request=_task_req("lane-turn-1")
        )
        second = await AgentTaskService().create_task(
            uow, session=session, request=_task_req("lane-turn-2")
        )

    executor = TaskExecutor(generation=_FailFirstFacade(_service()))
    async with PostgresUnitOfWork(session_maker) as uow:
        with pytest.raises(AgentRuntimeError):
            await executor.execute(uow, first.id)
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, second.id)

    async with PostgresUnitOfWork(session_maker) as uow:
        t1 = await uow.agent_tasks.get_by_id(first.id)
        t2 = await uow.agent_tasks.get_by_id(second.id)
        sess = await uow.agent_sessions.get_by_id(session.id)
    assert t1 is not None and t1.status == AgentTaskStatus.FAILED
    # The lane survives the failed turn — session is not terminal.
    assert sess is not None
    assert sess.state not in {
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
        AgentSessionState.COMPLETED,
    }
    # The sibling task ran to completion (no orphan, no cascade).
    assert t2 is not None and t2.status == AgentTaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_failed_claimed_task_never_orphans_in_running(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """No matter how a claimed task fails, it reaches a terminal state — never
    'running'."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        session = await AgentSessionService().create_run_session(
            uow, run_id=run_id, request=_session_req()
        )
        task = await AgentTaskService().create_task(
            uow, session=session, request=_task_req("orphan-guard")
        )
    executor = TaskExecutor(generation=_FailFirstFacade(_service()))
    async with PostgresUnitOfWork(session_maker) as uow:
        with pytest.raises(AgentRuntimeError):
            await executor.execute(uow, task.id)
    async with PostgresUnitOfWork(session_maker) as uow:
        final = await uow.agent_tasks.get_by_id(task.id)
    assert final is not None
    assert final.status != AgentTaskStatus.RUNNING
    assert final.status == AgentTaskStatus.FAILED
    assert final.error_code is not None
    assert final.completed_at is not None


@pytest.mark.asyncio
async def test_timeout_fires_and_times_out_task(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """The per-task timeout still bounds the model call in the split structure."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        session = await AgentSessionService().create_run_session(
            uow, run_id=run_id, request=_session_req()
        )
        task = await AgentTaskService().create_task(
            uow, session=session, request=_task_req("timeout")
        )
    executor = TaskExecutor(generation=_HangingFacade(_service()), timeout_seconds=0.5)
    async with PostgresUnitOfWork(session_maker) as uow:
        with pytest.raises(AgentRuntimeError):
            await executor.execute(uow, task.id)
    async with PostgresUnitOfWork(session_maker) as uow:
        final = await uow.agent_tasks.get_by_id(task.id)
    assert final is not None
    assert final.status == AgentTaskStatus.TIMED_OUT


async def _make_running_task(
    uow: PostgresUnitOfWork,
    *,
    attempt: int,
    started_ago_seconds: float,
    incident_id: str,
) -> str:
    session = await AgentSessionService().create_session(
        uow,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id=_TRACE,
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    task = await AgentTaskService().create_task(
        uow, session=session, request=_task_req(f"orphan-{attempt}-{started_ago_seconds}")
    )
    # The sweep's staleness anchor is ``updated_at`` (the heartbeat's liveness
    # signal), not ``started_at`` — an abandoned task is one whose heartbeat
    # stopped, so both timestamps must be old for the task to read as orphaned.
    abandoned = datetime.now(UTC) - timedelta(seconds=started_ago_seconds)
    running = task.model_copy(
        update={
            "status": AgentTaskStatus.RUNNING,
            "attempt": attempt,
            "started_at": abandoned,
            "updated_at": abandoned,
        }
    )
    await uow.agent_tasks.update(running)
    return task.id


@pytest.mark.asyncio
async def test_orphan_recovery_requeues_then_fails_and_respects_age(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    # Seed the incident once (fixed-id seeder); reuse it across distinct sessions.
    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, _run_id, _evidence = await seed_incident_with_evidence(uow)

    # (1) First-attempt orphan, aged past threshold -> requeued, attempt++.
    async with PostgresUnitOfWork(session_maker) as uow:
        t_requeue = await _make_running_task(
            uow, attempt=1, started_ago_seconds=400, incident_id=incident_id
        )
    async with PostgresUnitOfWork(session_maker) as uow:
        n = await recover_orphaned_tasks(uow, older_than_seconds=240)
        assert n == 1
    async with PostgresUnitOfWork(session_maker) as uow:
        task = await uow.agent_tasks.get_by_id(t_requeue)
    assert task is not None
    assert task.status == AgentTaskStatus.QUEUED
    assert task.attempt == 2

    # (2) Attempt-capped orphan -> terminally timed out.
    async with PostgresUnitOfWork(session_maker) as uow:
        t_fail = await _make_running_task(
            uow, attempt=2, started_ago_seconds=400, incident_id=incident_id
        )
    async with PostgresUnitOfWork(session_maker) as uow:
        n = await recover_orphaned_tasks(uow, older_than_seconds=240)
        assert n == 1
    async with PostgresUnitOfWork(session_maker) as uow:
        task = await uow.agent_tasks.get_by_id(t_fail)
    assert task is not None
    assert task.status == AgentTaskStatus.TIMED_OUT
    assert task.completed_at is not None

    # (3) A freshly-claimed running task (within the window) is NOT reclaimed.
    async with PostgresUnitOfWork(session_maker) as uow:
        t_fresh = await _make_running_task(
            uow, attempt=1, started_ago_seconds=5, incident_id=incident_id
        )
    async with PostgresUnitOfWork(session_maker) as uow:
        n = await recover_orphaned_tasks(uow, older_than_seconds=240)
        assert n == 0
    async with PostgresUnitOfWork(session_maker) as uow:
        task = await uow.agent_tasks.get_by_id(t_fresh)
    assert task is not None
    assert task.status == AgentTaskStatus.RUNNING


async def _orphan_run_scoped_task(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    started_ago_seconds: float,
    key: str,
) -> str:
    """Create a run-scoped mock task under ``run_id`` and strand it in 'running'."""
    async with PostgresUnitOfWork(session_maker) as uow:
        session = await AgentSessionService().create_run_session(
            uow, run_id=run_id, request=_session_req()
        )
        task = await AgentTaskService().create_task(uow, session=session, request=_task_req(key))
        # Same anchor as _make_running_task: the sweep reads ``updated_at``, so an
        # abandoned task must carry an old heartbeat timestamp, not just an old claim.
        abandoned = datetime.now(UTC) - timedelta(seconds=started_ago_seconds)
        orphaned = task.model_copy(
            update={
                "status": AgentTaskStatus.RUNNING,
                "attempt": 1,
                "started_at": abandoned,
                "updated_at": abandoned,
            }
        )
        await uow.agent_tasks.update(orphaned)
    return task.id


@pytest.mark.asyncio
async def test_worker_poll_reclaims_orphan_and_reruns_to_completion(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """The worker poll reclaims a task abandoned in 'running' past the lease and
    re-runs it to completion in the same pass — the 'worker replaced mid-task'
    path. A task still within the lease is left untouched."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
    abandoned = await _orphan_run_scoped_task(
        session_maker, run_id=run_id, started_ago_seconds=1000, key="worker-orphan-abandoned"
    )
    live = await _orphan_run_scoped_task(
        session_maker, run_id=run_id, started_ago_seconds=5, key="worker-orphan-live"
    )

    executor = TaskExecutor(generation=AgentGenerationFacade(_service()))
    # One poll: reclaim (requeue attempt++) -> list_queued picks it up -> execute.
    await _poll_once(session_maker, executor, orphan_lease_seconds=480.0)

    async with PostgresUnitOfWork(session_maker) as uow:
        reclaimed = await uow.agent_tasks.get_by_id(abandoned)
        untouched = await uow.agent_tasks.get_by_id(live)
    # The stale orphan was reclaimed (attempt++) and re-run to completion.
    assert reclaimed is not None
    assert reclaimed.status == AgentTaskStatus.COMPLETED
    assert reclaimed.attempt == 2
    # The within-lease running task is never reclaimed.
    assert untouched is not None
    assert untouched.status == AgentTaskStatus.RUNNING
    assert untouched.attempt == 1


async def _make_in_flight_task(
    uow: PostgresUnitOfWork,
    *,
    run_id: str,
    status: AgentTaskStatus,
    key: str,
) -> str:
    """Create a run-scoped task under ``run_id`` and leave it queued or running."""
    session = await AgentSessionService().create_run_session(
        uow, run_id=run_id, request=_session_req()
    )
    task = await AgentTaskService().create_task(uow, session=session, request=_task_req(key))
    if status == AgentTaskStatus.RUNNING:
        running = task.model_copy(
            update={"status": AgentTaskStatus.RUNNING, "started_at": datetime.now(UTC)}
        )
        await uow.agent_tasks.update(running)
    return task.id


@pytest.mark.asyncio
async def test_run_stop_finalization_cancels_in_flight_tasks_with_events(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """A stopped run's queued and running tasks reach CANCELLED with an
    attributable reason, and each cancellation lands in the run's event stream —
    the copilot cards resolve instead of spinning, and the record shows why."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        queued_id = await _make_in_flight_task(
            uow, run_id=run_id, status=AgentTaskStatus.QUEUED, key="stop-queued"
        )
        running_id = await _make_in_flight_task(
            uow, run_id=run_id, status=AgentTaskStatus.RUNNING, key="stop-running"
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        cancelled = await finalize_tasks_for_stopped_run(uow, run_id=run_id)
        assert cancelled == 2

    async with PostgresUnitOfWork(session_maker) as uow:
        queued = await uow.agent_tasks.get_by_id(queued_id)
        running = await uow.agent_tasks.get_by_id(running_id)
        events = await uow.events.list_by_run(run_id)
    assert queued is not None
    assert queued.status == AgentTaskStatus.CANCELLED
    assert queued.error_code == AgentRuntimeErrorCode.TASK_CANCELLED.value
    assert queued.error_message == "Run stopped before the task started"
    assert queued.completed_at is not None
    assert running is not None
    assert running.status == AgentTaskStatus.CANCELLED
    assert running.error_message == "Run stopped while the task was in flight"
    failed_events = [e for e in events if e.type == "agent.task.failed"]
    assert len(failed_events) == 2
    for event in failed_events:
        assert event.payload["status"] == "cancelled"
        assert event.payload["errorCode"] == AgentRuntimeErrorCode.TASK_CANCELLED.value
        assert event.payload["errorMessage"] in {
            "Run stopped before the task started",
            "Run stopped while the task was in flight",
        }


@pytest.mark.asyncio
async def test_executor_does_not_resurrect_a_cancelled_task(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """The executor must never clobber a run-stop cancellation: a task cancelled
    while the worker was mid-flight stays CANCELLED even when the executor runs
    against it afterwards (its claim phase finds no QUEUED row and no-ops)."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        task_id = await _make_in_flight_task(
            uow, run_id=run_id, status=AgentTaskStatus.RUNNING, key="stop-resurrect"
        )
    async with PostgresUnitOfWork(session_maker) as uow:
        await finalize_tasks_for_stopped_run(uow, run_id=run_id)

    executor = TaskExecutor(generation=AgentGenerationFacade(_service()))
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task_id)
    async with PostgresUnitOfWork(session_maker) as uow:
        final = await uow.agent_tasks.get_by_id(task_id)
    assert final is not None
    assert final.status == AgentTaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_late_executor_failure_does_not_clobber_a_cancelled_task(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """The failure path is CAS-guarded too: a task the run-stop finalizer
    cancelled while the executor was mid-flight keeps its CANCELLED state and the
    canceller's event — a late FAILED write and its event are both skipped."""
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence = await seed_run_with_evidence(uow)
        task_id = await _make_in_flight_task(
            uow, run_id=run_id, status=AgentTaskStatus.RUNNING, key="stop-late-fail"
        )
        task = await uow.agent_tasks.get_by_id(task_id)
        assert task is not None
        session = await uow.agent_sessions.get_by_id(task.session_id)
        assert session is not None
        running_snapshot = task
    async with PostgresUnitOfWork(session_maker) as uow:
        await finalize_tasks_for_stopped_run(uow, run_id=run_id)

    executor = TaskExecutor(generation=AgentGenerationFacade(_service()))
    async with PostgresUnitOfWork(session_maker) as uow:
        # The executor's own failure path, racing the cancellation: the CAS out of
        # 'running' loses, so nothing is written and no event is appended.
        await executor._fail_task(  # type: ignore[attr-defined]
            uow,
            task=running_snapshot,
            session=session,
            run_id=run_id,
            code=AgentRuntimeErrorCode.PROVIDER_FAILURE,
            message="Provider request timed out",
        )
        await uow.commit()
    async with PostgresUnitOfWork(session_maker) as uow:
        final = await uow.agent_tasks.get_by_id(task_id)
        events = await uow.events.list_by_run(run_id)
    assert final is not None
    assert final.status == AgentTaskStatus.CANCELLED
    assert final.error_code == AgentRuntimeErrorCode.TASK_CANCELLED.value
    # Only the canceller's event exists — the late failure added nothing.
    failed_events = [e for e in events if e.type == "agent.task.failed"]
    assert len(failed_events) == 1
    assert failed_events[0].payload["status"] == "cancelled"
