"""WebSocket gateway connection and subscription manager."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime

from aegis_contracts import (
    AegisSettings,
    RealtimeMessageEnvelopeV1,
    build_websocket_frame,
    parse_contract,
)
from aegis_contracts.errors import ContractValidationError
from aegis_contracts.versioning import PROTOCOL_VERSION_V1
from aegis_contracts.websocket import (
    WebSocketErrorCode,
    WebSocketEventPayloadV1,
    WebSocketFrameV1,
    WebSocketHelloAckPayloadV1,
    WebSocketHelloPayloadV1,
    WebSocketMessageType,
    WebSocketPingPayloadV1,
    WebSocketResyncCompletePayloadV1,
    WebSocketSnapshotRequiredPayloadV1,
    WebSocketSubscribedPayloadV1,
    WebSocketSubscribePayloadV1,
    WebSocketUnsubscribePayloadV1,
    WebSocketWarningPayloadV1,
)
from aegis_event_streaming.config import StreamingConfig
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.db.session import get_db_session_maker
from aegis_api.websocket.auth import (
    AuthenticatedPrincipal,
    DevRunSubscriptionAuthorizer,
    WebSocketAuthenticator,
    build_authenticator,
)
from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.connection import (
    ConnectionState,
    SubscriptionState,
    new_connection_id,
    new_trace_id,
)
from aegis_api.websocket.consumer import GatewayStreamConsumer
from aegis_api.websocket.errors import GatewayError
from aegis_api.websocket.metrics import GLOBAL_GATEWAY_METRICS, GatewayMetrics
from aegis_api.websocket.recovery import SubscriptionRecoveryService, envelope_from_domain_event

logger = logging.getLogger(__name__)


class WebSocketGatewayManager:
    def __init__(
        self,
        settings: AegisSettings,
        *,
        config: GatewayConfig | None = None,
        metrics: GatewayMetrics | None = None,
        authenticator: WebSocketAuthenticator | None = None,
    ) -> None:
        self._settings = settings
        self._config = config or GatewayConfig.from_settings(settings)
        self._metrics = metrics or GLOBAL_GATEWAY_METRICS
        self._authenticator = authenticator or build_authenticator(settings, self._config)
        self._recovery = SubscriptionRecoveryService(self._config)
        self._connections: dict[str, ConnectionState] = {}
        self._subscription_index: dict[tuple[str, str], set[str]] = {}
        self._redis: Redis | None = None
        self._consumer: GatewayStreamConsumer | None = None
        self._consumer_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def metrics(self) -> GatewayMetrics:
        return self._metrics

    async def start(self) -> None:
        if not self._config.enabled:
            return
        self._session_maker = get_db_session_maker()
        self._redis = Redis.from_url(str(self._settings.REDIS_URL), decode_responses=False)
        self._consumer = GatewayStreamConsumer(
            self._redis,
            self.deliver_envelope,
            consumer_name="gateway-1",
            consumer_group=self._config.consumer_group,
            config=StreamingConfig.from_env(),
        )
        self._consumer_task = asyncio.create_task(
            self._consumer.run(),
            name="ws-gateway-consumer",
        )
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name="ws-gateway-heartbeat",
        )

    async def stop(self) -> None:
        if self._consumer is not None:
            self._consumer.stop()
        for task in (self._consumer_task, self._heartbeat_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        async with self._lock:
            for connection in list(self._connections.values()):
                await self._close_connection(connection, reason="shutdown")
        if self._redis is not None:
            await self._redis.aclose()

    async def handle_connection(self, websocket: WebSocket) -> None:
        if not self._config.enabled:
            await websocket.close(code=1008)
            return

        if len(self._connections) >= self._config.max_connections:
            await websocket.accept()
            await websocket.close(code=1008, reason="connection_limit")
            self._metrics.connection_closed("connection_limit")
            return

        await websocket.accept()
        connection_id = new_connection_id()
        queue: asyncio.Queue[WebSocketFrameV1] = asyncio.Queue(
            maxsize=self._config.max_queue_depth,
        )
        connection = ConnectionState(
            connection_id=connection_id,
            websocket=websocket,
            principal=AuthenticatedPrincipal(principal_id="anonymous"),
            outbound_queue=queue,
        )
        connection.sender_task = asyncio.create_task(
            self._sender_loop(connection),
            name=f"ws-sender-{connection_id}",
        )

        async with self._lock:
            self._connections[connection_id] = connection
            self._metrics.connection_opened()

        try:
            await self._handshake(connection)
            await self._receive_loop(connection)
        except WebSocketDisconnect:
            await self._close_connection(connection, reason="client_disconnect")
        except GatewayError as exc:
            await self._send_frame_direct(connection, exc.to_frame(trace_id=new_trace_id()))
            await self._close_connection(connection, reason=exc.code.value)
        except Exception:
            logger.exception("WebSocket connection failed for %s", connection_id)
            await self._close_connection(connection, reason="internal_error")
        finally:
            async with self._lock:
                self._connections.pop(connection_id, None)
                self._remove_connection_subscriptions(connection)

    async def deliver_envelope(self, envelope: RealtimeMessageEnvelopeV1) -> None:
        key = (envelope.event.run_id, envelope.channel)
        async with self._lock:
            connection_ids = list(self._subscription_index.get(key, set()))

        for connection_id in connection_ids:
            connection = self._connections.get(connection_id)
            if connection is None:
                continue
            subscription = connection.get_subscription(envelope.event.run_id, envelope.channel)
            if subscription is None or subscription.paused:
                continue
            await self._deliver_live_event(connection, subscription, envelope)

    async def _handshake(self, connection: ConnectionState) -> None:
        raw = await asyncio.wait_for(
            connection.websocket.receive_text(),
            timeout=self._config.hello_timeout_seconds,
        )
        self._validate_message_size(raw)
        frame = self._parse_frame(raw)
        if frame.message_type != WebSocketMessageType.HELLO:
            raise GatewayError(
                code=WebSocketErrorCode.WS_INVALID_MESSAGE,
                message="First frame must be hello",
            )
        hello = parse_contract(WebSocketHelloPayloadV1, frame.payload)
        if hello.protocol_version != PROTOCOL_VERSION_V1:
            raise GatewayError(
                code=WebSocketErrorCode.WS_UNSUPPORTED_PROTOCOL,
                message=f"Unsupported protocol version: {hello.protocol_version}",
            )
        connection.principal = await self._authenticator.authenticate(
            auth_token=hello.auth_token,
        )
        await self._send_frame(
            connection,
            build_websocket_frame(
                message_type=WebSocketMessageType.HELLO_ACK,
                trace_id=frame.trace_id,
                sent_at=datetime.now(UTC),
                payload=WebSocketHelloAckPayloadV1(
                    protocol_version=PROTOCOL_VERSION_V1,
                    connection_id=connection.connection_id,
                    principal_id=connection.principal.principal_id,
                ),
            ),
        )

    async def _receive_loop(self, connection: ConnectionState) -> None:
        while True:
            raw = await connection.websocket.receive_text()
            self._validate_message_size(raw)
            try:
                frame = self._parse_frame(raw)
            except GatewayError as exc:
                await self._send_frame_direct(connection, exc.to_frame(trace_id=new_trace_id()))
                continue
            self._metrics.record_received()
            if frame.message_type == WebSocketMessageType.PONG:
                connection.touch_pong()
                continue
            if frame.message_type == WebSocketMessageType.SUBSCRIBE:
                try:
                    await self._handle_subscribe(connection, frame)
                except GatewayError as exc:
                    await self._send_frame_direct(connection, exc.to_frame(trace_id=frame.trace_id))
                continue
            if frame.message_type == WebSocketMessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(connection, frame)
                continue
            await self._send_frame_direct(
                connection,
                GatewayError(
                    code=WebSocketErrorCode.WS_INVALID_MESSAGE,
                    message=f"Unsupported client message type: {frame.message_type}",
                ).to_frame(trace_id=frame.trace_id),
            )

    async def _handle_subscribe(
        self,
        connection: ConnectionState,
        frame: WebSocketFrameV1,
    ) -> None:
        payload = parse_contract(WebSocketSubscribePayloadV1, frame.payload)
        assert self._session_maker is not None
        async with self._session_maker() as session:
            authorizer = DevRunSubscriptionAuthorizer(session)
            await authorizer.authorize(
                principal=connection.principal,
                run_id=payload.run_id,
                channel=payload.channel,
            )
            plan = await self._recovery.plan_recovery(
                session,
                run_id=payload.run_id,
                last_applied_sequence=payload.last_applied_sequence,
            )

        key = connection.subscription_key(payload.run_id, payload.channel)
        subscription = SubscriptionState(
            run_id=payload.run_id,
            channel=payload.channel,
            last_applied_sequence=payload.last_applied_sequence,
        )
        connection.subscriptions[key] = subscription
        async with self._lock:
            self._subscription_index.setdefault(key, set()).add(connection.connection_id)

        await self._send_frame(
            connection,
            build_websocket_frame(
                message_type=WebSocketMessageType.SUBSCRIBED,
                trace_id=frame.trace_id,
                sent_at=datetime.now(UTC),
                payload=WebSocketSubscribedPayloadV1(
                    run_id=payload.run_id,
                    channel=payload.channel,
                    last_applied_sequence=payload.last_applied_sequence,
                    delivery_mode=plan.delivery_mode,
                ),
            ),
        )

        delivered = 0
        from_sequence = payload.last_applied_sequence
        for event in plan.events:
            envelope = envelope_from_domain_event(event, channel=payload.channel)
            await self._enqueue_event(connection, subscription, envelope)
            delivered += 1
            subscription.last_applied_sequence = event.sequence

        if delivered > 0:
            self._metrics.record_resync()
            await self._send_frame(
                connection,
                build_websocket_frame(
                    message_type=WebSocketMessageType.RESYNC_COMPLETE,
                    trace_id=frame.trace_id,
                    sent_at=datetime.now(UTC),
                    payload=WebSocketResyncCompletePayloadV1(
                        run_id=payload.run_id,
                        from_sequence=from_sequence + 1,
                        to_sequence=subscription.last_applied_sequence,
                        events_delivered=delivered,
                    ),
                ),
            )

    async def _handle_unsubscribe(
        self,
        connection: ConnectionState,
        frame: WebSocketFrameV1,
    ) -> None:
        payload = parse_contract(WebSocketUnsubscribePayloadV1, frame.payload)
        key = connection.subscription_key(payload.run_id, payload.channel)
        connection.subscriptions.pop(key, None)
        async with self._lock:
            subscribers = self._subscription_index.get(key)
            if subscribers is not None:
                subscribers.discard(connection.connection_id)
                if not subscribers:
                    self._subscription_index.pop(key, None)

    async def _deliver_live_event(
        self,
        connection: ConnectionState,
        subscription: SubscriptionState,
        envelope: RealtimeMessageEnvelopeV1,
    ) -> None:
        expected = subscription.last_applied_sequence + 1
        if envelope.event.sequence < expected:
            if not connection.remember_event_id(envelope.event.event_id):
                self._metrics.record_duplicate()
                await self._send_frame(
                    connection,
                    build_websocket_frame(
                        message_type=WebSocketMessageType.WARNING,
                        trace_id=new_trace_id(),
                        sent_at=datetime.now(UTC),
                        payload=WebSocketWarningPayloadV1(
                            code="WS_DUPLICATE_SUPPRESSED",
                            message="Duplicate event suppressed",
                            run_id=envelope.event.run_id,
                            details={"eventId": envelope.event.event_id},
                        ),
                    ),
                )
            return

        if envelope.event.sequence > expected:
            self._metrics.record_gap()
            assert self._session_maker is not None
            async with self._session_maker() as session:
                gap_events = await self._recovery.fill_sequence_gap(
                    session,
                    run_id=envelope.event.run_id,
                    from_sequence=expected,
                    to_sequence=envelope.event.sequence - 1,
                )
            for gap_event in gap_events:
                gap_envelope = envelope_from_domain_event(gap_event, channel=envelope.channel)
                await self._enqueue_event(connection, subscription, gap_envelope)

        await self._enqueue_event(connection, subscription, envelope)

    async def _enqueue_event(
        self,
        connection: ConnectionState,
        subscription: SubscriptionState,
        envelope: RealtimeMessageEnvelopeV1,
    ) -> None:
        if not connection.remember_event_id(envelope.event.event_id):
            self._metrics.record_duplicate()
            return

        frame = build_websocket_frame(
            message_type=WebSocketMessageType.EVENT,
            trace_id=envelope.event.trace_id,
            sent_at=datetime.now(UTC),
            payload=WebSocketEventPayloadV1(envelope=envelope),
        )
        try:
            connection.outbound_queue.put_nowait(frame)
            subscription.last_applied_sequence = envelope.event.sequence
            self._metrics.update_queue_depth(connection.outbound_queue.qsize())
        except asyncio.QueueFull:
            await self._handle_queue_overflow(connection, subscription, envelope.event.sequence)

    async def _handle_queue_overflow(
        self,
        connection: ConnectionState,
        subscription: SubscriptionState,
        from_sequence: int,
    ) -> None:
        subscription.paused = True
        self._metrics.record_slow_client()
        await self._send_frame_direct(
            connection,
            build_websocket_frame(
                message_type=WebSocketMessageType.SNAPSHOT_REQUIRED,
                trace_id=new_trace_id(),
                sent_at=datetime.now(UTC),
                payload=WebSocketSnapshotRequiredPayloadV1(
                    run_id=subscription.run_id,
                    reason=WebSocketErrorCode.WS_QUEUE_OVERFLOW,
                    from_sequence=from_sequence,
                ),
            ),
        )

    async def _sender_loop(self, connection: ConnectionState) -> None:
        try:
            while True:
                frame = await connection.outbound_queue.get()
                await connection.websocket.send_text(
                    json.dumps(frame.model_dump(mode="json", by_alias=True), separators=(",", ":"))
                )
                self._metrics.record_sent()
                self._metrics.update_queue_depth(connection.outbound_queue.qsize())
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Sender loop ended for %s", connection.connection_id, exc_info=True)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.heartbeat_interval_seconds)
            now = datetime.now(UTC)
            async with self._lock:
                connections = list(self._connections.values())
            for connection in connections:
                if connection.idle_seconds() > self._config.idle_timeout_seconds:
                    await self._send_error_and_close(
                        connection,
                        code=WebSocketErrorCode.WS_IDLE_TIMEOUT,
                        message="Connection idle timeout exceeded",
                    )
                    continue
                await self._send_frame(
                    connection,
                    build_websocket_frame(
                        message_type=WebSocketMessageType.PING,
                        trace_id=new_trace_id(),
                        sent_at=now,
                        payload=WebSocketPingPayloadV1(server_time=now),
                    ),
                )

    async def _send_error_and_close(
        self,
        connection: ConnectionState,
        *,
        code: WebSocketErrorCode,
        message: str,
    ) -> None:
        error = GatewayError(code=code, message=message)
        await self._send_frame_direct(connection, error.to_frame(trace_id=new_trace_id()))
        await self._close_connection(connection, reason=code.value)

    async def _send_frame_direct(
        self,
        connection: ConnectionState,
        frame: WebSocketFrameV1,
    ) -> None:
        await connection.websocket.send_text(
            json.dumps(frame.model_dump(mode="json", by_alias=True), separators=(",", ":"))
        )
        self._metrics.record_sent()

    async def _send_frame(self, connection: ConnectionState, frame: WebSocketFrameV1) -> None:
        try:
            connection.outbound_queue.put_nowait(frame)
        except asyncio.QueueFull:
            await self._send_error_and_close(
                connection,
                code=WebSocketErrorCode.WS_QUEUE_OVERFLOW,
                message="Outbound queue overflow",
            )

    async def _close_connection(self, connection: ConnectionState, *, reason: str) -> None:
        if connection.close_reason is not None:
            return
        connection.close_reason = reason
        if connection.sender_task is not None:
            connection.sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection.sender_task
        with contextlib.suppress(Exception):
            await connection.websocket.close()
        self._metrics.connection_closed(reason)

    def _remove_connection_subscriptions(self, connection: ConnectionState) -> None:
        for key in list(connection.subscriptions):
            subscribers = self._subscription_index.get(key)
            if subscribers is None:
                continue
            subscribers.discard(connection.connection_id)
            if not subscribers:
                self._subscription_index.pop(key, None)

    def _validate_message_size(self, raw: str) -> None:
        if len(raw.encode("utf-8")) > self._config.max_message_bytes:
            raise GatewayError(
                code=WebSocketErrorCode.WS_MESSAGE_TOO_LARGE,
                message="WebSocket message exceeds size limit",
                details={"maxBytes": self._config.max_message_bytes},
            )

    def _parse_frame(self, raw: str) -> WebSocketFrameV1:
        try:
            data = json.loads(raw)
            return parse_contract(WebSocketFrameV1, data)
        except (json.JSONDecodeError, ContractValidationError) as exc:
            raise GatewayError(
                code=WebSocketErrorCode.WS_INVALID_MESSAGE,
                message="Invalid WebSocket frame",
                details={"error": str(exc)},
            ) from exc
