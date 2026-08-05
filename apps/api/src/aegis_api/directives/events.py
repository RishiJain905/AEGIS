"""Domain events for standing directives (Phase 7).

``directive.created`` / ``directive.deleted`` are operator-attributed lifecycle events;
``directive.triggered`` is emitted by the autonomy loop when a new alert matches an active
directive and an auto-task is enqueued (initiator=autonomy), so replay / the ops feed can
show which standing tasking reacted to which evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def _operator_event(
    *,
    event_type: str,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    payload: dict[str, object],
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=ActorRef(type=ActorType.OPERATOR, id=actor_id),
        subject=ActorRef(type=ActorType.OPERATOR, id=actor_id),
        payload={"schemaVersion": 1, **payload},
        trace_id=trace_id,
    )


def build_directive_created_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    directive_id: str,
    text: str,
    scope_asset_ids: list[str],
    scope_zone_ids: list[str],
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return _operator_event(
        event_type="directive.created",
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        actor_id=actor_id,
        trace_id=trace_id,
        payload={
            "directiveId": directive_id,
            "text": text,
            "scopeAssetIds": scope_asset_ids,
            "scopeZoneIds": scope_zone_ids,
            "initiator": "operator",
        },
        sim_time=sim_time,
    )


def build_directive_deleted_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    actor_id: str,
    trace_id: str,
    directive_id: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return _operator_event(
        event_type="directive.deleted",
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        actor_id=actor_id,
        trace_id=trace_id,
        payload={"directiveId": directive_id, "initiator": "operator"},
        sim_time=sim_time,
    )


def build_directive_triggered_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    trace_id: str,
    directive_id: str,
    alert_id: str,
    asset_id: str,
    task_id: str,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="directive.triggered",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=ActorRef(type=ActorType.AGENT, id="agent-session:autonomy"),
        subject=ActorRef(type=ActorType.AGENT, id="agent-session:autonomy"),
        payload={
            "schemaVersion": 1,
            "directiveId": directive_id,
            "alertId": alert_id,
            "assetId": asset_id,
            "taskId": task_id,
            "initiator": "autonomy",
        },
        trace_id=trace_id,
    )
