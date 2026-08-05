"""Unit tests: Redis Streams message ids must be decoded to ``str``, not stringified.

Regression coverage for a defect where ``bytes`` message ids returned by
``XREADGROUP``/``XAUTOCLAIM`` (when the Redis client is not configured with
``decode_responses=True``) were assigned straight into the ``stream_message_id``
contract field, producing Pydantic serializer warnings ("Expected `str` but
got `bytes`") and, in code paths that naively wrapped the id in ``str(...)``,
silently corrupting the id into its Python repr (``"b'1-0'"``).
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1, EventTypeRegistry
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
from aegis_event_streaming.consumer import IdempotentStreamConsumer
from aegis_event_streaming.envelope import (
    build_realtime_envelope,
    decode_stream_message_id,
    envelope_to_redis_fields,
)
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM


def _sample_event() -> DomainEventEnvelopeV1:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return DomainEventEnvelopeV1(
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


def test_decode_stream_message_id_decodes_bytes_to_utf8_str() -> None:
    decoded = decode_stream_message_id(b"1730000000000-0")
    assert decoded == "1730000000000-0"
    # The historical bug used ``str(bytes_id)``, which yields the Python repr
    # instead of the decoded text -- guard against that regression explicitly.
    assert decoded != "b'1730000000000-0'"
    assert isinstance(decoded, str)


def test_decode_stream_message_id_passes_through_str_untouched() -> None:
    assert decode_stream_message_id("1730000000000-0") == "1730000000000-0"


class _FakeSession:
    async def commit(self) -> None:
        return None


class _FakeSessionContext(AbstractAsyncContextManager["_FakeSession"]):
    async def __aenter__(self) -> _FakeSession:
        return _FakeSession()

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class _FakeReceiptRepository:
    """Stands in for PostgresConsumerReceiptRepository without touching a DB."""

    recorded_stream_message_ids: list[str | None] = []

    def __init__(self, _session: _FakeSession) -> None:
        pass

    async def has_receipt(self, *, consumer_id: str, event_id: str) -> bool:
        return False

    async def try_record(
        self,
        *,
        consumer_id: str,
        event_id: str,
        stream_message_id: str | None,
        processed_at: datetime,
    ) -> bool:
        _FakeReceiptRepository.recorded_stream_message_ids.append(stream_message_id)
        return True


class _FakeCursorRepository:
    def __init__(self, _session: _FakeSession) -> None:
        pass

    async def upsert(self, cursor: Any) -> Any:
        return cursor


class _FakeRedis:
    """Minimal stand-in for the subset of redis.asyncio.Redis the consumer uses."""

    def __init__(self, message_id: bytes, fields: dict[str, str]) -> None:
        self._message_id = message_id
        self._fields = fields
        self._delivered = False
        self.acked: list[str] = []

    async def xgroup_create(self, *_args: object, **_kwargs: object) -> bool:
        return True

    async def xreadgroup(
        self,
        *,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int,
        block: int,
    ) -> list[tuple[str, list[tuple[bytes, dict[str, str]]]]]:
        if self._delivered:
            return []
        self._delivered = True
        stream_key = next(iter(streams))
        return [(stream_key, [(self._message_id, self._fields)])]

    async def xack(self, _stream_key: str, _group: str, message_id: str) -> int:
        self.acked.append(message_id)
        return 1


@pytest.mark.asyncio
async def test_idempotent_stream_consumer_decodes_bytes_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stream reader hands back bytes; the envelope and receipt must see str."""
    _FakeReceiptRepository.recorded_stream_message_ids = []
    monkeypatch.setattr(
        "aegis_event_streaming.consumer.PostgresConsumerReceiptRepository",
        _FakeReceiptRepository,
    )
    monkeypatch.setattr(
        "aegis_event_streaming.consumer.PostgresConsumerCursorRepository",
        _FakeCursorRepository,
    )

    event = _sample_event()
    envelope = build_realtime_envelope(event)
    fields = envelope_to_redis_fields(envelope)
    raw_message_id = b"1730000000000-0"

    redis = _FakeRedis(raw_message_id, fields)

    received_envelopes = []

    async def handler(received_envelope: Any) -> None:
        received_envelopes.append(received_envelope)

    def fake_session_maker() -> _FakeSessionContext:
        return _FakeSessionContext()

    consumer = IdempotentStreamConsumer(
        fake_session_maker,  # type: ignore[arg-type]
        redis,  # type: ignore[arg-type]
        handler,
        consumer_name="test-consumer",
        stream_key=DOMAIN_EVENTS_STREAM,
    )

    processed = await consumer.process_once()

    assert processed == 1
    assert len(received_envelopes) == 1
    delivered = received_envelopes[0].stream_message_id
    assert delivered == "1730000000000-0"
    assert isinstance(delivered, str)
    assert delivered != "b'1730000000000-0'"

    assert redis.acked == ["1730000000000-0"]
    assert _FakeReceiptRepository.recorded_stream_message_ids == ["1730000000000-0"]
