"""Deterministic provider modes, outage behavior, and agent failure isolation."""

from __future__ import annotations

import os

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import (
    AgentTaskStatus,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderCapability,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.registry import ProviderRegistry
from aegis_model_provider.service import GenerationService
from tests.agents.runtime.helpers import seed_incident_with_evidence

pytestmark = [pytest.mark.failure_injection, pytest.mark.asyncio]


def _request(provider_id: str) -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id=provider_id,
            model_id=f"{provider_id}-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="System prompt"),
            GenerationMessageV1(role=GenerationMessageRole.USER, content="Summarize"),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "confidence"],
                "additionalProperties": False,
            },
            strict=True,
            max_repair_attempts=0,
        ),
        capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
    )


def _service(settings: ProviderSettings, registry: ProviderRegistry) -> GenerationService:
    return GenerationService(
        registry=registry,
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )


@pytest.mark.parametrize("provider_id", ["mock", "recorded"])
async def test_deterministic_provider_modes(provider_id: str) -> None:
    settings = ProviderSettings()
    service = _service(settings, build_provider_registry(settings))
    first = await service.generate(_request(provider_id), dry_run=True)
    second = await service.generate(_request(provider_id), dry_run=True)
    assert first.error is None and second.error is None
    assert first.response is not None and second.response is not None
    assert first.response.structured_data == second.response.structured_data


async def test_completely_unavailable_provider_is_structured_and_core_db_operates(
    unit_of_work,
) -> None:
    settings = ProviderSettings(AEGIS_PROVIDER_DEFAULT="mock")
    service = _service(settings, ProviderRegistry({}, default_provider_id="unavailable"))
    result = await service.generate(_request("unavailable"), dry_run=True)
    assert result.response is None
    assert result.error is not None
    assert result.error.code.value == "VALIDATION_FAILED"

    incident_id, run_id, _ = await seed_incident_with_evidence(unit_of_work)
    await unit_of_work.commit()
    assert await unit_of_work.incidents.get_by_id(incident_id) is not None
    run = await unit_of_work.runs.get_by_id(run_id)
    assert run is not None and run.status == "running"


async def test_one_failed_agent_session_cannot_corrupt_run_or_peer_session(
    unit_of_work,
) -> None:
    incident_id, run_id, _ = await seed_incident_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()

    async def create_task(provider_id: str, trace_suffix: str):
        session = await sessions.create_session(
            unit_of_work,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=AgentRole.TRACE,
                trace_id=f"trc_01ARZ3NDEKTSV4RRFFQ69G5F{trace_suffix}",
                enqueue_initial_task=False,
                provider_id=provider_id,
            ),
        )
        task = await tasks.create_task(
            unit_of_work,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key=f"phase34-{provider_id}",
                provider_id=provider_id,
            ),
        )
        return session, task

    failed_session, failed_task = await create_task("unavailable", "A5")
    healthy_session, healthy_task = await create_task("mock", "A6")
    settings = ProviderSettings()
    executor = TaskExecutor(
        generation=AgentGenerationFacade(_service(settings, build_provider_registry(settings)))
    )
    with pytest.raises(AgentRuntimeError) as exc_info:
        await executor.execute(unit_of_work, failed_task.id)
    assert exc_info.value.code == AgentRuntimeErrorCode.PROVIDER_FAILURE
    await executor.execute(unit_of_work, healthy_task.id)

    failed = await tasks.get_task(unit_of_work, failed_task.id)
    healthy = await tasks.get_task(unit_of_work, healthy_task.id)
    assert failed.status == AgentTaskStatus.FAILED
    assert healthy.status == AgentTaskStatus.COMPLETED
    failed_detail = await sessions.get_detail(unit_of_work, failed_session.id)
    healthy_detail = await sessions.get_detail(unit_of_work, healthy_session.id)
    assert failed_detail.session.state.value == "failed"
    assert healthy_detail.session.state.value == "completed"
    run = await unit_of_work.runs.get_by_id(run_id)
    assert run is not None and run.status == "running"


@pytest.mark.skipif(
    not os.environ.get("AEGIS_PROVIDER_OPENAI_API_KEY"),
    reason="live provider mode requires AEGIS_PROVIDER_OPENAI_API_KEY and is not a release gate",
)
async def test_live_provider_mode_when_explicitly_configured() -> None:
    settings = ProviderSettings()
    result = await _service(settings, build_provider_registry(settings)).generate(
        _request("openai"), dry_run=True
    )
    assert result.error is None


@pytest.mark.skipif(
    os.environ.get("AEGIS_PROVIDER_LOCAL_SKIP", "1") == "1",
    reason="local provider mode requires an explicitly configured compatible endpoint",
)
async def test_local_provider_mode_when_explicitly_configured() -> None:
    settings = ProviderSettings()
    result = await _service(settings, build_provider_registry(settings)).generate(
        _request("openai-compatible"), dry_run=True
    )
    assert result.error is None
