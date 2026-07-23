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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "proposalId": proposal_id,
        "incidentId": incident_id,
        "scenarioCommand": scenario_command,
        "actionClass": action_class,
        "targetAssetId": target_asset_id,
        "initiator": "operator",
    }
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="operator.action.proposed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
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
) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="run.roe_changed",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=_operator_actor(actor_id),
        subject=_operator_actor(actor_id),
        payload={
            "schemaVersion": 1,
            "previousRoe": previous_roe,
            "newRoe": new_roe,
        },
        trace_id=trace_id,
    )
