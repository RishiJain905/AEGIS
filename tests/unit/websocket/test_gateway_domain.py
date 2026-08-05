"""Unit tests for WebSocket gateway domain logic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_api.websocket.auth import AuthenticatedPrincipal, DevWebSocketAuthenticator
from aegis_api.websocket.config import GatewayConfig as GatewayConfigCls
from aegis_api.websocket.connection import ConnectionState, SubscriptionState, new_connection_id
from aegis_api.websocket.consumer import GatewayStreamConsumer, _coerce_redis_fields
from aegis_api.websocket.errors import GatewayError
from aegis_api.websocket.recovery import RecoveryPlan, SubscriptionRecoveryService
from aegis_contracts import (
    ActorRef,
    ActorType,
    DomainEventEnvelopeV1,
    EventTypeRegistry,
    WebSocketDeliveryMode,
    WebSocketErrorCode,
    WebSocketFrameV1,
    WebSocketMessageType,
    build_websocket_frame,
)
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
from aegis_contracts.websocket import WebSocketHelloPayloadV1
from aegis_event_streaming.envelope import build_realtime_envelope, envelope_to_redis_fields


def _gateway_config(**overrides: object) -> GatewayConfigCls:
    base = {
        "ws_path": "/ws/v1/realtime",
        "enabled": True,
        "max_connections": 10,
        "max_queue_depth": 4,
        "max_message_bytes": 1024,
        "heartbeat_interval_seconds": 15,
        "idle_timeout_seconds": 45,
        "dev_auth_enabled": True,
        "dev_auth_token": "aegis-dev-token",
        "consumer_group": "aegis-ws-gateway",
        "snapshot_gap_threshold": 10,
    }
    base.update(overrides)
    return GatewayConfigCls(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_dev_authenticator_accepts_valid_token() -> None:
    auth = DevWebSocketAuthenticator(_gateway_config())
    principal = await auth.authenticate(auth_token="aegis-dev-token")
    assert principal.principal_id == "dev-operator"


@pytest.mark.asyncio
async def test_dev_authenticator_rejects_invalid_token() -> None:
    auth = DevWebSocketAuthenticator(_gateway_config())
    with pytest.raises(GatewayError) as exc:
        await auth.authenticate(auth_token="wrong")
    assert exc.value.code == WebSocketErrorCode.WS_UNAUTHORIZED


def test_connection_dedup_tracks_event_ids() -> None:
    queue: asyncio.Queue[WebSocketFrameV1] = asyncio.Queue(maxsize=4)

    class _Ws:
        pass

    connection = ConnectionState(
        connection_id=new_connection_id(),
        websocket=_Ws(),  # type: ignore[arg-type]
        principal=AuthenticatedPrincipal(principal_id="test"),
        outbound_queue=queue,
    )
    assert connection.remember_event_id("evt_01ARZ3NDEKTSV4RRFFQ69G5FAW") is True
    assert connection.remember_event_id("evt_01ARZ3NDEKTSV4RRFFQ69G5FAW") is False


def test_gateway_consumer_decodes_redis_bytes() -> None:
    assert _coerce_redis_fields({b"payload": b"{}", b"sequence": 7}) == {
        "payload": "{}",
        "sequence": "7",
    }


class _FakeGatewayRedis:
    """Minimal stand-in for redis.asyncio.Redis with decode_responses=False.

    Mirrors production: WebSocketGatewayManager.start() constructs its Redis
    client with decode_responses=False, so XREADGROUP hands back both the
    message id and field map as bytes.
    """

    def __init__(self, message_id: bytes, fields: dict[bytes, bytes]) -> None:
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
    ) -> list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]]:
        if self._delivered:
            return []
        self._delivered = True
        stream_key = next(iter(streams))
        return [(stream_key, [(self._message_id, self._fields)])]

    async def xack(self, _stream_key: str, _group: str, message_id: str) -> int:
        self.acked.append(message_id)
        return 1


@pytest.mark.asyncio
async def test_gateway_stream_consumer_decodes_bytes_message_id() -> None:
    """Regression test: bytes message ids must reach the handler as plain str.

    Previously ``message_id`` was passed straight from ``xreadgroup`` into
    ``envelope.model_copy(update={"stream_message_id": message_id})`` without
    decoding, so a decode_responses=False Redis client (as used by
    WebSocketGatewayManager) fed raw bytes into the ``str`` contract field,
    producing Pydantic serializer warnings.
    """
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
    envelope = build_realtime_envelope(event)
    str_fields = envelope_to_redis_fields(envelope)
    bytes_fields = {key.encode("utf-8"): value.encode("utf-8") for key, value in str_fields.items()}
    raw_message_id = b"1730000000000-0"

    redis = _FakeGatewayRedis(raw_message_id, bytes_fields)

    received: list[Any] = []

    async def handler(received_envelope: Any) -> None:
        received.append(received_envelope)

    consumer = GatewayStreamConsumer(
        redis,  # type: ignore[arg-type]
        handler,
        consumer_name="test-gateway-consumer",
        consumer_group="test-gateway-group",
    )

    processed = await consumer._process_once()

    assert processed == 1
    assert len(received) == 1
    delivered = received[0].stream_message_id
    assert delivered == "1730000000000-0"
    assert isinstance(delivered, str)
    assert delivered != "b'1730000000000-0'"
    assert redis.acked == ["1730000000000-0"]


def test_gateway_error_to_frame() -> None:
    error = GatewayError(code=WebSocketErrorCode.WS_FORBIDDEN, message="nope")
    frame = error.to_frame(trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX")
    assert frame.message_type == WebSocketMessageType.ERROR


def test_build_hello_frame_validates() -> None:
    frame = build_websocket_frame(
        message_type=WebSocketMessageType.HELLO,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        sent_at=datetime.now(UTC),
        payload=WebSocketHelloPayloadV1(protocol_version=1, auth_token="aegis-dev-token"),
    )
    parsed = WebSocketFrameV1.model_validate(frame.model_dump(mode="json", by_alias=True))
    assert parsed.message_type == WebSocketMessageType.HELLO


def test_recovery_plan_stream_mode() -> None:
    plan = RecoveryPlan(delivery_mode=WebSocketDeliveryMode.STREAM, events=[])
    assert plan.delivery_mode == WebSocketDeliveryMode.STREAM


def test_subscription_state_pause_flag() -> None:
    sub = SubscriptionState(
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        channel="events",
        last_applied_sequence=0,
    )
    sub.paused = True
    assert sub.paused is True


def test_gateway_config_snapshot_threshold() -> None:
    config = _gateway_config(snapshot_gap_threshold=500)
    service = SubscriptionRecoveryService(config)
    assert service._config.snapshot_gap_threshold == 500
