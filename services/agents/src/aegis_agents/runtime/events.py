"""Agent domain event builders.

Every agent event carries two timestamps with distinct meaning (architecture
contract §7): ``sim_time`` is the run's VIRTUAL clock and must be supplied by the
caller from the run (``RunV1.sim_time``); ``recorded_at`` is the WALL-CLOCK instant
the event was persisted. Stamping ``sim_time`` with ``datetime.now()`` is a bug —
it renders agent activity ~204 days off (wall date minus the sim epoch) on the
replay/dossier timeline while alerts and operator commands sit at their true
sim-time offsets.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.entities import AgentSessionState
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _agent_actor(session_id: str) -> ActorRef:
    return ActorRef(type=ActorType.AGENT, id=session_id)


def build_session_started_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    trace_id: str,
    role: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.session.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={"schemaVersion": 1, "sessionId": session_id, "role": role},
        trace_id=trace_id,
    )


def build_session_state_changed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    trace_id: str,
    from_state: AgentSessionState,
    to_state: AgentSessionState,
    task_id: str | None,
    reason: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "fromState": from_state.value,
        "toState": to_state.value,
        "reason": reason,
    }
    if task_id is not None:
        payload["taskId"] = task_id
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.session.state_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload=payload,
        trace_id=trace_id,
    )


def build_task_started_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    sim_time: datetime,
    role: str | None = None,
) -> DomainEventEnvelopeV1:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "taskId": task_id,
    }
    if role is not None:
        payload["role"] = role
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.task.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload=payload,
        trace_id=trace_id,
    )


def build_task_completed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    status: str,
    sim_time: datetime,
    role: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> DomainEventEnvelopeV1:
    """The terminal event for a task: ``agent.task.completed`` or ``agent.task.failed``.

    ``role`` and the error fields are additive — the event tape reads them to say
    *which* agent failed and *why* instead of the generic "an agent could not
    finish its task". ``error_code``/``error_message`` are only meaningful on a
    failure, but the builder accepts them for any status and the caller decides.
    """
    event_type = "agent.task.completed" if status == "completed" else "agent.task.failed"
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "taskId": task_id,
        "status": status,
    }
    if role is not None:
        payload["role"] = role
    if error_code is not None:
        payload["errorCode"] = error_code
    if error_message is not None:
        payload["errorMessage"] = error_message
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload=payload,
        trace_id=trace_id,
    )


def build_tool_invoked_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    tool_name: str,
    status: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.tool.invoked",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "toolName": tool_name,
            "status": status,
        },
        trace_id=trace_id,
    )
