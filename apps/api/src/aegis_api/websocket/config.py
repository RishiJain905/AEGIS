"""WebSocket gateway configuration."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts import AegisSettings


@dataclass(frozen=True)
class GatewayConfig:
    ws_path: str
    enabled: bool
    max_connections: int
    max_queue_depth: int
    max_message_bytes: int
    heartbeat_interval_seconds: int
    idle_timeout_seconds: int
    dev_auth_enabled: bool
    dev_auth_token: str
    consumer_group: str
    snapshot_gap_threshold: int
    hello_timeout_seconds: int = 10
    # How long a subscribe backfill may wait for room in the connection's outbound queue.
    #
    # The backfill is a burst the *server* generates, sized by how far behind the client's
    # cursor is, and it is written from the connection's own receive-loop task — so waiting
    # for the sender to drain costs nothing but that one connection's turnaround. Refusing
    # to wait instead made every subscribe past `max_queue_depth` events overrun the queue
    # and close the socket, which no client can recover from by reconnecting: the cursor it
    # reconnects with is the same one that overran the queue. Only a client that has stopped
    # reading at all can exhaust this, and that is the slow-client case the overflow path
    # already handles.
    backfill_enqueue_timeout_seconds: float = 5.0
    # Recovery for a subscription the overflow path parked.
    #
    # Pausing is how the gateway protects its own memory from a client that stopped
    # reading, but nothing on the server ever un-paused one: the socket stayed open,
    # heartbeats kept passing, and the subscription delivered nothing for the rest of the
    # connection's life. Recovery depended entirely on the client noticing
    # `snapshot_required` and re-subscribing — so a client that missed it sat on a live,
    # healthy-looking, permanently silent socket.
    #
    # The heartbeat sweep now resolves every paused subscription one way or the other. A
    # queue that has drained back to this fraction of its bound has capacity again, and the
    # subscription resumes: the next live event is a sequence ahead of its cursor, which the
    # gap-fill path already repairs from PostgreSQL.
    paused_resume_queue_ratio: float = 0.5
    # A queue still full after this long belongs to a client that is not reading at all.
    # Its connection is closed so the client reconnects and re-subscribes from a cursor it
    # can actually serve, rather than holding a subscription that will never deliver again.
    paused_subscription_grace_seconds: float = 60.0

    @property
    def paused_resume_queue_depth(self) -> int:
        """Queue depth at or below which a paused subscription may resume."""
        return int(self.max_queue_depth * self.paused_resume_queue_ratio)

    @classmethod
    def from_settings(cls, settings: AegisSettings) -> GatewayConfig:
        dev_auth_enabled = settings.AEGIS_WS_DEV_AUTH_ENABLED
        if settings.AEGIS_ENV.value == "production" and not settings.AEGIS_WS_DEV_AUTH_ENABLED:
            dev_auth_enabled = False
        return cls(
            ws_path=settings.AEGIS_WS_PATH,
            enabled=settings.AEGIS_WS_ENABLED,
            max_connections=settings.AEGIS_WS_MAX_CONNECTIONS,
            max_queue_depth=settings.AEGIS_WS_MAX_QUEUE_DEPTH,
            max_message_bytes=settings.AEGIS_WS_MAX_MESSAGE_BYTES,
            heartbeat_interval_seconds=settings.AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS,
            idle_timeout_seconds=settings.AEGIS_WS_IDLE_TIMEOUT_SECONDS,
            dev_auth_enabled=dev_auth_enabled,
            dev_auth_token=settings.AEGIS_WS_DEV_AUTH_TOKEN,
            consumer_group=settings.AEGIS_WS_GATEWAY_CONSUMER_GROUP,
            snapshot_gap_threshold=settings.AEGIS_WS_SNAPSHOT_GAP_THRESHOLD,
        )
