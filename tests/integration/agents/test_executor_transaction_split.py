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
"""

from __future__ import annotations

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


class _LockProbingFacade(AgentGenerationFacade):
    """During generate(), asserts the run's advisory lock is FREE on a separate connection.

    The executor takes ``pg_advisory_xact_lock(key)`` when it appends the started
    event; a second connection's ``pg_try_advisory_xact_lock(key)`` therefore
    returns ``False`` if (and only if) some transaction still holds that lock. We
    run the probe on a fresh session (a distinct pooled connection) inside the
    model call. If the split is correct, the executor has already committed the
    claim transaction, so the probe acquires the lock and returns ``True``.
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
        async with self._session_maker() as probe:
            result = await probe.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": self._lock_key},
            )
            acquired = bool(result.scalar())
            # Release the xact-scoped lock by ending the probe transaction.
            await probe.rollback()
        self.lock_was_free = acquired
        assert acquired, (
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


@pytest.mark.asyncio
async def test_no_transaction_or_advisory_lock_spans_generate(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
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
                idempotency_key="txn-split-probe",
                provider_id="mock",
            ),
        )

    executor, facade = _build_probe_executor(session_maker, run_id)
    # A distinct uow/connection for the executor — mirrors the worker path.
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task.id)

    # generate() ran (the probe fired) and observed the lock free, and the task
    # reached its terminal state — the model call held no transaction.
    assert facade.lock_was_free is True

    async with PostgresUnitOfWork(session_maker) as uow:
        completed = await uow.agent_tasks.get_by_id(task.id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_ticker_can_append_events_while_agent_task_generates(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """A concurrent per-run event append proceeds during the model call.

    This is the freeze the fix targets: a second writer on the same run (the tick
    engine) appends an event under the per-run advisory lock while an agent task
    is mid-generation. It must not block on the executor's transaction.
    """
    _ = db_session
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
                idempotency_key="txn-split-ticker",
                provider_id="mock",
            ),
        )

    settings = load_provider_settings()

    class _TickerDuringGenerateFacade(AgentGenerationFacade):
        async def generate(
            self, request: GenerationRequestV1, *, dry_run: bool = False
        ) -> ProviderGenerateResponseV1:
            # Simulate the tick engine appending a per-run event mid-model-call by
            # acquiring the run's advisory lock and reading the sequence on a
            # separate connection, bounded so a regression fails fast instead of
            # hanging the suite.
            import asyncio

            async def _acquire_run_lock() -> None:
                async with session_maker() as ticker:
                    await ticker.execute(
                        text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": _advisory_lock_key(run_id)},
                    )
                    await ticker.rollback()

            await asyncio.wait_for(_acquire_run_lock(), timeout=10.0)
            return await super().generate(request, dry_run=dry_run)

    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    executor = TaskExecutor(generation=_TickerDuringGenerateFacade(service))
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task.id)

    async with PostgresUnitOfWork(session_maker) as uow:
        completed = await uow.agent_tasks.get_by_id(task.id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED
