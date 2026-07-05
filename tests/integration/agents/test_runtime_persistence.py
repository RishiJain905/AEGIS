"""Integration tests for agent runtime persistence."""

from __future__ import annotations

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.recovery import recover_running_tasks
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
from tests.agents.runtime.helpers import seed_incident_with_evidence


def _build_executor(*, timeout_seconds: float = 30.0) -> TaskExecutor:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    return TaskExecutor(
        generation=AgentGenerationFacade(service),
        timeout_seconds=timeout_seconds,
    )


@pytest.mark.asyncio
async def test_auditability_requires_tool_invocation_records(unit_of_work) -> None:
    incident_id, _run_id, _evidence_id = await seed_incident_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_session(
        unit_of_work,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=CreateAgentTaskRequestV1(
            schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotency_key="acceptance-audit",
            provider_id="mock",
        ),
    )
    await _build_executor().execute(unit_of_work, task.id)
    invocations = await unit_of_work.tool_invocations.list_for_session(session.id)
    assert invocations
    assert all(item.duration_ms >= 0 for item in invocations)


@pytest.mark.asyncio
async def test_agent_failure_does_not_mutate_run_state(unit_of_work) -> None:
    incident_id, run_id, _evidence_id = await seed_incident_with_evidence(unit_of_work)
    run_before = await unit_of_work.runs.get_by_id(run_id)
    assert run_before is not None
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_session(
        unit_of_work,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=CreateAgentTaskRequestV1(
            schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotency_key="failure-isolation",
            provider_id="mock",
        ),
    )
    executor = _build_executor()
    executor.request_cancel(task.id)
    with pytest.raises(AgentRuntimeError):
        await executor.execute(unit_of_work, task.id)
    run_after = await unit_of_work.runs.get_by_id(run_id)
    assert run_after is not None
    assert run_after.status == run_before.status


@pytest.mark.asyncio
async def test_runtime_state_persisted_and_recoverable(unit_of_work) -> None:
    incident_id, _run_id, _evidence_id = await seed_incident_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_session(
        unit_of_work,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=CreateAgentTaskRequestV1(
            schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotency_key="integration-persist",
            provider_id="mock",
        ),
    )
    await _build_executor().execute(unit_of_work, task.id)
    detail = await sessions.get_detail(unit_of_work, session.id)
    assert detail.tasks[0].status == AgentTaskStatus.COMPLETED
    assert detail.tool_invocations
    assert detail.artifacts


@pytest.mark.asyncio
async def test_duplicate_task_idempotency(unit_of_work) -> None:
    incident_id, _run_id, _evidence_id = await seed_incident_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_session(
        unit_of_work,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    request = CreateAgentTaskRequestV1(
        schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
        idempotency_key="duplicate-key",
        provider_id="mock",
    )
    first = await tasks.create_task(unit_of_work, session=session, request=request)
    second = await tasks.create_task(unit_of_work, session=session, request=request)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_recovery_marks_running_tasks_failed(unit_of_work) -> None:
    incident_id, _run_id, _evidence_id = await seed_incident_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_session(
        unit_of_work,
        incident_id=incident_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.TRACE,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
            provider_id="mock",
        ),
    )
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=CreateAgentTaskRequestV1(
            schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotency_key="recovery",
            provider_id="mock",
        ),
    )
    running = task.model_copy(update={"status": AgentTaskStatus.RUNNING})
    await unit_of_work.agent_tasks.update(running)
    recovered = await recover_running_tasks(unit_of_work)
    assert recovered == 1
