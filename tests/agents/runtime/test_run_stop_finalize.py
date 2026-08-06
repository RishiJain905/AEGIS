"""A stopped run must cancel every in-flight agent task, honestly and atomically.

Covers the run-stop finalizer: queued and running tasks reach a terminal
CANCELLED state with an attributable reason, the cancellation lands in the run's
event stream (so the replay and the after-action see it), incident-scoped
sessions go terminal while run-scoped lanes survive, and the status-guarded CAS
means a task the executor is concurrently completing is never clobbered. All
offline — the unit of work is a fake.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.runtime.errors import AgentRuntimeErrorCode
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.recovery import finalize_tasks_for_stopped_run
from aegis_contracts.agent_runtime import AgentTaskStatus, AgentTaskV1
from aegis_contracts.entities import AgentRole, AgentSessionState, AgentSessionV1, RunV1
from aegis_contracts.versioning import (
    AGENT_SESSION_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_SESSION_ID = "agent-session:ags_run_stop"


def _task(
    *,
    status: AgentTaskStatus,
    incident_id: str | None = None,
    session_id: str = _SESSION_ID,
) -> AgentTaskV1:
    return AgentTaskV1(
        schema_version=AGENT_TASK_SCHEMA_VERSION,
        id=new_runtime_id("atk"),
        session_id=session_id,
        run_id=_RUN_ID,
        incident_id=incident_id,
        status=status,
        attempt=1,
        idempotency_key=f"run-stop-{status.value}-{new_runtime_id('atk')}",
        trace_id=_TRACE_ID,
        provider_id="mock",
        created_at=_NOW,
        updated_at=_NOW,
        started_at=_NOW if status == AgentTaskStatus.RUNNING else None,
    )


def _session(
    *,
    incident_id: str | None = None,
    state: AgentSessionState = AgentSessionState.GATHERING,
) -> AgentSessionV1:
    return AgentSessionV1(
        schema_version=AGENT_SESSION_SCHEMA_VERSION,
        id=_SESSION_ID,
        run_id=_RUN_ID,
        incident_id=incident_id,
        role=AgentRole.TRACE,
        state=state,
        trace_id=_TRACE_ID,
        created_at=_NOW,
        updated_at=_NOW,
    )


class _FakeTaskRepo:
    def __init__(self, tasks: list[AgentTaskV1]) -> None:
        self.tasks = tasks
        self.transitions: list[tuple[AgentTaskV1, tuple[str, ...]]] = []
        #: Set to make the CAS lose, as it does when the executor got there first.
        self.claim_result = True

    async def list_for_run(
        self, run_id: str, *, statuses: tuple[str, ...] | None = None
    ) -> list[AgentTaskV1]:
        return [
            t
            for t in self.tasks
            if t.run_id == run_id and (statuses is None or t.status.value in statuses)
        ]

    async def claim_transition(
        self,
        task: AgentTaskV1,
        *,
        from_statuses: tuple[str, ...],
    ) -> bool:
        self.transitions.append((task, from_statuses))
        return self.claim_result


class _FakeSessions:
    """Stand-in for AgentSessionService: records transitions instead of writing."""

    def __init__(self, session: AgentSessionV1 | None) -> None:
        self.session = session
        self.transitions: list[tuple[AgentSessionV1, AgentSessionState]] = []

    async def get_by_id(self, session_id: str) -> AgentSessionV1 | None:
        return self.session

    async def update(self, updated: AgentSessionV1) -> AgentSessionV1:
        return updated

    async def transition(
        self,
        uow: Any,
        *,
        session: AgentSessionV1,
        to_state: AgentSessionState,
        reason: str,
        task_id: str | None,
        run_id: str,
    ) -> AgentSessionV1:
        self.transitions.append((session, to_state))
        return session.model_copy(update={"state": to_state})


def _uow(
    tasks: list[AgentTaskV1],
    *,
    session: AgentSessionV1 | None = None,
) -> Any:
    """The slice of the unit of work the finalizer actually touches."""

    class _Uow:
        pass

    uow = _Uow()
    uow.agent_tasks = _FakeTaskRepo(tasks)
    uow.appended: list[Any] = []
    uow.sessions = _FakeSessions(session)

    class _Events:
        async def next_sequence(self, run_id: str) -> int:
            return len(uow.appended) + 1

    class _Runs:
        async def get_by_id(self, run_id: str) -> RunV1:
            return RunV1(
                schema_version=RUN_SCHEMA_VERSION,
                id=_RUN_ID,
                scenario_version_id="scenario-version:test-v1",
                seed=42,
                status="stopped",
                started_at=_NOW,
                sim_time=_NOW,
                revision=1,
            )

    async def append_event(envelope: Any) -> Any:
        uow.appended.append(envelope)
        return envelope

    class _Transitions:
        async def add(self, transition: Any) -> Any:
            return transition

    uow.agent_sessions = uow.sessions
    uow.agent_transitions = _Transitions()
    uow.events = _Events()
    uow.runs = _Runs()
    uow.append_event = append_event
    return uow


@pytest.mark.asyncio
async def test_queued_and_running_tasks_are_cancelled_with_attributable_reasons() -> None:
    queued = _task(status=AgentTaskStatus.QUEUED)
    running = _task(status=AgentTaskStatus.RUNNING)
    uow = _uow([queued, running], session=_session())

    cancelled = await finalize_tasks_for_stopped_run(
        uow, run_id=_RUN_ID, sessions=uow.sessions
    )

    assert cancelled == 2
    by_id = {task.id: (task, from_statuses) for task, from_statuses in uow.agent_tasks.transitions}
    q_terminal, q_from = by_id[queued.id]
    r_terminal, r_from = by_id[running.id]
    assert q_terminal.status == AgentTaskStatus.CANCELLED
    assert q_terminal.error_code == AgentRuntimeErrorCode.TASK_CANCELLED.value
    assert q_terminal.error_message == "Run stopped before the task started"
    assert q_terminal.completed_at is not None
    assert q_from == (AgentTaskStatus.QUEUED.value,)
    assert r_terminal.status == AgentTaskStatus.CANCELLED
    assert r_terminal.error_message == "Run stopped while the task was in flight"
    assert r_from == (AgentTaskStatus.RUNNING.value,)


@pytest.mark.asyncio
async def test_each_cancellation_lands_in_the_event_stream_with_role_and_reason() -> None:
    queued = _task(status=AgentTaskStatus.QUEUED)
    running = _task(status=AgentTaskStatus.RUNNING)
    uow = _uow([queued, running], session=_session())

    await finalize_tasks_for_stopped_run(uow, run_id=_RUN_ID, sessions=uow.sessions)

    assert len(uow.appended) == 2
    for envelope in uow.appended:
        assert envelope.type == "agent.task.failed"
        assert envelope.payload["status"] == "cancelled"
        assert envelope.payload["role"] == "TRACE"
        assert envelope.payload["errorCode"] == AgentRuntimeErrorCode.TASK_CANCELLED.value
        assert envelope.payload["errorMessage"] in {
            "Run stopped before the task started",
            "Run stopped while the task was in flight",
        }


@pytest.mark.asyncio
async def test_incident_scoped_session_goes_terminal_but_run_scoped_lane_survives() -> None:
    incident_task = _task(
        status=AgentTaskStatus.RUNNING, incident_id="incident:inc_001"
    )
    lane_task = _task(status=AgentTaskStatus.RUNNING, incident_id=None)
    uow = _uow(
        [incident_task, lane_task],
        session=_session(incident_id="incident:inc_001"),
    )

    await finalize_tasks_for_stopped_run(uow, run_id=_RUN_ID, sessions=uow.sessions)

    # The incident-scoped session is cancelled; the run-scoped lane is untouched.
    assert len(uow.sessions.transitions) == 1
    session, to_state = uow.sessions.transitions[0]
    assert session.incident_id == "incident:inc_001"
    assert to_state == AgentSessionState.CANCELLED


@pytest.mark.asyncio
async def test_losing_the_cas_skips_the_cancellation() -> None:
    """A task the executor is concurrently completing is never clobbered: the CAS
    finds no row and the cancellation is skipped, with no event of its own."""
    running = _task(status=AgentTaskStatus.RUNNING)
    uow = _uow([running], session=_session())
    uow.agent_tasks.claim_result = False

    cancelled = await finalize_tasks_for_stopped_run(uow, run_id=_RUN_ID, sessions=uow.sessions)

    assert cancelled == 0
    assert uow.appended == []
    assert uow.sessions.transitions == []


@pytest.mark.asyncio
async def test_terminal_tasks_are_left_alone() -> None:
    completed = _task(status=AgentTaskStatus.COMPLETED)
    failed = _task(status=AgentTaskStatus.FAILED)
    uow = _uow([completed, failed], session=_session())

    cancelled = await finalize_tasks_for_stopped_run(uow, run_id=_RUN_ID, sessions=uow.sessions)

    assert cancelled == 0
    assert uow.agent_tasks.transitions == []
    assert uow.appended == []
