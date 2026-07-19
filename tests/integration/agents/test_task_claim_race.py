"""Regression test for AEGIS-BUG-002 — atomic agent task claim.

Two executors racing on one QUEUED task (worker + inline API execute, or two
workers) must result in exactly one execution. The atomic
``UPDATE ... WHERE status='queued'`` claim in ``TaskExecutor`` guarantees a
single winner; the loser observes zero rows updated and no-ops.
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
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.integration.agents.helpers import seed_investigation_run


def _build_executor() -> TaskExecutor:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    return TaskExecutor(generation=AgentGenerationFacade(service))


@pytest.mark.asyncio
async def test_concurrent_execute_claims_task_once(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, _alert_ids, _evidence_id = await seed_investigation_run(uow)
        session = await AgentSessionService().create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=AgentRole.TRACE,
                trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                enqueue_initial_task=False,
                provider_id="mock",
            ),
        )
        task = await AgentTaskService().create_task(
            uow,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key="claim-race",
                provider_id="mock",
            ),
        )

    async def _execute() -> None:
        async with PostgresUnitOfWork(session_maker) as uow:
            await _build_executor().execute(uow, task.id)

    await asyncio.gather(_execute(), _execute())

    async with PostgresUnitOfWork(session_maker) as uow:
        final = await uow.agent_tasks.get_by_id(task.id)
        events = await uow.events.list_by_run(run_id)

    assert final is not None
    assert final.status == AgentTaskStatus.COMPLETED
    # The losing executor must not have produced a second execution.
    started = [event for event in events if event.type == "agent.task.started"]
    assert len(started) == 1
    completed = [event for event in events if event.type == "agent.task.completed"]
    assert len(completed) == 1
