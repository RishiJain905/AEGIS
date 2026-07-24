"""Concurrency proof for the agent executor transaction split.

Root cause fixed here: the executor used to hold ONE transaction across the whole
task, including the LLM ``generate()`` call. Appending the "task started" event
takes a per-run ``pg_advisory_xact_lock`` held until commit, and the tick engine
appends step events under the SAME per-run lock — so while an agent task ran the
model (60-120s on the local 27B), the tick engine blocked and the run froze.

The fix splits execution into short transactions with the model call OUTSIDE any
transaction. These tests prove it directly: during ``generate()`` a SEPARATE
database connection can acquire the run's advisory lock, which is only possible if
the executor holds no transaction/advisory lock at model-call time. Under the old
single-transaction executor the probe would observe the lock held and fail.

Test hygiene: every probe uses a NON-blocking ``pg_try_advisory_xact_lock`` and a
try/finally that ALWAYS rolls back (releasing the xact lock) and closes the
connection, and the concurrent-writer probe uses ``PostgresUnitOfWork`` (whose
__aexit__ rolls back + closes even under cancellation). So a probe never leaks a
held lock or an open connection into sibling tests, even on failure.
"""

from __future__ import annotations

import asyncio

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import (
    AgentTaskStatus,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole
from aegis_contracts.generation import GenerationRequestV1, ProviderGenerateResponseV1
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.repositories.postgres import _advisory_lock_key
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.agents.runtime.helpers import seed_run_with_evidence

_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


async def _run_lock_is_free(
    session_maker: async_sessionmaker[AsyncSession], lock_key: int
) -> bool:
    """Return True if the per-run advisory lock is free, on a fresh connection.

    Uses the NON-blocking ``pg_try_advisory_xact_lock`` so it can never hang or be
    cancelled mid-query, and a try/finally that ALWAYS rolls back (releasing the
    xact-scoped lock it just took) and closes the connection — no lock or
    connection can leak into a sibling test.
    """
    probe = session_maker()
    try:
        result = await probe.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key}
        )
        return bool(result.scalar())
    finally:
        await probe.rollback()
        await probe.close()


class _LockProbingFacade(AgentGenerationFacade):
    """During generate(), records whether the run's advisory lock is free.

    The executor takes ``pg_advisory_xact_lock(key)`` when it appends the started
    event; a second connection can only acquire that key if no transaction still
    holds it. If the split is correct, the executor has already committed the claim
    transaction, so the probe finds the lock free.
    """

    def __init__(
        self,
        service: GenerationService,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        run_id: str,
    ) -> None:
        super().__init__(service)
        self._session_maker = session_maker
        self._lock_key = _advisory_lock_key(run_id)
        self.lock_was_free: bool | None = None

    async def generate(
        self, request: GenerationRequestV1, *, dry_run: bool = False
    ) -> ProviderGenerateResponseV1:
        self.lock_was_free = await _run_lock_is_free(self._session_maker, self._lock_key)
        assert self.lock_was_free, (
            "run advisory lock was held during generate() — a transaction spans "
            "the model call, which will freeze the tick engine"
        )
        return await super().generate(request, dry_run=dry_run)


def _build_probe_executor(
    session_maker: async_sessionmaker[AsyncSession],
    run_id: str,
) -> tuple[TaskExecutor, _LockProbingFacade]:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    facade = _LockProbingFacade(service, session_maker=session_maker, run_id=run_id)
    return TaskExecutor(generation=facade), facade


async def _seed_run_scoped_task(
    session_maker: async_sessionmaker[AsyncSession], *, idempotency_key: str
) -> tuple[str, str]:
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence_id = await seed_run_with_evidence(uow)
        session = await AgentSessionService().create_run_session(
            uow,
            run_id=run_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=AgentRole.TRACE,
                trace_id=_TRACE,
                enqueue_initial_task=False,
                provider_id="mock",
            ),
        )
        task = await AgentTaskService().create_task(
            uow,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key=idempotency_key,
                provider_id="mock",
            ),
        )
        return run_id, task.id


@pytest.mark.asyncio
async def test_no_transaction_or_advisory_lock_spans_generate(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    run_id, task_id = await _seed_run_scoped_task(session_maker, idempotency_key="txn-split-probe")

    executor, facade = _build_probe_executor(session_maker, run_id)
    # A distinct uow/connection for the executor — mirrors the worker path.
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task_id)

    # generate() ran (the probe fired) and observed the lock free, and the task
    # reached its terminal state — the model call held no transaction.
    assert facade.lock_was_free is True

    async with PostgresUnitOfWork(session_maker) as uow:
        completed = await uow.agent_tasks.get_by_id(task_id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_ticker_can_take_run_lock_while_agent_task_generates(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """A concurrent per-run writer proceeds during the model call.

    This is the freeze the fix targets: a second writer on the same run (the tick
    engine) takes the per-run advisory lock via ``next_sequence`` while an agent
    task is mid-generation. It must not block on the executor's transaction. The
    writer runs on its OWN ``PostgresUnitOfWork``, whose __aexit__ rolls back +
    closes even if the wait_for cancels it — so a regression fails fast without
    leaking a connection.
    """
    _ = db_session
    run_id, task_id = await _seed_run_scoped_task(session_maker, idempotency_key="txn-split-ticker")
    settings = load_provider_settings()
    ticker_advanced = {"ok": False}

    class _TickerDuringGenerateFacade(AgentGenerationFacade):
        async def generate(
            self, request: GenerationRequestV1, *, dry_run: bool = False
        ) -> ProviderGenerateResponseV1:
            async def _tick() -> None:
                async with PostgresUnitOfWork(session_maker) as ticker:
                    await ticker.events.next_sequence(run_id)

            await asyncio.wait_for(_tick(), timeout=5.0)
            ticker_advanced["ok"] = True
            return await super().generate(request, dry_run=dry_run)

    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    executor = TaskExecutor(generation=_TickerDuringGenerateFacade(service))
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task_id)

    assert ticker_advanced["ok"] is True
    async with PostgresUnitOfWork(session_maker) as uow:
        completed = await uow.agent_tasks.get_by_id(task_id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED
