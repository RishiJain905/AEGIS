"""Realtime message envelope mapping for Redis Streams."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from aegis_contracts import DomainEventEnvelopeV1, RealtimeMessageEnvelopeV1, parse_contract
from aegis_contracts.versioning import REALTIME_MESSAGE_SCHEMA_VERSION

from aegis_event_streaming.stream_names import DEFAULT_CHANNEL


def build_realtime_envelope(
    event: DomainEventEnvelopeV1,
    *,
    channel: str = DEFAULT_CHANNEL,
    stream_message_id: str | None = None,
    published_at: datetime | None = None,
) -> RealtimeMessageEnvelopeV1:
    return RealtimeMessageEnvelopeV1(
        schema_version=REALTIME_MESSAGE_SCHEMA_VERSION,
        channel=channel,
        stream_message_id=stream_message_id,
        published_at=published_at or datetime.now(UTC),
        event=event,
    )


def envelope_to_redis_fields(envelope: RealtimeMessageEnvelopeV1) -> dict[str, str]:
    payload = envelope.model_dump(mode="json", by_alias=True)
    return {
        "schemaVersion": str(payload["schemaVersion"]),
        "channel": payload["channel"],
        "eventId": payload["event"]["eventId"],
        "runId": payload["event"]["runId"],
        "sequence": str(payload["event"]["sequence"]),
        "type": payload["event"]["type"],
        "publishedAt": payload["publishedAt"],
        "payload": json.dumps(payload, separators=(",", ":")),
    }


def redis_fields_to_envelope(fields: dict[str, Any]) -> RealtimeMessageEnvelopeV1:
    if "payload" in fields:
        raw = fields["payload"]
        data = json.loads(raw) if isinstance(raw, str) else raw
        return parse_contract(RealtimeMessageEnvelopeV1, data)
    raise ValueError("Missing payload field in Redis stream message")
