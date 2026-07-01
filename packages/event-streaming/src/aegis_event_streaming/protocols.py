"""Outbox relay and consumer protocols."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from aegis_contracts import RealtimeMessageEnvelopeV1


class OutboxRelay(Protocol):
    async def publish_batch(self) -> int: ...


MessageHandler = Callable[[RealtimeMessageEnvelopeV1], Awaitable[None]]
PoisonHandler = Callable[[RealtimeMessageEnvelopeV1, Exception], Awaitable[None]]


class IdempotentConsumer(Protocol):
    async def process_once(self) -> int: ...

    async def reclaim_pending(self) -> int: ...
