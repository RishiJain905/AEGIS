"""Domain event builders for SCRIBE report generation."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.events import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _report_actor(*, session_id: str | None, incident_id: str) -> ActorRef:
    """Attribute the event to the SCRIBE session, or to the system when there was none.

    ``ActorRef.id`` is an ``AuthoredId``: the literal ``"SCRIBE"`` this previously used is
    not a valid namespaced identifier, so every report-generation event raised
    ``ContractValidationError`` before it could be appended — report generation could
    never complete. Agent-authored reports now cite their session id, matching every other
    agent-emitted event; deterministic reports have no session and are attributed to the
    system, with the incident as the subject either way.
    """
    if session_id is not None:
        return ActorRef(type=ActorType.AGENT, id=session_id)
    return ActorRef(type=ActorType.SYSTEM, id=incident_id)


def build_report_version_created_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str | None,
    task_id: str | None,
    trace_id: str,
    incident_id: str,
    report_version_id: str,
    version_number: int,
    checksum: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        event_id=event_id,
        type="report.version.created",
        run_id=run_id,
        sequence=sequence,
        sim_time=now,
        recorded_at=now,
        subject=ActorRef(type=ActorType.SYSTEM, id=incident_id),
        actor=_report_actor(session_id=session_id, incident_id=incident_id),
        trace_id=trace_id,
        causation_id=task_id,
        correlation_id=session_id,
        payload={
            "incidentId": incident_id,
            "reportVersionId": report_version_id,
            "versionNumber": version_number,
            "checksum": checksum,
            "sessionId": session_id,
            "taskId": task_id,
        },
    )


def build_report_generation_completed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str | None,
    task_id: str | None,
    trace_id: str,
    incident_id: str,
    report_version_id: str,
    grounding_fallback: bool,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        event_id=event_id,
        type="report.generation.completed",
        run_id=run_id,
        sequence=sequence,
        sim_time=now,
        recorded_at=now,
        subject=ActorRef(type=ActorType.SYSTEM, id=incident_id),
        actor=_report_actor(session_id=session_id, incident_id=incident_id),
        trace_id=trace_id,
        causation_id=task_id,
        correlation_id=session_id,
        payload={
            "incidentId": incident_id,
            "reportVersionId": report_version_id,
            "groundingFallback": grounding_fallback,
            "sessionId": session_id,
            "taskId": task_id,
        },
    )
