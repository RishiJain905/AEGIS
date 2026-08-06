"""Subscription lifecycle for the WebSocket gateway: pause recovery and terminated runs.

Two ways a subscription used to stop delivering without ever saying so.

A subscription the overflow path paused was never un-paused by anything on the server. The
socket stayed open, heartbeats kept passing, and the subscription delivered nothing for the
rest of the connection's life — recovery depended entirely on the client noticing
``snapshot_required`` and re-subscribing, which a client that had stopped reading is by
construction least likely to do. The gateway now resolves every paused subscription on the
heartbeat sweep: resume it if the queue drained, close the connection if it did not.

A run that ended left its subscriptions registered against a stream that would never produce
another event. The client waited on a live, silent socket; the gateway held fan-out index
entries nothing could ever match. A terminal run now produces one deterministic
``run_terminated`` frame per subscription, and the subscription is unregistered.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from aegis_api.websocket.auth import AuthenticatedPrincipal, DevWebSocketAuthenticator
from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.connection import ConnectionState, SubscriptionState, new_connection_id
from aegis_api.websocket.manager import WebSocketGatewayManager
from aegis_api.websocket.recovery import RecoveryPlan
from aegis_contracts import (
    ActorRef,
    ActorType,
    AegisEnvironment,
    AegisSettings,
    DomainEventEnvelopeV1,
    EventTypeRegistry,
    WebSocketDeliveryMode,
    WebSocketFrameV1,
    WebSocketMessageType,
    build_websocket_frame,
)
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION, PROTOCOL_VERSION_V1
from aegis_contracts.websocket import WebSocketSubscribePayloadV1
from aegis_event_streaming.envelope import build_realtime_envelope

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
CHANNEL = "events"
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
        "backfill_enqueue_timeout_seconds": 0.05,
        "paused_subscription_grace_seconds": 30.0,
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


def _event(sequence: int, event_type: str = "sim.run.started") -> DomainEventEnvelopeV1:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return DomainEventEnvelopeV1(
        event_id=f"evt_{sequence:026d}",
        run_id=RUN_ID,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:operator-console"),
        payload={"schemaVersion": EventTypeRegistry.payload_schema_version(event_type)},
        trace_id=f"trc_{sequence:026d}",
    )


def _queued(connection: ConnectionState) -> list[WebSocketFrameV1]:
    """Everything sitting in the outbound queue, without consuming it."""
    return list(connection.outbound_queue._queue)  # type: ignore[attr-defined]


def _message_types(connection: ConnectionState) -> list[str]:
    return [frame.message_type.value for frame in _queued(connection)]


async def _register(
    manager: WebSocketGatewayManager,
    connection: ConnectionState,
    *,
    last_applied_sequence: int = 0,
) -> SubscriptionState:
    subscription = SubscriptionState(
        run_id=RUN_ID,
        channel=CHANNEL,
        last_applied_sequence=last_applied_sequence,
    )
    key = connection.subscription_key(RUN_ID, CHANNEL)
    connection.subscriptions[key] = subscription
    manager._connections[connection.connection_id] = connection
    manager._subscription_index.setdefault(key, set()).add(connection.connection_id)
    return subscription


async def _overflow(
    manager: WebSocketGatewayManager,
    connection: ConnectionState,
    subscription: SubscriptionState,
) -> None:
    """Fill the outbound queue past its bound so the overflow path parks the subscription."""
    for sequence in range(1, QUEUE_DEPTH + 2):
        await manager._enqueue_event(
            connection,
            subscription,
            build_realtime_envelope(_event(sequence), channel=CHANNEL),
        )
    assert subscription.paused is True


@pytest.mark.asyncio
async def test_paused_subscription_resumes_once_the_queue_drains() -> None:
    manager = _manager(_config())
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = await _register(manager, connection)
    await _overflow(manager, connection, subscription)
    paused_at = subscription.paused_at
    assert paused_at is not None

    # The client started reading again.
    while not connection.outbound_queue.empty():
        connection.outbound_queue.get_nowait()

    closed = await manager._sweep_paused_subscriptions(connection, datetime.now(UTC))

    assert closed is False
    assert subscription.paused is False
    assert subscription.paused_at is None
    assert websocket.closed is False
    # The client is told delivery is live again, and from where — its cursor is behind the
    # run head, and the next live event's gap fill closes that from PostgreSQL.
    resumed = [
        frame
        for frame in _queued(connection)
        if frame.message_type is WebSocketMessageType.WARNING
        and frame.payload["code"] == "WS_SUBSCRIPTION_RESUMED"
    ]
    assert len(resumed) == 1
    assert resumed[0].payload["runId"] == RUN_ID
    assert resumed[0].payload["details"]["fromSequence"] == subscription.last_applied_sequence + 1
    assert manager.metrics.subscriptions_resumed == 1


@pytest.mark.asyncio
async def test_paused_subscription_is_left_alone_inside_the_grace_window() -> None:
    # A queue that is still full but has only just overflowed gets time to drain; closing on
    # the first sweep would turn every momentary burst into a dropped connection.
    manager = _manager(_config())
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = await _register(manager, connection)
    await _overflow(manager, connection, subscription)

    closed = await manager._sweep_paused_subscriptions(connection, datetime.now(UTC))

    assert closed is False
    assert subscription.paused is True
    assert websocket.closed is False


@pytest.mark.asyncio
async def test_paused_subscription_that_never_drains_closes_the_connection() -> None:
    # The client has not read a byte for the whole grace window. There is nothing left to
    # resume onto, so the connection is closed and the client reconnects from a cursor the
    # gateway can actually serve — rather than holding a subscription that never delivers.
    manager = _manager(_config(paused_subscription_grace_seconds=30.0))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    subscription = await _register(manager, connection)
    await _overflow(manager, connection, subscription)

    later = datetime.now(UTC) + timedelta(seconds=31)
    closed = await manager._sweep_paused_subscriptions(connection, later)

    assert closed is True
    assert websocket.closed is True
    assert any("WS_QUEUE_OVERFLOW" in raw for raw in websocket.direct_sends)


@pytest.mark.asyncio
async def test_sweep_is_a_no_op_for_a_connection_with_nothing_paused() -> None:
    manager = _manager(_config())
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    await _register(manager, connection)

    closed = await manager._sweep_paused_subscriptions(connection, datetime.now(UTC))

    assert closed is False
    assert websocket.closed is False
    assert _queued(connection) == []


@pytest.mark.asyncio
async def test_terminal_run_event_ends_every_subscription_on_that_run() -> None:
    manager = _manager(_config(max_queue_depth=32))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    connection.outbound_queue = asyncio.Queue(maxsize=32)
    subscription = await _register(manager, connection)
    key = connection.subscription_key(RUN_ID, CHANNEL)

    await manager.deliver_envelope(
        build_realtime_envelope(_event(1, "sim.run.stopped"), channel=CHANNEL)
    )

    # The lifecycle event itself lands first; the terminal frame follows it, so a client that
    # applies frames in order sees the run stop before it is told the stream is over.
    assert _message_types(connection) == ["event", "run_terminated"]
    terminated = _queued(connection)[-1]
    assert terminated.payload["runId"] == RUN_ID
    assert terminated.payload["status"] == "stopped"
    # No zombie: neither the connection nor the fan-out index still holds the subscription.
    assert connection.get_subscription(RUN_ID, CHANNEL) is None
    assert key not in manager._subscription_index
    assert subscription.run_id == RUN_ID  # the object survives; only the registration goes
    assert manager.metrics.subscriptions_terminated == 1


@pytest.mark.asyncio
async def test_subscribing_to_an_already_terminal_run_backfills_then_ends() -> None:
    # Replaying a finished run is a debrief, not an error: the backfill is served in full.
    # What must not survive it is the subscription — no live event will ever follow.
    manager = _manager(_config(max_queue_depth=32))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    connection.outbound_queue = asyncio.Queue(maxsize=32)
    manager._session_maker = _FakeSessionMaker()  # type: ignore[assignment]

    async def _plan_recovery(*_args: object, **_kwargs: object) -> RecoveryPlan:
        return RecoveryPlan(
            delivery_mode=WebSocketDeliveryMode.BACKFILL,
            events=[_event(1), _event(2)],
        )

    async def _seed(*_args: object, **_kwargs: object) -> str:
        return "completed"

    manager._recovery.plan_recovery = _plan_recovery  # type: ignore[assignment,method-assign]
    manager._seed_run_tracker = _seed  # type: ignore[assignment,method-assign]

    await manager._handle_subscribe(connection, _subscribe_frame())

    assert _message_types(connection) == [
        "subscribed",
        "event",
        "event",
        "resync_complete",
        "run_terminated",
    ]
    terminated = _queued(connection)[-1]
    assert terminated.payload["status"] == "completed"
    assert connection.get_subscription(RUN_ID, CHANNEL) is None
    assert connection.subscription_key(RUN_ID, CHANNEL) not in manager._subscription_index


@pytest.mark.asyncio
async def test_subscribing_to_an_active_run_keeps_the_subscription() -> None:
    manager = _manager(_config(max_queue_depth=32))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    connection.outbound_queue = asyncio.Queue(maxsize=32)
    manager._session_maker = _FakeSessionMaker()  # type: ignore[assignment]

    async def _plan_recovery(*_args: object, **_kwargs: object) -> RecoveryPlan:
        return RecoveryPlan(delivery_mode=WebSocketDeliveryMode.STREAM, events=[])

    async def _seed(*_args: object, **_kwargs: object) -> str:
        return "running"

    manager._recovery.plan_recovery = _plan_recovery  # type: ignore[assignment,method-assign]
    manager._seed_run_tracker = _seed  # type: ignore[assignment,method-assign]

    await manager._handle_subscribe(connection, _subscribe_frame())

    assert _message_types(connection) == ["subscribed"]
    assert connection.get_subscription(RUN_ID, CHANNEL) is not None
    assert connection.subscription_key(RUN_ID, CHANNEL) in manager._subscription_index


@pytest.mark.asyncio
async def test_unreadable_run_status_leaves_the_subscription_live() -> None:
    # Fog seeding is best-effort and reports `None` when it cannot read the run. Treating
    # that as terminal would drop a perfectly good subscription over a transient DB blip.
    manager = _manager(_config(max_queue_depth=32))
    websocket = _RecordingWebSocket()
    connection = _connection(websocket)
    connection.outbound_queue = asyncio.Queue(maxsize=32)
    manager._session_maker = _FakeSessionMaker()  # type: ignore[assignment]

    async def _plan_recovery(*_args: object, **_kwargs: object) -> RecoveryPlan:
        return RecoveryPlan(delivery_mode=WebSocketDeliveryMode.STREAM, events=[])

    async def _seed(*_args: object, **_kwargs: object) -> None:
        return None

    manager._recovery.plan_recovery = _plan_recovery  # type: ignore[assignment,method-assign]
    manager._seed_run_tracker = _seed  # type: ignore[assignment,method-assign]

    await manager._handle_subscribe(connection, _subscribe_frame())

    assert "run_terminated" not in _message_types(connection)
    assert connection.get_subscription(RUN_ID, CHANNEL) is not None


def _subscribe_frame() -> WebSocketFrameV1:
    return build_websocket_frame(
        message_type=WebSocketMessageType.SUBSCRIBE,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        sent_at=datetime.now(UTC),
        payload=WebSocketSubscribePayloadV1(
            run_id=RUN_ID,
            channel=CHANNEL,
            last_applied_sequence=0,
        ),
    )


class _FakeSessionMaker:
    """Stands in for the async sessionmaker; the collaborators that use it are stubbed."""

    def __call__(self) -> _FakeSessionMaker:
        return self

    async def __aenter__(self) -> _FakeSessionMaker:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def _allow_every_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authorization is exercised by its own tests and needs a real run row; skip it here."""

    class _AllowAll:
        def __init__(self, _session: object) -> None:
            pass

        async def authorize(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        "aegis_api.websocket.manager.DevRunSubscriptionAuthorizer",
        _AllowAll,
    )


def test_protocol_version_is_pinned() -> None:
    # Guards the frames above: they are built against v1 and parsed by clients as v1.
    assert PROTOCOL_VERSION_V1 == 1
    assert json.loads(_subscribe_frame().model_dump_json(by_alias=True))["protocolVersion"] == 1
