"""Task execution orchestrator."""

# ruff: noqa: E501

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.registry import PostProcessContext, get_role_handler
from aegis_agents.runtime.budget import apply_usage, check_budget
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.events import (
    build_task_completed_event,
    build_task_started_event,
    build_tool_invoked_event,
)
from aegis_agents.runtime.grounding import validate_citations
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.registry import (
    DEFAULT_AGENT_REGISTRY,
    AgentDefinitionRegistry,
    build_definition,
)
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.tools.executor import ToolExecutor
from aegis_agents.tools.handlers import ToolExecutionContext
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts import AgentSessionState
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
    AgentArtifactV1,
    AgentTaskStatus,
    EvidenceCitationV1,
)
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderCapability,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    AGENT_ARTIFACT_SCHEMA_VERSION,
    EVIDENCE_CITATION_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork

AGENT_STEP_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidenceCitations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "evidenceId": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["evidenceId"],
                "additionalProperties": False,
            },
        },
        "toolRequests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rationale", "confidence", "evidenceCitations", "toolRequests"],
    "additionalProperties": False,
}

DEFAULT_TASK_TIMEOUT_SECONDS = 30.0


class TaskExecutor:
    def __init__(
        self,
        *,
        generation: AgentGenerationFacade,
        registry: AgentDefinitionRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        timeout_seconds: float = DEFAULT_TASK_TIMEOUT_SECONDS,
    ) -> None:
        self._generation = generation
        self._registry = registry or DEFAULT_AGENT_REGISTRY
        self._tool_executor = ToolExecutor(registry=tool_registry)
        self._sessions = AgentSessionService(registry=self._registry)
        self._timeout_seconds = timeout_seconds
        self._cancelled: set[str] = set()

    def request_cancel(self, task_id: str) -> None:
        self._cancelled.add(task_id)

    async def execute(self, uow: PostgresUnitOfWork, task_id: str) -> None:
        task = await uow.agent_tasks.get_by_id(task_id)
        if task is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_NOT_FOUND,
                message=f"Agent task not found: {task_id}",
            )
        if task.status != AgentTaskStatus.QUEUED:
            return

        session = await uow.agent_sessions.get_by_id(task.session_id)
        if session is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.SESSION_NOT_FOUND,
                message=f"Agent session not found: {task.session_id}",
                trace_id=task.trace_id,
            )
        incident = await uow.incidents.get_by_id(task.incident_id)
        if incident is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INCIDENT_NOT_FOUND,
                message=f"Incident not found: {task.incident_id}",
                trace_id=task.trace_id,
            )
        definition = build_definition(session.role, provider_id=task.provider_id)
        budget = await uow.agent_sessions.get_budget(session.id)
        if budget is None:
            budget = definition.default_budget

        now = datetime.now(UTC)
        running = task.model_copy(
            update={
                "status": AgentTaskStatus.RUNNING,
                "started_at": now,
                "updated_at": now,
            }
        )
        await uow.agent_tasks.update(running)
        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.GATHERING,
            reason="task_started",
            task_id=task.id,
            run_id=incident.run_id,
        )
        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_task_started_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                session_id=session.id,
                task_id=task.id,
                trace_id=task.trace_id,
            )
        )

        try:
            await asyncio.wait_for(
                self._run_task_body(
                    uow=uow,
                    task=running,
                    session=session,
                    incident_run_id=incident.run_id,
                    definition=definition,
                    budget=budget,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            await self._fail_task(
                uow,
                task=running,
                session=session,
                run_id=incident.run_id,
                code=AgentRuntimeErrorCode.TASK_TIMEOUT,
                message="Agent task timed out",
            )
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_TIMEOUT,
                message="Agent task timed out",
                trace_id=task.trace_id,
            ) from exc
        except AgentRuntimeError as exc:
            await self._fail_task(
                uow,
                task=running,
                session=session,
                run_id=incident.run_id,
                code=exc.code,
                message=exc.message,
            )
            raise
        except Exception as exc:
            await self._fail_task(
                uow,
                task=running,
                session=session,
                run_id=incident.run_id,
                code=AgentRuntimeErrorCode.INTERNAL,
                message=str(exc),
            )
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INTERNAL,
                message="Agent task failed",
                trace_id=task.trace_id,
            ) from exc

    async def _run_task_body(
        self,
        *,
        uow: PostgresUnitOfWork,
        task: Any,
        session: Any,
        incident_run_id: str,
        definition: Any,
        budget: Any,
    ) -> None:
        if task.id in self._cancelled:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_CANCELLED,
                message="Agent task cancelled",
                trace_id=task.trace_id,
            )

        evidence = await uow.evidence.list_for_run(incident_run_id)
        visible_ids = {item.id for item in evidence}
        check_budget(budget, trace_id=task.trace_id)

        role_handler = get_role_handler(session.role)
        output_schema = (
            role_handler.output_schema() if role_handler is not None else AGENT_STEP_OUTPUT_SCHEMA
        )
        system_prompt = (
            role_handler.system_prompt()
            if role_handler is not None
            else "You are the AEGIS generic agent runtime. Return grounded structured output."
        )
        user_prompt = (
            "Perform bounded TRACE investigation for the incident."
            if role_handler is not None and session.role.value == "TRACE"
            else "Perform WATCHTOWER triage for the incident."
            if role_handler is not None and session.role.value == "WATCHTOWER"
            else "Generate competing evidence-grounded hypotheses for the incident."
            if role_handler is not None and session.role.value == "ORACLE"
            else "Propose evidence-grounded response options for the incident."
            if role_handler is not None and session.role.value == "BASTION"
            else "Explain policy evaluation context for pending proposals."
            if role_handler is not None and session.role.value == "WARDEN"
            else "Generate an evidence-linked after-action incident summary."
            if role_handler is not None and session.role.value == "SCRIBE"
            else "Perform one investigation step for the incident."
        )

        request = GenerationRequestV1(
            schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
            request_id=new_runtime_id("gen"),
            trace_id=task.trace_id,
            provider_id=definition.provider_id,
            model_config_ref=ModelConfigV1(
                schema_version=MODEL_CONFIG_SCHEMA_VERSION,
                provider_id=definition.provider_id,
                model_id=definition.model_id,
                prompt_version=definition.prompt_version,
            ),
            messages=[
                GenerationMessageV1(
                    role=GenerationMessageRole.SYSTEM,
                    content=system_prompt,
                ),
                GenerationMessageV1(
                    role=GenerationMessageRole.USER,
                    content=user_prompt,
                ),
            ],
            structured_output=StructuredOutputSpecV1(
                schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
                json_schema=output_schema,
                strict=True,
                max_repair_attempts=1,
            ),
            capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
        )
        response = await self._generation.generate(request)
        if response.error is not None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.PROVIDER_FAILURE,
                message=response.error.message,
                details={"providerCode": response.error.code.value},
                trace_id=task.trace_id,
                retryable=response.error.code.value
                in {"TIMEOUT", "RETRY_EXHAUSTED", "PROVIDER_UNAVAILABLE"},
            )
        assert response.response is not None
        structured = response.response.structured_data
        if structured is None and response.response.content:
            structured = json.loads(response.response.content)
        if structured is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.PROVIDER_FAILURE,
                message="Provider returned no structured agent step output",
                trace_id=task.trace_id,
            )

        usage = response.response.usage
        budget = apply_usage(
            budget,
            tokens=usage.total_tokens if usage else 0,
            latency_ms=response.response.latency_ms,
            cost_usd=usage.estimated_cost_usd if usage and usage.estimated_cost_usd else 0.0,
        )
        await uow.agent_sessions.update(session, budget=budget)

        citations = [
            EvidenceCitationV1(
                schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                evidence_id=item["evidenceId"],
                rationale=item.get("rationale", ""),
            )
            for item in structured.get("evidenceCitations", [])
        ]
        if citations:
            validate_citations(citations, visible_evidence_ids=visible_ids, trace_id=task.trace_id)

        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.HYPOTHESIZING,
            reason="model_step_received",
            task_id=task.id,
            run_id=incident_run_id,
        )
        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.VERIFYING,
            reason="grounding_validated",
            task_id=task.id,
            run_id=incident_run_id,
        )

        ctx = ToolExecutionContext(
            uow=uow,
            session_id=session.id,
            task_id=task.id,
            incident_id=task.incident_id,
            run_id=incident_run_id,
            trace_id=task.trace_id,
            visible_evidence_ids=visible_ids,
        )
        tool_requests = structured.get("toolRequests", [])
        if not tool_requests and definition.provider_id == "mock":
            if role_handler is not None and session.role.value == "WATCHTOWER":
                tool_requests = [{"name": "list_alerts", "arguments": {}}]
            elif role_handler is not None and session.role.value == "TRACE":
                tool_requests = [{"name": "search_events", "arguments": {"limit": 200}}]
            elif role_handler is not None and session.role.value == "ORACLE":
                tool_requests = [
                    {"name": "list_existing_evidence", "arguments": {}},
                    {"name": "list_hypotheses", "arguments": {}},
                ]
            elif role_handler is not None and session.role.value == "BASTION":
                tool_requests = [
                    {"name": "list_existing_evidence", "arguments": {}},
                    {"name": "list_hypotheses", "arguments": {}},
                    {"name": "get_risk_scores", "arguments": {}},
                ]
            elif role_handler is not None and session.role.value == "WARDEN":
                tool_requests = [{"name": "list_proposals", "arguments": {}}]
            elif role_handler is not None and session.role.value == "SCRIBE":
                tool_requests = [
                    {"name": "list_existing_evidence", "arguments": {}},
                    {"name": "list_hypotheses", "arguments": {}},
                    {"name": "list_proposals", "arguments": {}},
                    {"name": "search_events", "arguments": {"limit": 200}},
                ]
            else:
                tool_requests = [{"name": "list_evidence", "arguments": {}}]

        for tool_request in tool_requests:
            if task.id in self._cancelled:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TASK_CANCELLED,
                    message="Agent task cancelled",
                    trace_id=task.trace_id,
                )
            invocation = await self._tool_executor.invoke(
                uow=uow,
                definition=definition,
                ctx=ctx,
                tool_name=tool_request["name"],
                payload=tool_request.get("arguments", {}),
            )
            next_sequence = await uow.events.next_sequence(incident_run_id)
            await uow.append_event(
                build_tool_invoked_event(
                    event_id=new_runtime_id("evt"),
                    run_id=incident_run_id,
                    sequence=next_sequence,
                    session_id=session.id,
                    task_id=task.id,
                    trace_id=task.trace_id,
                    tool_name=invocation.tool_name,
                    status=invocation.status.value,
                )
            )

        if role_handler is not None:
            await role_handler.post_process(
                ctx=PostProcessContext(
                    uow=uow,
                    session_id=session.id,
                    task_id=task.id,
                    incident_id=task.incident_id,
                    run_id=incident_run_id,
                    trace_id=task.trace_id,
                    idempotency_key=task.idempotency_key,
                    visible_evidence_ids=visible_ids,
                ),
                structured=structured,
            )

        artifact = AgentArtifactV1(
            schema_version=AGENT_ARTIFACT_SCHEMA_VERSION,
            id=new_runtime_id("aaf"),
            task_id=task.id,
            session_id=session.id,
            artifact_type=AgentArtifactType.STEP_RESULT,
            payload=structured,
            generation_artifact_id=request.request_id,
            created_at=datetime.now(UTC),
        )
        await uow.agent_artifacts.add(artifact)

        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.COMPLETED,
            reason="report_only_complete",
            task_id=task.id,
            run_id=incident_run_id,
        )
        completed = task.model_copy(
            update={
                "status": AgentTaskStatus.COMPLETED,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        await uow.agent_tasks.update(completed)
        next_sequence = await uow.events.next_sequence(incident_run_id)
        await uow.append_event(
            build_task_completed_event(
                event_id=new_runtime_id("evt"),
                run_id=incident_run_id,
                sequence=next_sequence,
                session_id=session.id,
                task_id=task.id,
                trace_id=task.trace_id,
                status="completed",
            )
        )

    async def _fail_task(
        self,
        uow: PostgresUnitOfWork,
        *,
        task: Any,
        session: Any,
        run_id: str,
        code: AgentRuntimeErrorCode,
        message: str,
    ) -> None:
        failed = task.model_copy(
            update={
                "status": AgentTaskStatus.FAILED
                if code != AgentRuntimeErrorCode.TASK_TIMEOUT
                else AgentTaskStatus.TIMED_OUT,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
                "error_code": code.value,
                "error_message": message,
            }
        )
        await uow.agent_tasks.update(failed)
        terminal_state = (
            AgentSessionState.CANCELLED
            if code == AgentRuntimeErrorCode.TASK_CANCELLED
            else AgentSessionState.FAILED
        )
        await self._sessions.transition(
            uow,
            session=session,
            to_state=terminal_state,
            reason=code.value.lower(),
            task_id=task.id,
            run_id=run_id,
        )
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_task_completed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session.id,
                task_id=task.id,
                trace_id=task.trace_id,
                status=failed.status.value,
            )
        )
