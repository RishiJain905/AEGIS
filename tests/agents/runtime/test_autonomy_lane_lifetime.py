"""An autonomy lane must outlive its own successful turns.

Chrome QA drove run ``run_HAQWCJAZ9P7CVFZVKMNEH9WXQ5`` (OpenRouter, forward-deployed
RoE) and read "No WATCHTOWER activity yet" for the whole run. The DB said otherwise:
eight autonomous WATCHTOWER tasks were enqueued and executed. One completed — and
every task after it died instantly with ``INVALID_TRANSITION: completed -> gathering``.

The cause is an asymmetry between the two terminal paths of a turn. ``_fail_task``
already decides whether to terminate the session from the *session's* scope, with a
comment naming this exact hazard; the success path still decided from the *task's*
scope. An autonomy lane session is run-scoped (``incident_id is None``) and shared by
every triage turn in the run, but each turn carries the incident id of the case it
enriches (ADR 0037). So the first turn that succeeded read "incident-scoped" off the
task, completed the shared lane, and COMPLETED has no outgoing transitions — the lane
was dead for the rest of the run.

Offline: no database, no provider. The unit of work and the session service are fakes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.runtime.executor import TaskExecutor, _LoopOutcome, _PreparedTask
from aegis_agents.runtime.grounding import build_evidence_catalogue
from aegis_agents.runtime.registry import build_definition
from aegis_agents.runtime.state_machine import can_transition
from aegis_contracts.agent_runtime import AgentBudgetV1, AgentTaskStatus, AgentTaskV1
from aegis_contracts.entities import AgentRole, AgentSessionState, AutonomyInitiatorV1
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ModelConfigV1,
    ProviderFinishReason,
    ProviderGenerateResponseV1,
    ProviderUsageV1,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    AGENT_BUDGET_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    GENERATION_REQUEST_SCHEMA_VERSION,
    GENERATION_RESPONSE_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_LANE_SESSION_ID = "agent-session:ags_autonomy_watchtower"
_INCIDENT_ID = "incident:inc_det_ff3c1988978e876c4b12"
_NOW = datetime(2026, 8, 7, 6, 28, tzinfo=UTC)


def _runtime_id(prefix: str) -> str:
    return f"{prefix}_{1:026d}"


class _FakeRepo:
    def __init__(self, task: AgentTaskV1 | None = None) -> None:
        self.task = task

    async def get_by_id(self, _id: str) -> Any:
        return self.task

    async def next_sequence(self, _run_id: str) -> int:
        return 1

    async def update(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def add(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def claim_transition(self, _task: Any, *, from_statuses: tuple[str, ...]) -> bool:
        return True


class _FakeSessionLike:
    def expire_all(self) -> None:
        return None


class _FakeUow:
    def __init__(self, task: AgentTaskV1) -> None:
        self.session = _FakeSessionLike()
        self.agent_sessions = _FakeRepo()
        self.agent_artifacts = _FakeRepo()
        self.agent_tasks = _FakeRepo(task)
        self.events = _FakeRepo()
        self.runs = _FakeRepo()
        self.appended_events: list[Any] = []

    async def append_event(self, envelope: Any) -> Any:
        self.appended_events.append(envelope)
        return envelope

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _LaneSession:
    """A run-scoped autonomy lane: shared by every triage turn, bound to no case."""

    id = _LANE_SESSION_ID
    role = AgentRole.WATCHTOWER
    incident_id: str | None = None
    origin = AutonomyInitiatorV1.AUTONOMY


class _CaseSession:
    """An operator-tasked, incident-scoped session: one investigation, then terminal."""

    id = "agent-session:ags_operator_case"
    role = AgentRole.WATCHTOWER
    incident_id: str | None = _INCIDENT_ID
    origin = AutonomyInitiatorV1.OPERATOR


class _RecordingSessions:
    """The session service, minus persistence: records what the turn asked for."""

    def __init__(self) -> None:
        self.states: list[AgentSessionState] = []

    async def transition(
        self, _uow: Any, *, session: Any, to_state: AgentSessionState, **_kwargs: Any
    ) -> Any:
        self.states.append(to_state)
        return session


def _budget() -> AgentBudgetV1:
    return AgentBudgetV1(
        schema_version=AGENT_BUDGET_SCHEMA_VERSION,
        max_tokens=8000,
        max_latency_ms=60_000,
        max_cost_usd=1.0,
    )


def _task(session_id: str) -> AgentTaskV1:
    """An autonomy triage turn: scoped to the case it enriches (ADR 0037)."""
    return AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id=_runtime_id("atk"),
        session_id=session_id,
        run_id=_RUN_ID,
        incident_id=_INCIDENT_ID,
        idempotency_key="autonomy-alert:det-bd03901f085415dc01cd",
        status=AgentTaskStatus.RUNNING,
        attempt=1,
        trace_id=_runtime_id("trc"),
        provider_id="openrouter",
        initiator=AutonomyInitiatorV1.AUTONOMY,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _request() -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id=_runtime_id("gen"),
        trace_id=_runtime_id("trc"),
        provider_id="openrouter",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id="openrouter",
            model_id="openrouter-v1",
            prompt_version="phase20-watchtower-v1",
        ),
        messages=[
            GenerationMessageV1(
                role=GenerationMessageRole.SYSTEM, content="You are AEGIS WATCHTOWER."
            )
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={"type": "object"},
            strict=True,
            max_repair_attempts=1,
        ),
    )


def _answer() -> ProviderGenerateResponseV1:
    payload = {
        "rationale": "Unseen source activity on the SSO broker.",
        "confidence": 0.7,
        "evidenceCitations": [],
        "toolRequests": [],
    }
    return ProviderGenerateResponseV1(
        schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
        response=GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=_runtime_id("gen"),
            trace_id=_runtime_id("trc"),
            provider_id="openrouter",
            model_id="deepseek/deepseek-v4-flash-0731",
            prompt_version="phase20-watchtower-v1",
            content=json.dumps(payload),
            structured_data=payload,
            finish_reason=ProviderFinishReason.STOP,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
            latency_ms=7,
            completed_at=_NOW,
        ),
    )


async def _run_turn(session: Any) -> _RecordingSessions:
    """Persist one successful turn against ``session`` and report its transitions."""
    sessions = _RecordingSessions()
    executor = TaskExecutor(generation=None)  # type: ignore[arg-type]
    executor._sessions = sessions  # type: ignore[assignment]
    task = _task(session.id)
    prepared = _PreparedTask(
        task=task,
        session=session,
        run_id=_RUN_ID,
        agent_name="WATCHTOWER",
        definition=build_definition(AgentRole.WATCHTOWER, provider_id="openrouter"),
        budget=_budget(),
        incident_title="Unseen source activity detected",
        # The turn is incident-scoped: it enriches the case the detection engine
        # already opened for the alert's asset.
        run_scoped=False,
        visible_ids=set(),
        role_handler=None,
        request=_request(),
        evidence_catalogue=build_evidence_catalogue([]),
    )
    outcome = _LoopOutcome(
        response=_answer(),
        request=prepared.request,
        pending_tool_requests=[],
        executed_tool_count=1,
        iterations=1,
    )
    await executor._persist_result(_FakeUow(task), prepared, outcome)  # type: ignore[arg-type]
    return sessions


@pytest.mark.asyncio
async def test_a_successful_autonomy_turn_leaves_its_lane_re_runnable() -> None:
    """The regression: completing the shared lane strands every later triage."""
    sessions = await _run_turn(_LaneSession())

    assert AgentSessionState.COMPLETED not in sessions.states
    # It rests at VERIFYING, which the state machine lets the next turn re-enter.
    assert sessions.states[-1] is AgentSessionState.VERIFYING
    assert can_transition(sessions.states[-1], AgentSessionState.GATHERING)


@pytest.mark.asyncio
async def test_an_incident_scoped_session_still_completes() -> None:
    """The narrowing must not weaken the one-investigation-then-terminal guarantee."""
    sessions = await _run_turn(_CaseSession())

    assert sessions.states[-1] is AgentSessionState.COMPLETED
