"""Proposal and policy domain event builders."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _agent_actor(session_id: str) -> ActorRef:
    return ActorRef(type=ActorType.AGENT, id=session_id)


def build_proposal_created_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    proposal_id: str,
    revision_id: str,
    incident_id: str,
    action_class: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "revisionId": revision_id,
            "actionClass": action_class,
        },
        trace_id=trace_id,
    )


def build_policy_evaluated_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    proposal_id: str,
    revision_id: str,
    incident_id: str,
    outcome: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.policy_evaluated",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "revisionId": revision_id,
            "outcome": outcome,
        },
        trace_id=trace_id,
    )


def build_incident_state_changed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    trace_id: str,
    incident_id: str,
    previous_state: str,
    new_state: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="incident.state_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_agent_actor(session_id),
        subject=ActorRef(type=ActorType.SYSTEM, id=incident_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "previousState": previous_state,
            "newState": new_state,
        },
        trace_id=trace_id,
    )
