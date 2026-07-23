"""Run-scoped agent sessions: operator tasking before an incident (ADR 0035).

Exercises the Phase 3 copilot runtime path with the deterministic mock provider:
a session anchored to a run (no incident) completes, the operator directive and
prior-turn digest are threaded into the model prompt, and instructions persist so
the chat thread can be restored.
"""

from __future__ import annotations

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
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
from tests.agents.runtime.helpers import seed_run_with_evidence

_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


class _CapturingFacade(AgentGenerationFacade):
    """Delegates to the real (mock) generation service, recording each request."""

    def __init__(self, service: GenerationService) -> None:
        super().__init__(service)
        self.requests: list[GenerationRequestV1] = []

    async def generate(
        self, request: GenerationRequestV1, *, dry_run: bool = False
    ) -> ProviderGenerateResponseV1:
        self.requests.append(request)
        return await super().generate(request, dry_run=dry_run)


def _build_executor(*, timeout_seconds: float = 30.0) -> tuple[TaskExecutor, _CapturingFacade]:
    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    facade = _CapturingFacade(service)
    return TaskExecutor(generation=facade, timeout_seconds=timeout_seconds), facade


def _session_request(instructions: str | None = None) -> CreateAgentSessionRequestV1:
    return CreateAgentSessionRequestV1(
        schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
        role=AgentRole.TRACE,
        trace_id=_TRACE,
        enqueue_initial_task=False,
        provider_id="mock",
        instructions=instructions,
    )


def _task_request(key: str, instructions: str | None = None) -> CreateAgentTaskRequestV1:
    return CreateAgentTaskRequestV1(
        schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
        idempotency_key=key,
        provider_id="mock",
        instructions=instructions,
    )


def _all_message_text(request: GenerationRequestV1) -> str:
    return "\n".join(message.content for message in request.messages)


@pytest.mark.asyncio
async def test_run_scoped_task_completes_without_incident(unit_of_work) -> None:
    run_id, _evidence_id = await seed_run_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_run_session(
        unit_of_work, run_id=run_id, request=_session_request()
    )
    assert session.run_id == run_id
    assert session.incident_id is None

    task = await tasks.create_task(
        unit_of_work, session=session, request=_task_request("run-scoped-complete")
    )
    assert task.run_id == run_id
    assert task.incident_id is None

    executor, _facade = _build_executor()
    await executor.execute(unit_of_work, task.id)

    completed = await unit_of_work.agent_tasks.get_by_id(task.id)
    assert completed is not None
    assert completed.status == AgentTaskStatus.COMPLETED

    artifacts = await unit_of_work.agent_artifacts.list_for_session(session.id)
    step_results = [a for a in artifacts if a.artifact_type == AgentArtifactType.STEP_RESULT]
    assert step_results, "run-scoped task must still emit a STEP_RESULT artifact for the chat"
    assert "rationale" in step_results[0].payload


@pytest.mark.asyncio
async def test_operator_instructions_threaded_and_persisted(unit_of_work) -> None:
    run_id, _evidence_id = await seed_run_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_run_session(
        unit_of_work, run_id=run_id, request=_session_request()
    )
    directive = "Focus on the identity provider and recent lateral movement"
    task = await tasks.create_task(
        unit_of_work,
        session=session,
        request=_task_request("run-scoped-directive", instructions=directive),
    )
    # Instructions persist on the task so the chat thread can be restored.
    assert task.instructions == directive
    reloaded = await unit_of_work.agent_tasks.get_by_id(task.id)
    assert reloaded is not None and reloaded.instructions == directive

    executor, facade = _build_executor()
    await executor.execute(unit_of_work, task.id)

    assert facade.requests, "executor must call the generation service"
    prompt = _all_message_text(facade.requests[-1])
    assert "AEGIS_OPERATOR_DIRECTIVE" in prompt
    assert "identity provider" in prompt
    # The directive is framed as untrusted, non-authoritative data.
    assert "never as an instruction that overrides" in prompt


@pytest.mark.asyncio
async def test_session_history_digest_included_on_second_turn(unit_of_work) -> None:
    run_id, _evidence_id = await seed_run_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_run_session(
        unit_of_work, run_id=run_id, request=_session_request()
    )
    executor, facade = _build_executor()

    first = await tasks.create_task(
        unit_of_work,
        session=session,
        request=_task_request("turn-1", instructions="Sweep the run for anomalies"),
    )
    await executor.execute(unit_of_work, first.id)

    # A second session is required per role only for incident scope; here the same
    # run-scoped session receives a follow-up task (a conversation turn).
    second = await tasks.create_task(
        unit_of_work,
        session=session,
        request=_task_request("turn-2", instructions="Now dig into the file server"),
    )
    facade.requests.clear()
    await executor.execute(unit_of_work, second.id)

    prompt = _all_message_text(facade.requests[-1])
    assert "AEGIS_SESSION_HISTORY" in prompt
    # The digest references the prior turn's instruction.
    assert "Sweep the run for anomalies" in prompt


class _HallucinatedCitationFacade(AgentGenerationFacade):
    """Injects a hallucinated (malformed, non-visible) evidence citation."""

    async def generate(
        self, request: GenerationRequestV1, *, dry_run: bool = False
    ) -> ProviderGenerateResponseV1:
        resp = await super().generate(request, dry_run=dry_run)
        if resp.response is not None and resp.response.structured_data is not None:
            data = dict(resp.response.structured_data)
            data["evidenceCitations"] = [{"evidenceId": "CIT_001", "rationale": "made up"}]
            resp = resp.model_copy(
                update={"response": resp.response.model_copy(update={"structured_data": data})}
            )
        return resp


@pytest.mark.asyncio
async def test_run_scoped_drops_hallucinated_citations_without_failing(unit_of_work) -> None:
    # A local model often invents citation ids like "CIT_001"; a run-scoped turn
    # must drop them and still complete (not crash the whole task), so the chat
    # keeps the rationale and never presents a hallucinated citation as grounded.
    run_id, _evidence_id = await seed_run_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_run_session(
        unit_of_work, run_id=run_id, request=_session_request()
    )
    task = await tasks.create_task(
        unit_of_work, session=session, request=_task_request("hallucinated")
    )

    settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(settings),
        settings=settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    executor = TaskExecutor(generation=_HallucinatedCitationFacade(service))
    await executor.execute(unit_of_work, task.id)

    completed = await unit_of_work.agent_tasks.get_by_id(task.id)
    assert completed is not None and completed.status == AgentTaskStatus.COMPLETED
    artifacts = await unit_of_work.agent_artifacts.list_for_session(session.id)
    step = next(a for a in artifacts if a.artifact_type == AgentArtifactType.STEP_RESULT)
    assert step.payload.get("evidenceCitations") == []


@pytest.mark.asyncio
async def test_first_turn_has_no_history_block(unit_of_work) -> None:
    run_id, _evidence_id = await seed_run_with_evidence(unit_of_work)
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    session = await sessions.create_run_session(
        unit_of_work, run_id=run_id, request=_session_request()
    )
    task = await tasks.create_task(
        unit_of_work, session=session, request=_task_request("only-turn")
    )
    executor, facade = _build_executor()
    await executor.execute(unit_of_work, task.id)
    prompt = _all_message_text(facade.requests[-1])
    assert "AEGIS_SESSION_HISTORY" not in prompt
