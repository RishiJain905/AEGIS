"""Subscribe-backfill delivery for the WebSocket gateway.

Live QA found every WebSocket connection dying within ~250ms of a successful handshake,
100% of the time, on any run more than `max_queue_depth` events old. The gateway's own log
recorded it as ``RuntimeError: WebSocket is not connected`` raised out of the receive loop.

The chain: a subscribe backfill is as long as the client's cursor is stale, and it was
written with ``put_nowait`` from the connection's receive-loop task, which never yields — so
the outbound queue filled, the overflow path paused the subscription, and the
``resync_complete`` frame that follows then failed to enqueue and *closed the socket*. The
client reconnected with the same stale cursor and hit exactly the same wall, forever. The
operator's board only ever advanced via the HTTP resync each reconnect triggered, which is
why the live delta path looked dead and why "Resync" appeared to be the only thing that
worked.

These tests pin the two properties that break that loop: a backfill longer than the queue
is delivered rather than dropped, and a client that has genuinely stopped reading is paused
and told to take a snapshot rather than having its connection torn down.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aegis_api.websocket.auth import AuthenticatedPrincipal, DevWebSocketAuthenticator
from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.connection import ConnectionState, SubscriptionState, new_connection_id
from aegis_api.websocket.manager import WebSocketGatewayManager
from aegis_contracts import (
    ActorRef,
    ActorType,
    AegisEnvironment,
    AegisSettings,
    DomainEventEnvelopeV1,
    EventTypeRegistry,
    WebSocketFrameV1,
)
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION
from aegis_event_streaming.envelope import build_realtime_envelope

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
QUEUE_DEPTH = 4


def _settings() -> AegisSettings:
    return AegisSettings(
        AEGIS_ENV=AegisEnvironment.TEST,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="aegis",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="minio",
        S3_SECRET_KEY="minio123",
        S3_BUCKET="aegis",
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_ENABLED=True,
        AEGIS_WS_DEV_AUTH_ENABLED=True,
        AEGIS_OIDC_ENABLED=False,
        AEGIS_CORS_ALLOWED_ORIGINS="http://localhost:3000",
    )


def _config(**overrides: object) -> GatewayConfig:
    base: dict[str, object] = {
        "ws_path": "/ws/v1/realtime",
        "enabled": True,
        "max_connections": 10,
        "max_queue_depth": QUEUE_DEPTH,
        "max_message_bytes": 65536,
        "heartbeat_interval_seconds": 15,
        "idle_timeout_seconds": 45,
        "dev_auth_enabled": True,
        "dev_auth_token": "aegis-dev-token",
        "consumer_group": "aegis-ws-gateway",
        "snapshot_gap_threshold": 500,
        "backfill_enqueue_timeout_seconds": 0.2,
    }
    base.update(overrides)
    return GatewayConfig(**base)  # type: ignore[arg-type]


class _RecordingWebSocket:
    """Records direct sends and whether the gateway closed the socket."""

    def __init__(self) -> None:
        self.direct_sends: list[str] = []
        self.closed = False

    async def send_text(self, raw: str) -> None:
        self.direct_sends.append(raw)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


def _manager(config: GatewayConfig) -> WebSocketGatewayManager:
    return WebSocketGatewayManager(
        _settings(),
        config=config,
        authenticator=DevWebSocketAuthenticator(config),
    )


def _connection(websocket: _RecordingWebSocket) -> ConnectionState:
    return ConnectionState(
        connection_id=new_connection_id(),
        websocket=websocket,  # type: ignore[arg-type]
        principal=AuthenticatedPrincipal(principal_id="dev-operator"),
        outbound_queue=asyncio.Queue(maxsize=QUEUE_DEPTH),
    )


def _event(sequence: int):
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return DomainEventEnvelopeV1(
        event_id=f"evt_{sequence:026d}",
        run_id=RUN_ID,
        sequence=sequence,
        type="sim.run.started",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        payload={"schemaVersion": EventTypeRegistry.payload_schema_version("sim.run.started")},
        trace_id=f"trc_{sequence:026d}",
    )


async def _drain(
    queue: asyncio.Queue[WebSocketFrameV1],
    collected: list[WebSocketFrameV1],
    delivered: asyncio.Event,
    expected: int,
) -> None:
    """Stand-in for the real sender loop: pulls frames off the queue forever."""
    while True:
        collected.append(await queue.get())
        if len(collected) >= expected:
            delivered.set()


@pytest.mark.asyncio
async def test_backfill_longer_than_the_queue_is_delivered_whole() -> None:
    # The exact shape that killed every connection in QA: far more backfill events than the
    # outbound queue can hold at once.
    backfill_length = QUEUE_DEPTH * 5
    manager = _manager(_config())
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = SubscriptionState(run_id=RUN_ID, channel="events", last_applied_sequence=0)

    sent: list[WebSocketFrameV1] = []
    delivered = asyncio.Event()
    sender = asyncio.create_task(
        _drain(connection.outbound_queue, sent, delivered, backfill_length)
    )
    try:
        for sequence in range(1, backfill_length + 1):
            accepted = await manager._enqueue_event(
                connection,
                subscription,
                build_realtime_envelope(_event(sequence)),
                wait_for_capacity=True,
            )
            assert accepted is True, f"backfill refused at sequence {sequence}"
        # The tail of the backfill is still in flight to the sender when the loop ends.
        await asyncio.wait_for(delivered.wait(), timeout=2)
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)

    assert subscription.paused is False
    assert websocket.closed is False
    assert subscription.last_applied_sequence == backfill_length
    assert [frame.payload["envelope"]["event"]["sequence"] for frame in sent] == list(
        range(1, backfill_length + 1)
    )


@pytest.mark.asyncio
async def test_backfill_pauses_rather_than_closing_when_the_client_never_reads() -> None:
    # No sender draining: a client that has genuinely stopped reading. The gateway must fall
    # back to the snapshot-required contract, not tear the connection down — the operator can
    # recover from a snapshot, but a closed socket only reconnects into the same state.
    manager = _manager(_config())
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = SubscriptionState(run_id=RUN_ID, channel="events", last_applied_sequence=0)

    results = [
        await manager._enqueue_event(
            connection,
            subscription,
            build_realtime_envelope(_event(sequence)),
            wait_for_capacity=True,
        )
        for sequence in range(1, QUEUE_DEPTH + 2)
    ]

    assert results[:QUEUE_DEPTH] == [True] * QUEUE_DEPTH
    assert results[-1] is False
    assert subscription.paused is True
    assert websocket.closed is False
    assert any("snapshot_required" in raw for raw in websocket.direct_sends)


@pytest.mark.asyncio
async def test_live_fan_out_still_refuses_to_wait_on_a_slow_client() -> None:
    # Live delivery runs on the shared Redis consumer task, so it must never block: one slow
    # client waiting there would stall delivery to every other connection.
    manager = _manager(_config(backfill_enqueue_timeout_seconds=30.0))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = SubscriptionState(run_id=RUN_ID, channel="events", last_applied_sequence=0)

    for sequence in range(1, QUEUE_DEPTH + 1):
        assert (
            await manager._enqueue_event(
                connection, subscription, build_realtime_envelope(_event(sequence))
            )
            is True
        )

    overflow = await asyncio.wait_for(
        manager._enqueue_event(
            connection, subscription, build_realtime_envelope(_event(QUEUE_DEPTH + 1))
        ),
        timeout=1.0,
    )
    assert overflow is False
    assert subscription.paused is True
