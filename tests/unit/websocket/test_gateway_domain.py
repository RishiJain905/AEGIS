"""Unit tests for WebSocket gateway domain logic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aegis_api.websocket.auth import AuthenticatedPrincipal, DevWebSocketAuthenticator
from aegis_api.websocket.config import GatewayConfig as GatewayConfigCls
from aegis_api.websocket.connection import ConnectionState, SubscriptionState, new_connection_id
from aegis_api.websocket.consumer import _coerce_redis_fields
from aegis_api.websocket.errors import GatewayError
from aegis_api.websocket.recovery import RecoveryPlan, SubscriptionRecoveryService
from aegis_contracts import (
    WebSocketDeliveryMode,
    WebSocketErrorCode,
    WebSocketFrameV1,
    WebSocketMessageType,
    build_websocket_frame,
)
from aegis_contracts.websocket import WebSocketHelloPayloadV1


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
