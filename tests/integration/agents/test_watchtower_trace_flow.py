"""Full WATCHTOWER and TRACE flow integration test with PostgreSQL."""

from __future__ import annotations

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import AgentTaskStatus
from aegis_contracts.investigation import TriageEscalationLevel, TriggerWatchtowerRequestV1
from aegis_contracts.versioning import TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
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
async def test_watchtower_trace_flow_is_idempotent_and_grounded(unit_of_work) -> None:
    incident_id, run_id, alert_ids, evidence_id = await seed_investigation_run(unit_of_work)
    coordinator = WatchtowerCoordinator()
    request = TriggerWatchtowerRequestV1(
        schema_version=TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
        run_id=run_id,
        alert_ids=alert_ids,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id="mock",
        idempotency_key="integration-watchtower-001",
    )

    first = await coordinator.trigger_for_run(unit_of_work, request)
    assert first.incident_id == incident_id
    assert first.triage.grouped_alert_ids
    assert first.triage.escalation in {
        TriageEscalationLevel.INVESTIGATE,
        TriageEscalationLevel.URGENT,
    }
    assert first.trace_session_id is not None

    second = await coordinator.trigger_for_run(unit_of_work, request)
    assert second.triage.id == first.triage.id
    assert second.watchtower_session_id == first.watchtower_session_id

    tasks = AgentTaskService()
    trace_tasks = await unit_of_work.agent_tasks.list_for_session(first.trace_session_id)
    assert trace_tasks
    trace_task = trace_tasks[0]
    await _build_executor().execute(unit_of_work, trace_task.id)
    completed = await tasks.get_task(unit_of_work, trace_task.id)
    assert completed.status == AgentTaskStatus.COMPLETED

    detail = await unit_of_work.investigation.get_detail(incident_id, run_id)
    assert detail.triage_results
    assert detail.plans
    assert any(item.evidence_ids for item in detail.triage_results) or detail.evidence_attachments
    if detail.evidence_attachments:
        assert all(
            attachment.provenance.source_id or attachment.evidence_id
            for attachment in detail.evidence_attachments
        )
    _ = evidence_id
