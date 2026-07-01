"""Unit tests for streaming envelope mapping."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1, EventTypeRegistry
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION, REALTIME_MESSAGE_SCHEMA_VERSION
from aegis_event_streaming.envelope import (
    build_realtime_envelope,
    envelope_to_redis_fields,
    redis_fields_to_envelope,
)


def test_envelope_round_trip() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    event = DomainEventEnvelopeV1(
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        sequence=1,
        type="sim.run.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        payload={"schemaVersion": EventTypeRegistry.payload_schema_version("sim.run.started")},
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
    )
    envelope = build_realtime_envelope(event, stream_message_id="1-0", published_at=now)
    assert envelope.schema_version == REALTIME_MESSAGE_SCHEMA_VERSION
    fields = envelope_to_redis_fields(envelope)
    restored = redis_fields_to_envelope(fields)
    assert restored.event.event_id == event.event_id
    assert restored.stream_message_id == "1-0"
