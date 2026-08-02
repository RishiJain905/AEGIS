"""Task execution orchestrator."""

# ruff: noqa: E501

from __future__ import annotations

import asyncio
import json
import time
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
from aegis_agents.runtime.run_state import summarize_run_state
from aegis_agents.runtime.session_service import AgentSessionService, _run_sim_time
from aegis_agents.runtime.state_machine import can_transition
from aegis_agents.runtime.tool_loop import (
    DEFAULT_TOOL_LOOP_MAX_ITERATIONS,
    MAX_TOOL_REQUESTS_PER_ITERATION,
    ToolRequest,
    bounded_results_payload,
    classify_tool_requests,
    describe_available_tools,
    parse_tool_requests,
    summarize_deferred_request,
    summarize_tool_result,
)
from aegis_agents.security.scenario_content import (
    MAX_SCENARIO_CONTENT_BYTES,
    build_available_tools_message,
    build_commander_intent_message,
    build_operator_directive_message,
    build_run_state_message,
    build_scenario_data_message,
    build_session_history_message,
    build_tool_budget_exhausted_message,
    build_tool_results_message,
)
from aegis_agents.tools.executor import ToolExecutor
from aegis_agents.tools.handlers import TOOL_HANDLERS, ToolExecutionContext
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY, ToolRegistry
from aegis_contracts import AgentSessionState
from aegis_contracts.agent_runtime import (
    AgentArtifactType,
    AgentArtifactV1,
    AgentTaskStatus,
    EvidenceCitationV1,
    ToolInvocationStatus,
)
from aegis_contracts.entities import AutonomyInitiatorV1
from aegis_contracts.errors import ContractValidationError
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

# Wall-clock the loop reserves out of the task timeout for the persist phase, so
# a task that spends its whole budget investigating still has room to write its
# results. Persist is short local DB work; this is deliberately generous.
LOOP_PERSIST_HEADROOM_SECONDS = 5.0

# Minimum time remaining before the loop is willing to start ANOTHER round. Below
# this there is not enough runway for a tool round plus the model call that would
# consume it, so the loop concludes with the answer it already holds rather than
# risking a timeout that would discard the whole turn.
MIN_LOOP_ITERATION_SECONDS = 15.0

# Slack between the provider's own budget and the ``wait_for`` that guards it.
# The provider stack must always run out of road FIRST: when it does it returns a
# real error (TIMEOUT/RETRY_EXHAUSTED) with a persisted artifact, whereas the
# wait_for merely kills it mid-flight. That distinction is what produced the
# operator-facing "Provider request was cancelled (PROVIDER_FAILURE)" — the
# provider had no deadline of its own, so the only thing that ever stopped it was
# this cancellation.
PROVIDER_BUDGET_HEADROOM_SECONDS = 2.0

# The generation contract bounds timeoutMs to [100, 600000].
_MIN_PROVIDER_BUDGET_MS = 100
_MAX_PROVIDER_BUDGET_MS = 600_000


def _with_provider_budget(
    request: GenerationRequestV1,
    *,
    wait_for_seconds: float,
) -> GenerationRequestV1:
    """Pin the request's total provider budget inside the caller's deadline.

    ``timeout_ms`` is the budget for the entire provider call — every retry and
    backoff included — so setting it here is what stops the retry loop from
    outliving the task that owns it.
    """
    budget_ms = int((wait_for_seconds - PROVIDER_BUDGET_HEADROOM_SECONDS) * 1000)
    clamped = max(_MIN_PROVIDER_BUDGET_MS, min(_MAX_PROVIDER_BUDGET_MS, budget_ms))
    return request.model_copy(update={"timeout_ms": clamped})


# Provider codes meaning the endpoint or the network let us down, so a later
# attempt has a real chance. OUTPUT_LIMIT_EXCEEDED is deliberately absent:
# retrying under the same token budget truncates the same way.
_RETRYABLE_PROVIDER_CODES = frozenset({"TIMEOUT", "RETRY_EXHAUSTED", "PROVIDER_UNAVAILABLE"})


def _provider_failure(error: Any, *, trace_id: str | None) -> AgentRuntimeError:
    """The runtime error an operator should read for a failed generation.

    ``STRUCTURED_OUTPUT_INVALID`` is separated from ``PROVIDER_FAILURE`` because
    collapsing them is a misdiagnosis with a real cost: it tells the operator the
    provider is at fault and sends them to check the endpoint, when what actually
    happened is that the model wrote something its own schema rejects. That is a
    property of the answer, not of the provider — and unlike most provider faults
    it is worth simply asking again, so it is reported retryable.
    """
    code = error.code.value
    details: dict[str, Any] = {"providerCode": code, **dict(error.details or {})}
    if code == "STRUCTURED_OUTPUT_INVALID":
        return AgentRuntimeError(
            code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
            message=f"Model returned malformed output: {error.message}",
            details=details,
            trace_id=trace_id,
            retryable=True,
        )
    return AgentRuntimeError(
        code=AgentRuntimeErrorCode.PROVIDER_FAILURE,
        message=error.message,
        details=details,
        trace_id=trace_id,
        retryable=code in _RETRYABLE_PROVIDER_CODES,
    )


def _invalid_model_output(
    exc: ContractValidationError,
    *,
    trace_id: str | None,
    summary: str,
) -> AgentRuntimeError:
    """A contract violation caused by the model's own answer, made presentable.

    A local model routinely invents identifiers — ``EVT-ALERT-001``,
    ``LOG-2024-0892-001`` — that are not AEGIS ids at all. Those reach the
    authored-id validators inside the domain contracts, which raise
    :class:`ContractValidationError` from deep in persistence. Left uncaught it
    surfaced as an opaque ``INTERNAL`` "Agent task failed" that named neither the
    id nor the model as the cause. The task still fails — a hallucinated citation
    must never be persisted as grounding — but it fails as a named, retryable
    model-output fault with the offending value in the error.
    """
    return AgentRuntimeError(
        code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
        message=f"{summary}: {exc.message}",
        details={"contractCode": exc.code.value, **dict(exc.details or {})},
        trace_id=trace_id,
        retryable=True,
    )


@dataclass
class _LoopOutcome:
    """What the multi-turn tool loop produced for the persist phase.

    ``response``/``request`` are the LAST usable pair — the model's final answer
    when the loop concluded normally, or the newest answer it managed to produce
    before a mid-loop failure. ``pending_tool_requests`` are the requests the loop
    did NOT run: state-changing ones (which belong to the proposal/approval
    pipeline) and anything left over when the loop stopped. The persist phase
    executes those exactly as it executed every tool request before the loop
    existed, so proposals still reach the approval gate.
    """

    response: Any
    request: GenerationRequestV1
    pending_tool_requests: list[dict[str, Any]]
    executed_tool_count: int
    iterations: int
    extra_tokens: int = 0
    extra_latency_ms: int = 0
    extra_cost_usd: float = 0.0


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
        tool_loop_max_iterations: int = DEFAULT_TOOL_LOOP_MAX_ITERATIONS,
    ) -> None:
        self._generation = generation
        self._registry = registry or DEFAULT_AGENT_REGISTRY
        self._tool_registry = tool_registry or DEFAULT_TOOL_REGISTRY
        self._tool_executor = ToolExecutor(registry=self._tool_registry)
        self._sessions = AgentSessionService(registry=self._registry)
        self._timeout_seconds = timeout_seconds
        self._tool_loop_max_iterations = max(0, tool_loop_max_iterations)
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
        2. **Generation (the bounded tool loop)** — call the model with NO
           transaction open, so the advisory lock is free. This is the fix: the
           tick engine appends step events under the *same* per-run advisory lock,
           so a transaction held across a 60-120s model call froze the whole run.
           The generation facade is built with ``session=None`` (in-memory
           artifact repo) and never touches ``uow``'s session, so no transaction
           spans ``generate()``. When the model asks for read-only tools, this
           phase runs them and calls the model again with their results — see
           :meth:`_run_tool_loop`. Each tool round commits its own short
           transaction, so the invariant holds unchanged: no transaction is ever
           open while a model is thinking.
        3. **Persist** — grounding validation, execution of the tool requests the
           loop deliberately did NOT run (state-changing ones, which reach the
           policy/approval pipeline exactly as before), artifact + result events,
           mark the task terminal, then COMMIT (re-acquiring the advisory lock
           only for the few milliseconds those short writes take).

        ``uow`` stays caller-supplied — the API routes and the worker create it,
        and the SCRIBE routes create the task in the *same* uow before calling
        here, so the executor must use that session (a separate connection would
        not see the still-uncommitted task). The executor now owns the intra-task
        commits so the model call cannot span a transaction. On ANY failure a
        FAILED/TIMED_OUT task is persisted (committed) and an ``AgentRuntimeError``
        is re-raised: the interactive routes suppress it, the worker
        logs-and-continues.
        """
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

            # Phase 2: the model calls, with NO open transaction / advisory lock
            # held across any of them. The loop may run read-only tools between
            # calls; each of those commits its own short transaction before the
            # next model call, so the per-run advisory lock is never held while a
            # model is thinking. Only generation is time-boxed: it is the
            # minutes-long step, and bounding it via cancellation while a
            # transaction were open would risk poisoning the connection.
            try:
                outcome = await self._run_tool_loop(uow, prepared)
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
                await self._persist_result(uow, prepared, outcome)
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

    async def _run_tool_loop(
        self,
        uow: PostgresUnitOfWork,
        prepared: _PreparedTask,
    ) -> _LoopOutcome:
        """Phase 2: generate, run read-only tools, feed results back, repeat.

        Control flow, and every way out of it:

        * Generate. If the answer carries no tool requests, that IS the answer —
          identical to the pre-loop single-shot path.
        * Otherwise split the requests by the registry's tool class. READ-class
          requests run now; everything else is deferred to the persist phase,
          which routes proposals through policy and human approval. The loop can
          only ever hand a READ-class request to the tool executor, so it is
          structurally incapable of executing a state change.
        * Append the (bounded) results and generate again.

        Termination, in the order checked:

        (a) the model asks for no tools, or asks only for tools already run with
            identical arguments — it has nothing new to learn, so it concludes;
        (b) the iteration cap is reached — the loop spends one final model call,
            preceded by an explicit "your budget is exhausted, answer now" note,
            so a capped task still produces a conclusion rather than silence;
        (c) too little of the task's time budget remains for another round plus
            the model call that would consume it — the leftover requests fall
            through to the persist phase, which is exactly the old behavior.

        Failure is soft after the first call: a provider error, timeout, or
        budget exhaustion mid-loop keeps the newest good response and proceeds to
        persist. The loop can only improve a turn; it must never destroy one that
        already has a usable answer. The FIRST generation is different — a
        failure there leaves nothing to persist, so it propagates and fails the
        task exactly as it did before.
        """
        deadline = time.monotonic() + self._timeout_seconds
        request = _with_provider_budget(prepared.request, wait_for_seconds=self._timeout_seconds)
        response = await asyncio.wait_for(
            self._generation.generate(request),
            timeout=self._timeout_seconds,
        )
        outcome = _LoopOutcome(
            response=response,
            request=request,
            pending_tool_requests=[],
            executed_tool_count=0,
            iterations=0,
        )
        if self._tool_loop_max_iterations < 1:
            outcome.pending_tool_requests = [
                item.as_payload() for item in parse_tool_requests(self._safe_structured(response))
            ]
            return outcome

        messages = list(request.messages)
        executed: set[str] = set()
        pending: list[ToolRequest] = []
        pending_keys: set[str] = set()
        budget = prepared.budget

        def defer(items: list[ToolRequest]) -> None:
            for item in items:
                if item.key in executed or item.key in pending_keys:
                    continue
                pending_keys.add(item.key)
                pending.append(item)

        while True:
            requests = parse_tool_requests(self._safe_structured(response))
            if not requests:
                break
            runnable, deferred = classify_tool_requests(requests, registry=self._tool_registry)
            defer(deferred)
            fresh = [item for item in runnable if item.key not in executed][
                :MAX_TOOL_REQUESTS_PER_ITERATION
            ]
            if not fresh:
                # Every read the model asked for has already been answered this
                # task. Running it again would return the same rows, so the only
                # useful move is to let the answer we have stand.
                break
            if outcome.iterations >= self._tool_loop_max_iterations:
                break
            if time.monotonic() + MIN_LOOP_ITERATION_SECONDS >= deadline:
                # Out of runway. Hand the reads back to the persist phase so they
                # are still recorded, matching pre-loop single-shot behavior.
                defer(runnable)
                break
            if prepared.task.id in self._cancelled:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TASK_CANCELLED,
                    message="Agent task cancelled",
                    trace_id=prepared.task.trace_id,
                )

            results = await self._execute_loop_tools(
                uow,
                prepared,
                fresh,
                iteration=outcome.iterations + 1,
            )
            for item in fresh:
                executed.add(item.key)
            outcome.executed_tool_count += len(fresh)
            outcome.iterations += 1

            results.extend(summarize_deferred_request(item) for item in deferred)
            exhausted = outcome.iterations >= self._tool_loop_max_iterations
            messages = [
                *messages,
                build_tool_results_message(
                    bounded_results_payload(results, max_bytes=MAX_SCENARIO_CONTENT_BYTES),
                    rounds_remaining=self._tool_loop_max_iterations - outcome.iterations,
                ),
            ]
            if exhausted:
                messages = [*messages, build_tool_budget_exhausted_message()]

            remaining = deadline - time.monotonic() - LOOP_PERSIST_HEADROOM_SECONDS
            follow_up = _with_provider_budget(
                request.model_copy(
                    update={"request_id": new_runtime_id("gen"), "messages": messages}
                ),
                wait_for_seconds=max(1.0, remaining),
            )
            try:
                check_budget(budget, trace_id=prepared.task.trace_id)
                next_response = await asyncio.wait_for(
                    self._generation.generate(follow_up),
                    timeout=max(1.0, remaining),
                )
                if next_response.error is not None:
                    raise _provider_failure(next_response.error, trace_id=prepared.task.trace_id)
            except Exception:  # noqa: BLE001 - timeout, provider error, or budget
                # Fail soft: keep the last good answer. The tools we ran are
                # already committed, so the trail survives even though the model
                # never got to reason over this round's results.
                break

            # Bank the usage of the answer being superseded. The persist phase adds
            # the surviving response's own usage, so the two together are the true
            # cost of the task and nothing is counted twice.
            superseded = response.response if response.response else None
            superseded_usage = superseded.usage if superseded else None
            outcome.extra_tokens += superseded_usage.total_tokens if superseded_usage else 0
            outcome.extra_latency_ms += superseded.latency_ms if superseded else 0
            outcome.extra_cost_usd += (
                superseded_usage.estimated_cost_usd
                if superseded_usage and superseded_usage.estimated_cost_usd
                else 0.0
            )
            budget = apply_usage(
                budget,
                tokens=superseded_usage.total_tokens if superseded_usage else 0,
                latency_ms=superseded.latency_ms if superseded else 0,
                cost_usd=(
                    superseded_usage.estimated_cost_usd
                    if superseded_usage and superseded_usage.estimated_cost_usd
                    else 0.0
                ),
            )
            request = follow_up
            response = next_response
            outcome.request = follow_up
            outcome.response = next_response
            if exhausted:
                break

        # Anything the final answer still asks for and the loop never ran goes to
        # the persist phase, which handles it exactly as the single-shot runtime
        # always did.
        defer(parse_tool_requests(self._safe_structured(outcome.response)))
        outcome.pending_tool_requests = [item.as_payload() for item in pending]
        return outcome

    async def _execute_loop_tools(
        self,
        uow: PostgresUnitOfWork,
        prepared: _PreparedTask,
        requests: list[ToolRequest],
        *,
        iteration: int,
    ) -> list[dict[str, Any]]:
        """Run one round of read-only tools, each in its own short transaction.

        Every invocation commits before the next model call, so the per-run
        advisory lock taken by the tool-invoked event append is held for
        milliseconds and never spans generation.

        An in-loop tool failure never fails the task, for any scope. The strict
        incident-scoped contract — a failed tool fails the task — still governs
        the tools the model asks for in its FINAL answer, which the persist phase
        runs. Inside the loop the calls are exploratory: telling the model its
        query was rejected and letting it adapt is the whole point, and the failed
        attempt is still persisted as an audit row.
        """
        ctx = ToolExecutionContext(
            uow=uow,
            session_id=prepared.session.id,
            task_id=prepared.task.id,
            incident_id=prepared.task.incident_id or "",
            run_id=prepared.run_id,
            trace_id=prepared.task.trace_id,
            visible_evidence_ids=prepared.visible_ids,
        )
        results: list[dict[str, Any]] = []
        for request in requests:
            output: dict[str, Any] | None = None
            error_message: str | None = None
            try:
                invocation = await self._tool_executor.invoke(
                    uow=uow,
                    definition=prepared.definition,
                    ctx=ctx,
                    tool_name=request.name,
                    payload=request.arguments,
                    loop_iteration=iteration,
                )
                status = invocation.status.value
                output = invocation.output_payload
            except AgentRuntimeError as exc:
                # The executor already wrote the rejected/failed audit row and
                # left the session usable, so it commits with the event below.
                status = (
                    ToolInvocationStatus.REJECTED.value
                    if exc.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED
                    else ToolInvocationStatus.FAILED.value
                )
                error_message = exc.message
            except Exception as exc:  # noqa: BLE001 - a handler raising anything else
                # No audit row was written and the transaction may be poisoned
                # (a handler can raise mid-flush), so discard it before writing
                # the event that records the attempt.
                await uow.rollback()
                status = ToolInvocationStatus.FAILED.value
                error_message = str(exc)
            await self._append_tool_event(uow, prepared, tool_name=request.name, status=status)
            await uow.commit()
            results.append(
                summarize_tool_result(
                    request=request,
                    status=status,
                    output=output,
                    error_message=error_message,
                )
            )
        return results

    async def _append_tool_event(
        self,
        uow: PostgresUnitOfWork,
        prepared: _PreparedTask,
        *,
        tool_name: str,
        status: str,
    ) -> None:
        next_sequence = await uow.events.next_sequence(prepared.run_id)
        await uow.append_event(
            build_tool_invoked_event(
                event_id=new_runtime_id("evt"),
                run_id=prepared.run_id,
                sequence=next_sequence,
                session_id=prepared.session.id,
                task_id=prepared.task.id,
                trace_id=prepared.task.trace_id,
                tool_name=tool_name,
                status=status,
                sim_time=await _run_sim_time(uow, prepared.run_id),
            )
        )

    @staticmethod
    def _safe_structured(response: Any) -> dict[str, Any] | None:
        """Best-effort structured payload, for loop control only.

        The persist phase owns the strict reading (and raises PROVIDER_FAILURE on
        a response with nothing usable). Here a missing or malformed payload just
        means "no tool requests", so a bad response reaches that strict path
        instead of exploding inside the loop.
        """
        if response is None or getattr(response, "error", None) is not None:
            return None
        inner = getattr(response, "response", None)
        if inner is None:
            return None
        structured = inner.structured_data
        if structured is None and inner.content:
            try:
                structured = json.loads(inner.content)
            except (TypeError, ValueError):
                return None
        return structured if isinstance(structured, dict) else None

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

        # Once the task is claimed RUNNING, it MUST reach a committed terminal
        # state (or a committed ready-to-run prepared task) — never be left
        # orphaned in 'running'. The session-start, started event, and request
        # build are all funnelled: any failure here (a terminal/un-transitionable
        # session, budget, cancellation, unexpected error) persists a terminal
        # task and commits, alongside the claim, matching the pre-split behavior.
        try:
            # A run-scoped lane/chat session that already rests at GATHERING (from
            # a prior failed turn — run-scoped sessions are never terminated by a
            # failure, see _fail_task) needs no transition; otherwise advance
            # QUEUED/VERIFYING -> GATHERING for this turn.
            if session.state != AgentSessionState.GATHERING:
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
                    sim_time=await _run_sim_time(uow, run_id),
                )
            )
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
            #
            # The tool paragraph is what makes the loop reachable. The snapshot is
            # bounded by construction, so a question about anything it does not
            # carry (event search, graph paths, risk scores) is answerable only if
            # the agent knows it may ask for a tool and get the results back.
            user_prompt = (
                f"Act as {session.role.value} for the current live run. Address the "
                "operator's directive using the AEGIS_RUN_STATE snapshot below, which "
                "lists the run's alerts, incidents, and evidence as they stand now. "
                "Answer from that snapshot; do not report that something is absent "
                "unless its list there is empty. If answering needs data the snapshot "
                "does not carry, request read-only tools from AEGIS_AVAILABLE_TOOLS: "
                "they run immediately and their results come back to you for a "
                "follow-up turn, so investigate first and answer once you have what "
                "you need. When you can answer, return an empty toolRequests array. "
                "Return grounded structured output: a concise rationale, a confidence "
                "in [0,1], and evidence citations for any factual claim."
            )

        # Scenario-data grounding: an incident title when incident-scoped, or a
        # pointer to the run-state snapshot when run-scoped.
        #
        # This block used to be the ONLY grounding a run-scoped turn received, and
        # it asserted "No incident has been opened yet" with no run data attached.
        # Since generation is single-shot (model tool requests run after the reply
        # and never feed back), an operator asking "summarise the current alerts"
        # got a context whose one concrete statement was an assertion of absence,
        # and correctly answered that there was nothing to triage while the run had
        # live alerts. The snapshot below is what actually grounds the turn.
        run_state_message = None
        if run_scoped:
            alerts = await uow.alerts.list_by_run(run_id)
            incidents = await uow.incidents.list_by_run(run_id)
            run_state_message = build_run_state_message(
                summarize_run_state(
                    run_id=run_id,
                    alerts=alerts,
                    incidents=incidents,
                    evidence=evidence,
                )
            )
            scenario_data = build_scenario_data_message(
                {
                    "scope": "run",
                    "runId": run_id,
                    "note": (
                        "The AEGIS_RUN_STATE block below is the authoritative "
                        "snapshot of this run. Ground every claim in it."
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
        if run_state_message is not None:
            messages.append(run_state_message)
        if run_scoped:
            # Scoped to run-scoped turns for the same reason the run-state snapshot
            # is: incident-scoped turns are the strict, fixture-replayable audit
            # path, and their request fingerprints key recorded provider responses.
            # Those roles get their tool requests from role-shaped output schemas
            # instead — and now, thanks to the loop, actually see the results.
            messages.append(
                build_available_tools_message(
                    describe_available_tools(
                        self._tool_registry.model_visible_tools(session.role),
                        allowed_tools=definition.allowed_tools,
                        executable_tools=TOOL_HANDLERS.keys(),
                    )
                )
            )
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
        outcome: _LoopOutcome,
    ) -> None:
        """Phase 3: validate grounding, run tools, and persist the terminal state.

        All writes land in a short transaction the caller commits. The advisory
        lock is only re-taken by the event appends here, and only for the few
        milliseconds each short write holds it — never across the model call.

        The tools run here are the ones the loop deliberately left alone:
        state-changing requests, which must go through policy and human approval,
        plus anything left over when the loop stopped early. Read-only tools the
        loop already ran are not re-run — their results are what the model just
        reasoned over.
        """
        response = outcome.response
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
        request = outcome.request

        if response.error is not None:
            raise _provider_failure(response.error, trace_id=task.trace_id)
        assert response.response is not None
        structured = response.response.structured_data
        if structured is None and response.response.content:
            # The provider stack normally hands over a validated payload; this is
            # the last-resort read for a response that carried only text. A model
            # that wrote prose here is a malformed-output fault, not a crash.
            try:
                structured = json.loads(response.response.content)
            except (TypeError, ValueError) as exc:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
                    message="Model returned malformed output: response was not valid JSON",
                    details={"error": str(exc)},
                    trace_id=task.trace_id,
                    retryable=True,
                ) from exc
        if not isinstance(structured, dict):
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
                message="Model returned no structured agent step output",
                trace_id=task.trace_id,
                retryable=True,
            )

        # Every model call the task made counts against the session budget, not
        # just the last one, or a looping task would under-report its true cost.
        usage = response.response.usage
        budget = apply_usage(
            budget,
            tokens=(usage.total_tokens if usage else 0) + outcome.extra_tokens,
            latency_ms=response.response.latency_ms + outcome.extra_latency_ms,
            cost_usd=(usage.estimated_cost_usd if usage and usage.estimated_cost_usd else 0.0)
            + outcome.extra_cost_usd,
        )
        await uow.agent_sessions.update(session, budget=budget)

        raw_citations = structured.get("evidenceCitations", [])
        malformed_citations = not isinstance(raw_citations, list)
        if malformed_citations:
            # The schema asks for a list of objects; a local model sometimes sends
            # a bare object, a string, or null. Iterating that raised TypeError out
            # of the loop as an opaque INTERNAL crash. Each path below now gets the
            # answer its own contract calls for: the chat drops the grounding and
            # keeps the reply, the audit path reports a named model-output fault.
            raw_citations = []
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
                if not isinstance(item, dict):
                    continue
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
            # The strict audit path. A citation id the model invented is rejected
            # here rather than allowed to raise out of the contract layer: the
            # turn still fails (hallucinated grounding must never be persisted as
            # if it were real), but as a named model-output fault naming the id,
            # not as an opaque INTERNAL error from inside persistence.
            if malformed_citations:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
                    message=(
                        "Model returned evidenceCitations that is not a list of "
                        "citation objects"
                    ),
                    details={"receivedType": type(structured["evidenceCitations"]).__name__},
                    trace_id=task.trace_id,
                    retryable=True,
                )
            try:
                citations = [
                    EvidenceCitationV1(
                        schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                        evidence_id=item["evidenceId"],
                        rationale=item.get("rationale", ""),
                    )
                    for item in raw_citations
                ]
            except ContractValidationError as exc:
                raise _invalid_model_output(
                    exc,
                    trace_id=task.trace_id,
                    summary="Model cited an evidence id that is not a valid AEGIS identifier",
                ) from exc
            except (KeyError, TypeError, AttributeError) as exc:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.STRUCTURED_OUTPUT_INVALID,
                    message="Model returned malformed evidence citations",
                    details={"error": str(exc)},
                    trace_id=task.trace_id,
                    retryable=True,
                ) from exc
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
        # The mock provider's role fallback only applies to a task that asked for
        # nothing at all. A task whose loop already ran tools has a real trail, and
        # synthesizing more would double-record it.
        tool_requests = outcome.pending_tool_requests
        no_tool_activity = not tool_requests and outcome.executed_tool_count == 0
        if no_tool_activity and definition.provider_id == "mock":
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
                # Operator-tasked incident work keeps the strict contract: a tool
                # failure fails the task. Run-scoped tasks (operator chat) fail soft
                # — a tool the model tried that needs an incident (e.g. BASTION's
                # proposal tool with no incident open) is recorded and streamed as
                # a failed/rejected chip, and the agent's grounded artifact still
                # lands so the operator gets a useful reply. Autonomy turns fail
                # soft for the same reason even when scoped to the case they
                # enrich: nobody is watching a background lane, and losing the
                # whole triage because one tool errored is strictly worse than
                # recording the failure and keeping the grounded artifact.
                if not run_scoped and task.initiator is not AutonomyInitiatorV1.AUTONOMY:
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
                    sim_time=await _run_sim_time(uow, run_id),
                )
            )

        # Role post-processing writes incident-keyed investigation artifacts
        # (triage/hypotheses/proposals), so it only applies to incident-scoped
        # tasks. Run-scoped tasks still produce the STEP_RESULT artifact below,
        # which is what the chat renders.
        if role_handler is not None and not run_scoped:
            # Role post-processing feeds the model's own payload into domain
            # contracts (alert ids, asset ids, evidence ids). Every one of those
            # fields is authored-id validated, so a hallucinated value raises out
            # of the contract layer mid-write. Containing it here covers all six
            # roles at once and keeps the failure legible instead of INTERNAL.
            try:
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
            except ContractValidationError as exc:
                raise _invalid_model_output(
                    exc,
                    trace_id=task.trace_id,
                    summary=(
                        "Model output contained an identifier this run does not "
                        f"recognise for {session.role.value} results"
                    ),
                ) from exc

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
                sim_time=await _run_sim_time(uow, run_id),
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
        # Session handling on failure:
        # - Run-scoped lane/chat sessions (incident_id is None: autonomy lanes and
        #   operator copilot chats) host many turns and MUST survive a failed turn
        #   — symmetric with the success path, which also keeps run-scoped sessions
        #   non-terminal. Terminating them would kill the whole autonomy lane and
        #   strand its other queued tasks. So we leave the session untouched.
        # - Incident-scoped sessions model one investigation and go terminal.
        # A guard keeps this defensive: if the session cannot transition to the
        # target (already terminal, e.g. a legacy orphan), skip it rather than
        # raising — a claimed task must still reach its terminal state.
        # Keyed on the SESSION, not the task: an autonomy lane turn carries the
        # incident id of the case it enriches while its lane session stays
        # run-scoped, and failing that one turn must not terminate the lane.
        session_run_scoped = session.incident_id is None
        target_state: AgentSessionState | None
        if session_run_scoped:
            target_state = None
        elif code == AgentRuntimeErrorCode.TASK_CANCELLED:
            target_state = AgentSessionState.CANCELLED
        else:
            target_state = AgentSessionState.FAILED
        if target_state is not None and can_transition(session.state, target_state):
            await self._sessions.transition(
                uow,
                session=session,
                to_state=target_state,
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
                sim_time=await _run_sim_time(uow, run_id),
            )
        )
