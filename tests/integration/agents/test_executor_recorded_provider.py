"""Recorded provider deterministic replay for agent tasks."""

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
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from tests.agents.runtime.helpers import seed_incident_with_evidence


def _build_executor() -> TaskExecutor:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    return TaskExecutor(generation=AgentGenerationFacade(service))


@pytest.mark.asyncio
async def test_recorded_provider_replay_is_deterministic(unit_of_work) -> None:
    incident_id, _run_id, evidence_id = await seed_incident_with_evidence(unit_of_work)
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
            provider_id="recorded",
        ),
    )
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=CreateAgentTaskRequestV1(
            schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotency_key="recorded-replay",
            provider_id="recorded",
        ),
    )
    await _build_executor().execute(unit_of_work, task.id)
    completed = await tasks.get_task(unit_of_work, task.id)
    assert completed.status == AgentTaskStatus.COMPLETED
    detail = await sessions.get_detail(unit_of_work, session.id)
    step_artifacts = [
        item for item in detail.artifacts if item.artifact_type.value == "step_result"
    ]
    assert step_artifacts
    payload = step_artifacts[0].payload
    assert payload.get("rationale") == "Recorded deterministic investigation step"
    assert evidence_id in {item["evidenceId"] for item in payload.get("evidenceCitations", [])}
