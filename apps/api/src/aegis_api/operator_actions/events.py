"""Domain event builders for operator direct actions and rules-of-engagement changes.

These share the run's ``(run_id, sequence)`` event stream and flow through the existing
outbox -> WebSocket path, so the ops feed, replay, and after-action all observe operator
initiative exactly like agent activity. Execution itself reuses the approval workflow's
``action.executed`` / ``policy.evaluated`` events (emitted inside the reused internals), so
replay cannot tell an operator-authorized execution apart from an approver-authorized one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _operator_actor(actor_id: str) -> ActorRef:
    return ActorRef(type=ActorType.OPERATOR, id=actor_id)


def _asset_subject(asset_id: str) -> ActorRef:
    return ActorRef(type=ActorType.ASSET, id=asset_id)


def build_operator_action_proposed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    proposal_id: str,
    incident_id: str,
    scenario_command: str,
    action_class: str,
    target_asset_id: str,
    justification: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "proposalId": proposal_id,
        "incidentId": incident_id,
        "scenarioCommand": scenario_command,
        "actionClass": action_class,
        "targetAssetId": target_asset_id,
        # The reason the operator gave — typed into the consequence gate for Class 2/3,
        # synthesized by the console for auto-executing Class 0/1. It lived only on the
        # proposal row, so the audit trail — the feed, replay, the after-action — recorded
        # *that* a Class 2 containment ran but never *why*, which is the one thing an audit
        # trail exists for. Never empty: the request contract requires a non-blank reason.
        "justification": justification,
        "initiator": "operator",
    }
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="operator.action.proposed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_operator_actor(actor_id),
        subject=_asset_subject(target_asset_id),
        payload=payload,
        trace_id=trace_id,
    )


def build_run_roe_changed_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    previous_roe: str,
    new_roe: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="run.roe_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "previousRoe": previous_roe,
            "newRoe": new_roe,
        },
        trace_id=trace_id,
    )
