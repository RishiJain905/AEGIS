"""Agent domain events must carry the run's VIRTUAL sim-time, not wall-clock.

Architecture contract §7 keeps ``sim_time`` (virtual run clock) and ``recorded_at``
(wall-clock) distinct. A regression stamped every agent-task event with
``datetime.now()``, rendering agent activity ~204 days off (wall date minus the
sim epoch) on the replay/dossier timeline while alerts/operator commands sat at
their true offsets. This pins the fix: agent events equal the run's sim clock and
differ from wall-clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
from tests.agents.runtime.helpers import seed_run_with_evidence

_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
# A virtual sim-time far from wall-clock (the +00:24 offset from the 2026-01-01
# sim epoch, mirroring where alerts land) so wall-clock stamping is unmistakable.
_FIXED_SIM_TIME = datetime(2026, 1, 1, 0, 24, 0, tzinfo=UTC)

_AGENT_EVENT_TYPES = {
    "agent.session.started",
    "agent.session.state_changed",
    "agent.task.started",
    "agent.task.completed",
    "agent.tool.invoked",
}


def _build_executor() -> TaskExecutor:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    return TaskExecutor(generation=AgentGenerationFacade(service))


@pytest.mark.asyncio
async def test_agent_events_carry_run_sim_time_not_wall_clock(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    async with PostgresUnitOfWork(session_maker) as uow:
        run_id, _evidence_id = await seed_run_with_evidence(uow)
        # Pin the run's virtual clock to a value clearly distinct from wall-clock.
        run = await uow.runs.get_by_id(run_id)
        assert run is not None
        await uow.runs.update_with_revision(
            run.model_copy(update={"sim_time": _FIXED_SIM_TIME}),
            expected_revision=run.revision,
        )

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
                idempotency_key="sim-time-probe",
                provider_id="mock",
            ),
        )

    async with PostgresUnitOfWork(session_maker) as uow:
        await _build_executor().execute(uow, task.id)

    async with PostgresUnitOfWork(session_maker) as uow:
        completed = await uow.agent_tasks.get_by_id(task.id)
        events = await uow.events.list_by_run(run_id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED

    wall_now = datetime.now(UTC)
    agent_events = [e for e in events if e.type in _AGENT_EVENT_TYPES]
    # The task exercises the whole path: session started, state changes, task
    # started, tool invocations, task completed.
    types_seen = {e.type for e in agent_events}
    assert "agent.task.started" in types_seen
    assert "agent.task.completed" in types_seen
    assert "agent.tool.invoked" in types_seen

    for event in agent_events:
        # sim_time is the run's VIRTUAL clock, not wall-clock.
        assert event.sim_time == _FIXED_SIM_TIME, (
            f"{event.type} sim_time={event.sim_time!r} != run sim_time {_FIXED_SIM_TIME!r}"
        )
        # recorded_at stays wall-clock (distinct from sim_time, per contract §7).
        assert abs((event.recorded_at - wall_now).total_seconds()) < 300
        assert abs(event.sim_time - wall_now) > timedelta(days=1)
