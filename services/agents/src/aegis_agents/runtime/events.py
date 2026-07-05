"""Agent domain event builders."""

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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.session.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
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
        sim_time=now,
        recorded_at=now,
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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.task.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={"schemaVersion": 1, "sessionId": session_id, "taskId": task_id},
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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    event_type = "agent.task.completed" if status == "completed" else "agent.task.failed"
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={"schemaVersion": 1, "sessionId": session_id, "taskId": task_id, "status": status},
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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="agent.tool.invoked",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
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
