"""Full WATCHTOWER, TRACE, and ORACLE flow integration test."""

from __future__ import annotations

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.oracle.coordinator import OracleCoordinator
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import AgentTaskStatus
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.versioning import (
    TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
    TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
)
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
async def test_oracle_flow_generates_grounded_hypotheses(unit_of_work) -> None:
    incident_id, run_id, alert_ids, evidence_id = await seed_investigation_run(unit_of_work)
    watchtower = WatchtowerCoordinator()
    watchtower_request = TriggerWatchtowerRequestV1(
        schema_version=TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
        run_id=run_id,
        alert_ids=alert_ids,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id="mock",
        idempotency_key="integration-watchtower-oracle-001",
    )
    watchtower_result = await watchtower.trigger_for_run(unit_of_work, watchtower_request)
    assert watchtower_result.trace_session_id is not None

    trace_tasks = await unit_of_work.agent_tasks.list_for_session(
        watchtower_result.trace_session_id
    )
    await _build_executor().execute(unit_of_work, trace_tasks[0].id)

    oracle = OracleCoordinator()
    oracle_request = TriggerOracleRequestV1(
        schema_version=TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
        run_id=run_id,
        incident_id=incident_id,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provider_id="mock",
        idempotency_key="integration-oracle-001",
    )
    oracle_result = await oracle.trigger_for_run(unit_of_work, oracle_request)
    oracle_tasks = await unit_of_work.agent_tasks.list_for_session(oracle_result.oracle_session_id)
    await _build_executor().execute(unit_of_work, oracle_tasks[0].id)
    completed = await AgentTaskService().get_task(unit_of_work, oracle_tasks[0].id)
    assert completed.status == AgentTaskStatus.COMPLETED

    detail = await unit_of_work.investigation.get_detail(incident_id, run_id)
    assert len(detail.hypotheses) >= 2
    assert detail.hypothesis_revisions
    assert detail.hypothesis_comparisons
    if detail.hypothesis_revisions:
        revision = detail.hypothesis_revisions[0]
        assert revision.confidence.explanation
        assert revision.claims or revision.supporting_evidence_ids
    _ = evidence_id
