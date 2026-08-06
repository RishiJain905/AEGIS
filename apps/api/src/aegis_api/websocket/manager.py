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
    WebSocketRunTerminatedPayloadV1,
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
from aegis_api.websocket.disclosure import RunDisclosureTracker
from aegis_api.websocket.errors import GatewayError
from aegis_api.websocket.metrics import GLOBAL_GATEWAY_METRICS, GatewayMetrics
from aegis_api.websocket.recovery import SubscriptionRecoveryService, envelope_from_domain_event

logger = logging.getLogger(__name__)

# The lifecycle event that ends a run. Both a manual STOP and the ticker reaching the
# scenario horizon emit it, as does a quarantined run taken down through the real lifecycle
# path — so this is the one signal that means "no further event will ever be published for
# this run". Statuses written straight onto the run row without a lifecycle command emit
# nothing, which is why subscribe-time also checks the persisted status.
_RUN_TERMINAL_EVENT = "sim.run.stopped"


def _is_run_active(status: str) -> bool:
    """Whether a run can still produce events. Imported lazily, as the fog seeding is."""
    from aegis_simulation.disclosure_resolver import ACTIVE_RUN_STATUSES

    return status in ACTIVE_RUN_STATUSES


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
        # Fog of war: one disclosure tracker per subscribed run, seeded from persisted truth
        # on subscribe and updated as reveal/alert/lifecycle events flow through fan-out.
        # Redacts undisclosed attacker status changes on every operator-bound frame.
        self._run_trackers: dict[str, RunDisclosureTracker] = {}
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
        # Fold reveal/alert/lifecycle events into the run's disclosure state before fan-out
        # so already-connected clients' future frames redact/reveal correctly.
        tracker = self._run_trackers.get(envelope.event.run_id)
        if tracker is not None:
            tracker.note_event(envelope.event)

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

        # The run just ended. Every subscription on it is now a subscription to a stream that
        # will never produce another event, and leaving them registered is how a client ends
        # up holding an open, silent socket waiting on a finished run. Announce the ending
        # after the lifecycle event itself has been delivered, then unregister.
        if envelope.event.type == _RUN_TERMINAL_EVENT:
            await self._terminate_run_subscriptions(envelope.event.run_id, status="stopped")

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
            # Seed/refresh fog-of-war disclosure from persisted truth before any backfill so
            # the resync path redacts by current disclosure and converges after reveals.
            run_status = await self._seed_run_tracker(session, payload.run_id)
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
            # Backpressure, not overrun. The backfill is as long as the client's cursor is
            # stale, so on any run older than `max_queue_depth` events it used to fill the
            # queue outright: the overflow path paused the subscription, and the
            # resync-complete frame below then failed to enqueue and closed the socket. The
            # client reconnected with the same stale cursor and hit it again — every socket
            # dying inside a second, forever, with the operator's board only ever advancing
            # via the HTTP resync each reconnect triggered.
            if not await self._enqueue_event(
                connection, subscription, envelope, wait_for_capacity=True
            ):
                break
            delivered += 1

        # A paused subscription did not finish its backfill, so there is no resync to
        # announce — and announcing it would mean enqueuing onto the queue that just
        # overflowed. The client has already been sent `snapshot_required`.
        if delivered > 0 and not subscription.paused:
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

        # Subscribing to a run that has already ended is legitimate — a debrief replays the
        # whole stream from cursor 0 — so the backfill above still runs. What must not happen
        # is the subscription outliving it: no live event will ever arrive for a terminal run,
        # so the client would wait on a silent socket and the gateway would hold an entry in
        # the fan-out index nothing can ever match. Say the run has ended, then unregister.
        if run_status is not None and not _is_run_active(run_status):
            await self._announce_run_terminated(
                connection,
                run_id=payload.run_id,
                status=run_status,
                trace_id=frame.trace_id,
            )
            await self._drop_subscription(connection, key)

    async def _seed_run_tracker(self, session: AsyncSession, run_id: str) -> str | None:
        """Build/refresh the run's disclosure tracker from persisted truth.

        Overwriting with the authoritative current state on each subscribe is safe: it is a
        superset of the incremental fan-out updates, so live redaction stays correct and a
        post-reveal resync converges. Failures degrade to no redaction rather than dropping
        the subscription — fog is best-effort transport hygiene, never a hard dependency.

        Returns the run's persisted lifecycle status, which the caller needs anyway to decide
        whether the subscription has a future; `None` when it could not be read, in which case
        the subscription is treated as live (fail-soft, same as the fog seeding itself).
        """
        from aegis_persistence.repositories.postgres import PostgresRunRepository

        from aegis_api.runs.service import get_run_command_service

        try:
            run = await PostgresRunRepository(session).get_by_id(run_id)
            if run is None:
                return None
            disclosure = await get_run_command_service().resolve_disclosure(session, run)
            if not disclosure.has_hidden_state:
                self._run_trackers.pop(run_id, None)
                return run.status
            self._run_trackers[run_id] = RunDisclosureTracker(
                governing_map=dict(disclosure.governing_map),
                revealed_condition_ids=set(disclosure.inputs.revealed_condition_ids),
                alerted_asset_ids=set(disclosure.inputs.alerted_asset_ids),
                active=_is_run_active(run.status),
            )
            return run.status
        except Exception:  # noqa: BLE001 — never fail a subscription over fog seeding
            logger.warning("Fog-of-war tracker seed failed for run %s", run_id, exc_info=True)
            return None

    async def _announce_run_terminated(
        self,
        connection: ConnectionState,
        *,
        run_id: str,
        status: str,
        trace_id: str | None = None,
    ) -> None:
        """Tell one client its run has ended. Queued, so it lands after the run's own events."""
        await self._send_frame(
            connection,
            build_websocket_frame(
                message_type=WebSocketMessageType.RUN_TERMINATED,
                trace_id=trace_id or new_trace_id(),
                sent_at=datetime.now(UTC),
                payload=WebSocketRunTerminatedPayloadV1(run_id=run_id, status=status),
            ),
        )
        self._metrics.record_subscription_terminated()

    async def _terminate_run_subscriptions(self, run_id: str, *, status: str) -> None:
        """Close out every subscription on a run that has just ended.

        Covers every channel, not just the one the terminal event arrived on: the run is over
        for all of them. The run's disclosure tracker goes too — with no subscriber left there
        is nothing to redact, and holding it would leak one tracker per run for the lifetime
        of the gateway process.
        """
        async with self._lock:
            keys = [key for key in self._subscription_index if key[0] == run_id]
            targets = [(key, list(self._subscription_index.get(key, set()))) for key in keys]

        for key, connection_ids in targets:
            for connection_id in connection_ids:
                connection = self._connections.get(connection_id)
                if connection is None or connection.get_subscription(*key) is None:
                    continue
                await self._announce_run_terminated(connection, run_id=run_id, status=status)
                await self._drop_subscription(connection, key)

        self._run_trackers.pop(run_id, None)

    async def _drop_subscription(
        self,
        connection: ConnectionState,
        key: tuple[str, str],
    ) -> None:
        """Unregister one subscription from both the connection and the fan-out index."""
        connection.subscriptions.pop(key, None)
        async with self._lock:
            subscribers = self._subscription_index.get(key)
            if subscribers is not None:
                subscribers.discard(connection.connection_id)
                if not subscribers:
                    self._subscription_index.pop(key, None)

    async def _handle_unsubscribe(
        self,
        connection: ConnectionState,
        frame: WebSocketFrameV1,
    ) -> None:
        payload = parse_contract(WebSocketUnsubscribePayloadV1, frame.payload)
        await self._drop_subscription(
            connection,
            connection.subscription_key(payload.run_id, payload.channel),
        )

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
                if not await self._enqueue_event(connection, subscription, gap_envelope):
                    # The subscription is paused and the client has been told to take a
                    # snapshot; pushing the rest of the fill at a full queue only repeats
                    # that message.
                    return

        await self._enqueue_event(connection, subscription, envelope)

    async def _enqueue_event(
        self,
        connection: ConnectionState,
        subscription: SubscriptionState,
        envelope: RealtimeMessageEnvelopeV1,
        *,
        wait_for_capacity: bool = False,
    ) -> bool:
        # Single choke point for every operator-bound event (live, resync backfill, and gap
        # fill). Fog-of-war redaction rewrites undisclosed attacker status changes here so no
        # raw frame ever leaks truth, regardless of delivery path.
        #
        # Returns False only when the queue overflowed, meaning the caller must stop feeding
        # this subscription; a suppressed duplicate is a successful no-op.
        tracker = self._run_trackers.get(envelope.event.run_id)
        if tracker is not None:
            envelope = tracker.redact(envelope)

        if not connection.remember_event_id(envelope.event.event_id):
            self._metrics.record_duplicate()
            return True

        frame = build_websocket_frame(
            message_type=WebSocketMessageType.EVENT,
            trace_id=envelope.event.trace_id,
            sent_at=datetime.now(UTC),
            payload=WebSocketEventPayloadV1(envelope=envelope),
        )
        try:
            if wait_for_capacity:
                # Yields to the sender loop, which is the only thing that drains this queue.
                # Live fan-out must never wait here — it runs on the shared Redis consumer
                # task, where one slow client would stall every other connection.
                await asyncio.wait_for(
                    connection.outbound_queue.put(frame),
                    timeout=self._config.backfill_enqueue_timeout_seconds,
                )
            else:
                connection.outbound_queue.put_nowait(frame)
        except (asyncio.QueueFull, TimeoutError):
            await self._handle_queue_overflow(connection, subscription, envelope.event.sequence)
            return False
        subscription.last_applied_sequence = envelope.event.sequence
        self._metrics.update_queue_depth(connection.outbound_queue.qsize())
        return True

    async def _handle_queue_overflow(
        self,
        connection: ConnectionState,
        subscription: SubscriptionState,
        from_sequence: int,
    ) -> None:
        subscription.pause(datetime.now(UTC))
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
                if await self._sweep_paused_subscriptions(connection, now):
                    # The sweep closed the connection; a ping onto a closed socket would
                    # only raise out of the heartbeat loop.
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

    async def _sweep_paused_subscriptions(
        self,
        connection: ConnectionState,
        now: datetime,
    ) -> bool:
        """Resolve every parked subscription on one connection. Returns True if it closed it.

        Pausing bounds the gateway's memory; it is not a resting state. A subscription that
        stays paused delivers nothing for the rest of the connection's life, and the only
        thing that used to lift it was the client re-subscribing after noticing
        `snapshot_required` — which a client that had stopped reading is, by construction,
        least likely to do.

        Two outcomes, no third: the queue has drained back under the resume watermark and the
        subscription resumes (its cursor is behind, and the next live event's gap fill repairs
        that from PostgreSQL), or it has not drained inside the grace window and the
        connection is closed so the client reconnects onto a subscription that can be served.
        """
        paused = [
            subscription
            for subscription in connection.subscriptions.values()
            if subscription.paused
        ]
        if not paused:
            return False

        if connection.outbound_queue.qsize() > self._config.paused_resume_queue_depth:
            stalled = max(subscription.paused_seconds(now) for subscription in paused)
            if stalled <= self._config.paused_subscription_grace_seconds:
                return False
            logger.info(
                "Closing connection %s: subscription paused for %.0fs without draining",
                connection.connection_id,
                stalled,
            )
            await self._send_error_and_close(
                connection,
                code=WebSocketErrorCode.WS_QUEUE_OVERFLOW,
                message="Subscription paused too long without draining",
            )
            return True

        for subscription in paused:
            subscription.resume()
            self._metrics.record_subscription_resumed()
            await self._send_frame(
                connection,
                build_websocket_frame(
                    message_type=WebSocketMessageType.WARNING,
                    trace_id=new_trace_id(),
                    sent_at=now,
                    payload=WebSocketWarningPayloadV1(
                        code="WS_SUBSCRIPTION_RESUMED",
                        message="Live delivery resumed after backpressure",
                        run_id=subscription.run_id,
                        details={"fromSequence": subscription.last_applied_sequence + 1},
                    ),
                ),
            )
        return False

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
