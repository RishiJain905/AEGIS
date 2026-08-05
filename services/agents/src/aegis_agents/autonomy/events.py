"""Domain events for the autonomous triage loop."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION


def build_autonomy_task_enqueued_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    session_id: str,
    task_id: str,
    trace_id: str,
    role: str,
    reason: str,
    alert_id: str | None,
    asset_id: str | None,
    sim_time: datetime,
) -> DomainEventEnvelopeV1:
    payload = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "taskId": task_id,
        "role": role,
        "reason": reason,
        "initiator": "autonomy",
    }
    if alert_id is not None:
        payload["alertId"] = alert_id
    if asset_id is not None:
        payload["assetId"] = asset_id
    return DomainEventEnvelopeV1(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        type="autonomy.task.enqueued",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=datetime.now(UTC),
        actor=ActorRef(type=ActorType.AGENT, id=session_id),
        subject=ActorRef(type=ActorType.AGENT, id=session_id),
        payload=payload,
        trace_id=trace_id,
    )
