"""Task execution orchestrator."""

# ruff: noqa: E501

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
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
from aegis_agents.security.scenario_content import (
    build_commander_intent_message,
    build_operator_directive_message,
    build_scenario_data_message,
    build_session_history_message,
)
from aegis_agents.tools.executor import ToolExecutor
from aegis_agents.tools.handlers import ToolExecutionContext
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts import AgentSessionState
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
    AgentArtifactV1,
    AgentTaskStatus,
    EvidenceCitationV1,
    ToolInvocationStatus,
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


@dataclass
class _PreparedTask:
    """State carried from the claim/prepare phase into generation and persistence.

    ``session`` is pinned at GATHERING — the committed post-claim state. The
    persist phase transitions a *local copy* forward (HYPOTHESIZING/VERIFYING/…),
    so this object stays at GATHERING and remains the correct base for a failure
    transition: if a later phase aborts, its transaction is rolled back and the
    on-disk session is once again GATHERING, matching ``session`` here.
    """

    task: Any
    session: Any
    run_id: str
    agent_name: str
    definition: Any
    budget: Any
    incident_title: str | None
    run_scoped: bool
    visible_ids: set[str]
    role_handler: Any
    request: GenerationRequestV1


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
        """Execute one agent task with the model call held OUTSIDE any transaction.

        The task runs in three short transactions on ``uow``'s session:

        1. **Claim + prepare** — atomically claim QUEUED->RUNNING (exactly-once
           CAS), append the task-started event, and build the generation request,
           then COMMIT. Appending an event acquires the per-run
           ``pg_advisory_xact_lock`` (see ``PostgresEventRepository.next_sequence``);
           committing here releases it immediately.
        2. **Generation** — call the model with NO transaction open, so the
           advisory lock is free. This is the fix: the tick engine appends step
           events under the *same* per-run advisory lock, so a transaction held
           across a 60-120s model call froze the whole run. The generation facade
           is built with ``session=None`` (in-memory artifact repo) and never
           touches ``uow``'s session, so no transaction spans ``generate()``.
        3. **Persist** — grounding validation, tool execution, artifact + result
           events, mark the task terminal, then COMMIT (re-acquiring the advisory
           lock only for the few milliseconds those short writes take).

        ``uow`` stays caller-supplied — the API routes and the worker create it,
        and the SCRIBE routes create the task in the *same* uow before calling
        here, so the executor must use that session (a separate connection would
        not see the still-uncommitted task). The executor now owns the intra-task
        commits so the model call cannot span a transaction. On ANY failure a
        FAILED/TIMED_OUT task is persisted (committed) and an ``AgentRuntimeError``
        is re-raised: the interactive routes suppress it, the worker
        logs-and-continues.
        """
        import time

        started = time.perf_counter()
        agent_name = "unknown"
        status = "ok"
        tool_failure = False
        try:
            # Phase 1: claim, append started event, build request, commit.
            prepared = await self._claim_and_prepare(uow, task_id)
            if prepared is None:
                # Not found/not queued/claim lost -> no-op, exactly as before.
                return
            agent_name = prepared.agent_name

            # Phase 2: the model call, with NO open transaction / advisory lock.
            # Only the generation call is time-boxed: it is the minutes-long step,
            # and bounding it via cancellation while a transaction were open would
            # risk poisoning the connection. Tool execution in phase 3 is local,
            # fast DB work.
            try:
                response = await asyncio.wait_for(
                    self._generation.generate(prepared.request),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError as exc:
                await self._fail_and_commit(
                    uow,
                    prepared,
                    code=AgentRuntimeErrorCode.TASK_TIMEOUT,
                    message="Agent task timed out",
                )
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TASK_TIMEOUT,
                    message="Agent task timed out",
                    trace_id=prepared.task.trace_id,
                ) from exc
            except AgentRuntimeError as exc:
                await self._fail_and_commit(uow, prepared, code=exc.code, message=exc.message)
                raise
            except Exception as exc:
                await self._fail_and_commit(
                    uow,
                    prepared,
                    code=AgentRuntimeErrorCode.INTERNAL,
                    message=str(exc),
                )
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.INTERNAL,
                    message="Agent task failed",
                    trace_id=prepared.task.trace_id,
                ) from exc

            # Phase 3: persist results / tool calls / completion in a short txn.
            try:
                await self._persist_result(uow, prepared, response)
                await uow.commit()
            except AgentRuntimeError as exc:
                await self._fail_and_commit(uow, prepared, code=exc.code, message=exc.message)
                raise
            except Exception as exc:
                await self._fail_and_commit(
                    uow,
                    prepared,
                    code=AgentRuntimeErrorCode.INTERNAL,
                    message=str(exc),
                )
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.INTERNAL,
                    message="Agent task failed",
                    trace_id=prepared.task.trace_id,
                ) from exc
        except Exception:
            status = "error"
            raise
        finally:
            try:
                from aegis_observability.instrumentation import record_agent_task

                record_agent_task(
                    agent_name=agent_name,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    status=status,
                    tool_failure=tool_failure,
                )
            except Exception:  # noqa: BLE001
                pass

    async def _claim_and_prepare(
        self,
        uow: PostgresUnitOfWork,
        task_id: str,
    ) -> _PreparedTask | None:
        """Phase 1: claim the task, emit the started event, and build the request.

        Runs in a single short transaction that COMMITS before returning, so the
        per-run advisory lock (taken by the started-event append) is released
        before the model call. Returns ``None`` for the no-op cases (task missing
        from QUEUED, or a lost claim race). A failure while building the request
        (budget exceeded, cancellation) persists a FAILED task in this same
        transaction — the task is already claimed RUNNING, matching the pre-split
        single-transaction failure behavior — then re-raises.
        """
        task = await uow.agent_tasks.get_by_id(task_id)
        if task is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_NOT_FOUND,
                message=f"Agent task not found: {task_id}",
            )
        if task.status != AgentTaskStatus.QUEUED:
            return None

        session = await uow.agent_sessions.get_by_id(task.session_id)
        if session is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.SESSION_NOT_FOUND,
                message=f"Agent session not found: {task.session_id}",
                trace_id=task.trace_id,
            )
        agent_name = str(getattr(session, "role", None) or "unknown")
        try:
            from aegis_observability.context import merge_context

            merge_context(
                service="agents",
                operation="agent.task",
                agent_session_id=session.id,
                run_id=getattr(session, "run_id", None),
                incident_id=task.incident_id,
                trace_id=task.trace_id,
            )
        except Exception:  # noqa: BLE001
            pass

        # Run-scoped tasks (operator tasking before the first incident) carry no
        # incident; run_id is anchored on the session. Incident-scoped tasks must
        # still resolve their incident (a dangling incident_id is a data error).
        run_id = session.run_id
        incident = None
        if task.incident_id is not None:
            incident = await uow.incidents.get_by_id(task.incident_id)
            if incident is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.INCIDENT_NOT_FOUND,
                    message=f"Incident not found: {task.incident_id}",
                    trace_id=task.trace_id,
                )
        incident_title = incident.title if incident is not None else None
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
        # Atomic claim: exactly one executor may transition QUEUED -> RUNNING.
        # A losing racer (worker + inline API execute, or two workers) observes
        # zero rows updated and no-ops, so a task never executes twice.
        claimed = await uow.agent_tasks.claim_transition(running, from_statuses=("queued",))
        if not claimed:
            # Discard the read snapshot; nothing was written by this transaction.
            await uow.rollback()
            return None
        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.GATHERING,
            reason="task_started",
            task_id=task.id,
            run_id=run_id,
        )
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_task_started_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session.id,
                task_id=task.id,
                trace_id=task.trace_id,
            )
        )

        # Build the generation request within this same transaction. A failure
        # here (budget exceeded, cancellation) still persists a FAILED task: the
        # task is already claimed RUNNING, so we write the terminal failure into
        # the open transaction (alongside the claim + started event) and commit,
        # matching the pre-split behavior.
        try:
            request, run_scoped, visible_ids, role_handler = await self._build_request(
                uow,
                task=running,
                session=session,
                run_id=run_id,
                incident_title=incident_title,
                definition=definition,
                budget=budget,
            )
        except AgentRuntimeError as exc:
            await self._fail_task(
                uow,
                task=running,
                session=session,
                run_id=run_id,
                code=exc.code,
                message=exc.message,
            )
            await uow.commit()
            raise
        except Exception as exc:
            await self._fail_task(
                uow,
                task=running,
                session=session,
                run_id=run_id,
                code=AgentRuntimeErrorCode.INTERNAL,
                message=str(exc),
            )
            await uow.commit()
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.INTERNAL,
                message="Agent task failed",
                trace_id=running.trace_id,
            ) from exc

        # Commit the claim + started event, releasing the advisory lock BEFORE
        # the model call runs.
        await uow.commit()
        return _PreparedTask(
            task=running,
            session=session,
            run_id=run_id,
            agent_name=agent_name,
            definition=definition,
            budget=budget,
            incident_title=incident_title,
            run_scoped=run_scoped,
            visible_ids=visible_ids,
            role_handler=role_handler,
            request=request,
        )

    async def _build_request(
        self,
        uow: PostgresUnitOfWork,
        *,
        task: Any,
        session: Any,
        run_id: str,
        incident_title: str | None,
        definition: Any,
        budget: Any,
    ) -> tuple[GenerationRequestV1, bool, set[str], Any]:
        """Assemble the model request (reads only). Returns request + metadata.

        No event/lock-taking writes happen here, so it can share the claim
        transaction. Raises on cancellation or budget exhaustion, which the
        caller turns into a persisted FAILED task.
        """
        if task.id in self._cancelled:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TASK_CANCELLED,
                message="Agent task cancelled",
                trace_id=task.trace_id,
            )

        run_scoped = task.incident_id is None
        evidence = await uow.evidence.list_for_run(run_id)
        visible_ids = {item.id for item in evidence}
        check_budget(budget, trace_id=task.trace_id)

        role_handler = get_role_handler(session.role)
        # Run-scoped (chat) turns use the compact generic step schema, not the
        # role-specific investigation schema. The role schema only exists to feed
        # incident-keyed post-processing (skipped for run-scoped), and its size/
        # nesting hurts schema adherence for a local model. The generic schema
        # (rationale, confidence, evidence citations, tool requests) is exactly
        # what the chat renders, and small enough for reliable structured output.
        output_schema = (
            AGENT_STEP_OUTPUT_SCHEMA
            if run_scoped or role_handler is None
            else role_handler.output_schema()
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
        if run_scoped:
            # No incident yet: frame the turn around the live run and the operator's
            # directive, and pin the compact output shape for the chat.
            user_prompt = (
                f"Act as {session.role.value} for the current live run. Address the "
                "operator's directive using the run's alerts, telemetry, and evidence. "
                "Return grounded structured output: a concise rationale, a confidence "
                "in [0,1], evidence citations for any factual claim, and any tool "
                "requests you need."
            )

        # Scenario-data grounding: an incident title when incident-scoped, or a
        # run-scoped note (no incident opened yet) so the agent knows to sweep
        # run-level telemetry rather than assume an incident context exists.
        if run_scoped:
            scenario_data = build_scenario_data_message(
                {
                    "scope": "run",
                    "runId": run_id,
                    "note": (
                        "No incident has been opened yet. Work from run-level "
                        "alerts, telemetry, and evidence."
                    ),
                }
            )
        else:
            scenario_data = build_scenario_data_message(
                {"incidentTitle": incident_title or ""}
            )

        messages = [
            GenerationMessageV1(
                role=GenerationMessageRole.SYSTEM,
                content=system_prompt,
            ),
            GenerationMessageV1(
                role=GenerationMessageRole.USER,
                content=user_prompt,
            ),
            scenario_data,
        ]
        # Commander's intent (run-wide operator priorities) steers WHAT every role
        # prioritises for the whole engagement — applied to all roles, run-scoped and
        # incident-scoped alike. Untrusted, non-authoritative free text, delimited like
        # the operator directive. Absent when the operator skipped it (or on legacy runs).
        run = await uow.runs.get_by_id(run_id)
        commander_intent = getattr(run, "commander_intent", None) if run is not None else None
        if commander_intent:
            messages.append(build_commander_intent_message(commander_intent))
        # Multi-turn continuity: a bounded digest of prior turns in this session
        # so a run-scoped session feels like a conversation.
        history = await self._build_session_history(uow, session_id=session.id, before_task_id=task.id)
        if history is not None:
            messages.append(history)
        # Operator directive (untrusted free text) steers WHAT to investigate.
        if task.instructions:
            messages.append(build_operator_directive_message(task.instructions))

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
            messages=messages,
            structured_output=StructuredOutputSpecV1(
                schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
                json_schema=output_schema,
                strict=True,
                max_repair_attempts=1,
            ),
            capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
        )
        return request, run_scoped, visible_ids, role_handler

    async def _persist_result(
        self,
        uow: PostgresUnitOfWork,
        prepared: _PreparedTask,
        response: Any,
    ) -> None:
        """Phase 3: validate grounding, run tools, and persist the terminal state.

        All writes land in a short transaction the caller commits. The advisory
        lock is only re-taken by the event appends here, and only for the few
        milliseconds each short write holds it — never across the model call.
        """
        task = prepared.task
        # Advance a LOCAL copy of the session; ``prepared.session`` stays at
        # GATHERING so a failure can be recorded against the committed state.
        session = prepared.session
        run_id = prepared.run_id
        budget = prepared.budget
        visible_ids = prepared.visible_ids
        role_handler = prepared.role_handler
        run_scoped = prepared.run_scoped
        definition = prepared.definition
        request = prepared.request

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

        raw_citations = structured.get("evidenceCitations", [])
        if run_scoped:
            # A local model frequently invents citation ids (e.g. "CIT_001") that
            # aren't well-formed namespaced evidence ids, or cites evidence that
            # isn't visible in the run. For the interactive chat we DROP those
            # rather than hard-failing the whole turn — the grounded rationale
            # still lands, and only well-formed, visible citations survive, so no
            # hallucinated evidence is ever presented as grounded. The strict
            # audit path (incident-scoped) below is unchanged.
            citations = []
            kept: list[dict[str, Any]] = []
            for item in raw_citations:
                evidence_id = item.get("evidenceId")
                if not evidence_id or evidence_id not in visible_ids:
                    continue
                try:
                    citations.append(
                        EvidenceCitationV1(
                            schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                            evidence_id=evidence_id,
                            rationale=item.get("rationale", ""),
                        )
                    )
                except Exception:  # noqa: BLE001 - malformed id, treat as ungrounded
                    continue
                kept.append(item)
            structured["evidenceCitations"] = kept
        else:
            citations = [
                EvidenceCitationV1(
                    schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                    evidence_id=item["evidenceId"],
                    rationale=item.get("rationale", ""),
                )
                for item in raw_citations
            ]
            if citations:
                validate_citations(
                    citations, visible_evidence_ids=visible_ids, trace_id=task.trace_id
                )

        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.HYPOTHESIZING,
            reason="model_step_received",
            task_id=task.id,
            run_id=run_id,
        )
        session = await self._sessions.transition(
            uow,
            session=session,
            to_state=AgentSessionState.VERIFYING,
            reason="grounding_validated",
            task_id=task.id,
            run_id=run_id,
        )

        # Run-scoped tasks have no incident; pass "" so incident-keyed tools
        # resolve to "not found" and fail soft (caught below) while run-keyed
        # read tools (alerts/events/risk/evidence) work off ctx.run_id.
        ctx = ToolExecutionContext(
            uow=uow,
            session_id=session.id,
            task_id=task.id,
            incident_id=task.incident_id or "",
            run_id=run_id,
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
            tool_name = tool_request["name"]
            try:
                invocation = await self._tool_executor.invoke(
                    uow=uow,
                    definition=definition,
                    ctx=ctx,
                    tool_name=tool_name,
                    payload=tool_request.get("arguments", {}),
                )
                tool_status = invocation.status.value
            except AgentRuntimeError as exc:
                # Incident-scoped tasks keep the strict contract: a tool failure
                # fails the task. Run-scoped tasks (operator chat) fail soft — a
                # tool the model tried that needs an incident (e.g. BASTION's
                # proposal tool with no incident open) is recorded and streamed as
                # a failed/rejected chip, and the agent's grounded artifact still
                # lands so the operator gets a useful reply.
                if not run_scoped:
                    raise
                tool_status = (
                    ToolInvocationStatus.REJECTED.value
                    if exc.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED
                    else ToolInvocationStatus.FAILED.value
                )
            next_sequence = await uow.events.next_sequence(run_id)
            await uow.append_event(
                build_tool_invoked_event(
                    event_id=new_runtime_id("evt"),
                    run_id=run_id,
                    sequence=next_sequence,
                    session_id=session.id,
                    task_id=task.id,
                    trace_id=task.trace_id,
                    tool_name=tool_name,
                    status=tool_status,
                )
            )

        # Role post-processing writes incident-keyed investigation artifacts
        # (triage/hypotheses/proposals), so it only applies to incident-scoped
        # tasks. Run-scoped tasks still produce the STEP_RESULT artifact below,
        # which is what the chat renders.
        if role_handler is not None and not run_scoped:
            await role_handler.post_process(
                ctx=PostProcessContext(
                    uow=uow,
                    session_id=session.id,
                    task_id=task.id,
                    incident_id=task.incident_id or "",
                    run_id=run_id,
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

        # Incident-scoped sessions model one investigation and complete (terminal).
        # A run-scoped session is a conversation that hosts many turns, so it must
        # NOT go terminal after a turn — it rests at VERIFYING (a non-terminal state
        # that re-enters GATHERING when the next task starts, per the existing state
        # machine). This keeps the whole chat as one session (matching the prior-turn
        # digest) without weakening the terminal guarantees the state machine gives
        # incident-scoped sessions.
        if not run_scoped:
            session = await self._sessions.transition(
                uow,
                session=session,
                to_state=AgentSessionState.COMPLETED,
                reason="report_only_complete",
                task_id=task.id,
                run_id=run_id,
            )
        completed = task.model_copy(
            update={
                "status": AgentTaskStatus.COMPLETED,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        await uow.agent_tasks.update(completed)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_task_completed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session.id,
                task_id=task.id,
                trace_id=task.trace_id,
                status="completed",
            )
        )

    async def _build_session_history(
        self,
        uow: PostgresUnitOfWork,
        *,
        session_id: str,
        before_task_id: str,
        max_turns: int = 6,
    ) -> GenerationMessageV1 | None:
        """Bounded digest of prior completed turns in this session (chat memory).

        Returns the most recent ``max_turns`` prior tasks as a compact record of
        {instruction, status, rationale, tools}, wrapped as untrusted data so the
        model gets continuity without treating history as instructions. Returns
        ``None`` when there is no prior turn.
        """
        prior_tasks = [
            t
            for t in await uow.agent_tasks.list_for_session(session_id)
            if t.id != before_task_id and t.status == AgentTaskStatus.COMPLETED
        ]
        if not prior_tasks:
            return None
        recent = prior_tasks[-max_turns:]
        artifacts = await uow.agent_artifacts.list_for_session(session_id)
        step_by_task: dict[str, dict[str, Any]] = {}
        for artifact in artifacts:
            if artifact.artifact_type == AgentArtifactType.STEP_RESULT:
                step_by_task[artifact.task_id] = artifact.payload
        invocations = await uow.tool_invocations.list_for_session(session_id)
        tools_by_task: dict[str, list[str]] = {}
        for inv in invocations:
            tools_by_task.setdefault(inv.task_id, []).append(inv.tool_name)

        turns: list[dict[str, Any]] = []
        for t in recent:
            payload = step_by_task.get(t.id, {})
            rationale = str(payload.get("rationale", ""))[:500]
            turns.append(
                {
                    "instruction": (t.instructions or "")[:500],
                    "status": t.status.value,
                    "rationale": rationale,
                    "tools": tools_by_task.get(t.id, [])[:12],
                }
            )
        digest = json.dumps(turns, ensure_ascii=False, separators=(",", ":"))
        return build_session_history_message(digest)

    async def _fail_and_commit(
        self,
        uow: PostgresUnitOfWork,
        prepared: _PreparedTask,
        *,
        code: AgentRuntimeErrorCode,
        message: str,
    ) -> None:
        """Persist a terminal failure for a claimed task in its own transaction.

        Any partial writes from a failed persist phase are rolled back first, so
        the failure is recorded against the committed post-claim state (the
        on-disk session is GATHERING, matching ``prepared.session``). Commits so
        the FAILED/TIMED_OUT state survives even when the caller rolls back on the
        re-raised error (the worker) or suppresses it (the interactive routes).
        """
        await uow.rollback()
        await self._fail_task(
            uow,
            task=prepared.task,
            session=prepared.session,
            run_id=prepared.run_id,
            code=code,
            message=message,
        )
        await uow.commit()

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
