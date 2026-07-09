"""Approval workflow domain event builders."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _operator_actor(actor_id: str) -> ActorRef:
    return ActorRef(type=ActorType.OPERATOR, id=actor_id)


def build_proposal_approved_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    approval_id: str,
    revision_id: str,
    incident_id: str,
    comment: str = "",
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.approved",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "approvalId": approval_id,
            "revisionId": revision_id,
            "comment": comment,
        },
        trace_id=trace_id,
    )


def build_proposal_rejected_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    approval_id: str,
    revision_id: str,
    incident_id: str,
    reason: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.rejected",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "approvalId": approval_id,
            "revisionId": revision_id,
            "reason": reason,
        },
        trace_id=trace_id,
    )


def build_proposal_modified_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    previous_revision_id: str,
    new_revision_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.modified",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "previousRevisionId": previous_revision_id,
            "newRevisionId": new_revision_id,
        },
        trace_id=trace_id,
    )


def build_proposal_cancelled_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    revision_id: str,
    incident_id: str,
    reason: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.proposal.cancelled",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "revisionId": revision_id,
            "reason": reason,
        },
        trace_id=trace_id,
    )


def build_action_executed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    approval_id: str,
    executed_action_id: str,
    command_id: str,
    incident_id: str,
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="action.executed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "incidentId": incident_id,
            "proposalId": proposal_id,
            "approvalId": approval_id,
            "executedActionId": executed_action_id,
            "commandId": command_id,
        },
        trace_id=trace_id,
    )
