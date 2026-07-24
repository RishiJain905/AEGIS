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
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.recovery import recover_orphaned_tasks
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
    started = datetime.now(UTC) - timedelta(seconds=started_ago_seconds)
    running = task.model_copy(
        update={"status": AgentTaskStatus.RUNNING, "attempt": attempt, "started_at": started}
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
        started = datetime.now(UTC) - timedelta(seconds=started_ago_seconds)
        orphaned = task.model_copy(
            update={"status": AgentTaskStatus.RUNNING, "attempt": 1, "started_at": started}
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
