"""Per-connection state, bounded queues, and deduplication."""

from __future__ import annotations

import asyncio
import secrets
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from aegis_contracts import WebSocketFrameV1
from fastapi import WebSocket

from aegis_api.websocket.auth import AuthenticatedPrincipal


def new_connection_id() -> str:
    suffix = "".join(secrets.choice("0123456789abcdef") for _ in range(16))
    return f"conn_{suffix}"


def new_trace_id() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    body = "".join(secrets.choice(alphabet) for _ in range(26))
    return f"trc_{body}"


@dataclass
class SubscriptionState:
    run_id: str
    channel: str
    last_applied_sequence: int
    paused: bool = False
    # When the overflow path parked this subscription. The gateway sweeps paused
    # subscriptions on every heartbeat and needs to know how long each has been waiting:
    # a queue that drains is resumed, one that never drains has its connection closed.
    # `None` whenever `paused` is False — the two are set and cleared together.
    paused_at: datetime | None = None

    def pause(self, now: datetime) -> None:
        self.paused = True
        self.paused_at = now

    def resume(self) -> None:
        self.paused = False
        self.paused_at = None

    def paused_seconds(self, now: datetime) -> float:
        if self.paused_at is None:
            return 0.0
        return (now - self.paused_at).total_seconds()


@dataclass
class ConnectionState:
    connection_id: str
    websocket: WebSocket
    principal: AuthenticatedPrincipal
    outbound_queue: asyncio.Queue[WebSocketFrameV1]
    subscriptions: dict[tuple[str, str], SubscriptionState] = field(default_factory=dict)
    seen_event_ids: deque[str] = field(default_factory=lambda: deque(maxlen=4096))
    seen_event_id_set: set[str] = field(default_factory=set)
    last_pong_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    close_reason: str | None = None
    sender_task: asyncio.Task[None] | None = None

    def subscription_key(self, run_id: str, channel: str) -> tuple[str, str]:
        return (run_id, channel)

    def get_subscription(self, run_id: str, channel: str) -> SubscriptionState | None:
        return self.subscriptions.get(self.subscription_key(run_id, channel))

    def remember_event_id(self, event_id: str) -> bool:
        if event_id in self.seen_event_id_set:
            return False
        if len(self.seen_event_ids) == self.seen_event_ids.maxlen:
            oldest = self.seen_event_ids.popleft()
            self.seen_event_id_set.discard(oldest)
        self.seen_event_ids.append(event_id)
        self.seen_event_id_set.add(event_id)
        return True

    def touch_pong(self) -> None:
        self.last_pong_at = datetime.now(UTC)

    def idle_seconds(self) -> float:
        return (datetime.now(UTC) - self.last_pong_at).total_seconds()
