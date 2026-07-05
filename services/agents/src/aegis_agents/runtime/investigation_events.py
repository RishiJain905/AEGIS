"""Investigation domain event builders."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _agent_actor(session_id: str) -> ActorRef:
    return ActorRef(type=ActorType.AGENT, id=session_id)


def build_triage_completed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    triage_id: str,
    incident_id: str,
    escalation: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.triage.completed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "triageId": triage_id,
            "escalation": escalation,
        },
        trace_id=trace_id,
    )


def build_plan_created_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    plan_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.plan.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "planId": plan_id,
        },
        trace_id=trace_id,
    )


def build_evidence_attached_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    attachment_id: str,
    incident_id: str,
    is_contradiction: bool,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.evidence.attached",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "attachmentId": attachment_id,
            "isContradiction": is_contradiction,
        },
        trace_id=trace_id,
    )


def build_graph_overlay_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    overlay_id: str,
    incident_id: str,
    highlight_count: int,
    edge_highlight_count: int,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "taskId": task_id,
        "incidentId": incident_id,
        "overlayId": overlay_id,
        "highlightCount": highlight_count,
        "edgeHighlightCount": edge_highlight_count,
    }
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.graph.overlay",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload=payload,
        trace_id=trace_id,
    )


def build_hypothesis_created_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    hypothesis_id: str,
    revision_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.hypothesis.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "hypothesisId": hypothesis_id,
            "revisionId": revision_id,
        },
        trace_id=trace_id,
    )


def build_hypothesis_revised_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    hypothesis_id: str,
    revision_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.hypothesis.revised",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "hypothesisId": hypothesis_id,
            "revisionId": revision_id,
        },
        trace_id=trace_id,
    )


def build_hypothesis_comparison_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    comparison_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.hypothesis.comparison.created",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "comparisonId": comparison_id,
        },
        trace_id=trace_id,
    )


def build_verification_requested_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    verification_id: str,
    hypothesis_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="investigation.verification.requested",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_agent_actor(session_id),
        subject=_agent_actor(session_id),
        payload={
            "schemaVersion": 1,
            "sessionId": session_id,
            "taskId": task_id,
            "incidentId": incident_id,
            "verificationId": verification_id,
            "hypothesisId": hypothesis_id,
        },
        trace_id=trace_id,
    )
