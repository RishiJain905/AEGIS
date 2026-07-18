"""Redis stream consumer for WebSocket gateway fan-out."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from aegis_contracts import RealtimeMessageEnvelopeV1
from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.envelope import redis_fields_to_envelope
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

EnvelopeHandler = Callable[[RealtimeMessageEnvelopeV1], Awaitable[None]]
StreamReadResponse = list[tuple[str, list[tuple[str, dict[str, Any]]]]]


def _coerce_redis_fields(fields: dict[str, Any]) -> dict[str, str]:
    def as_text(value: Any) -> str:
        return value.decode('utf-8') if isinstance(value, bytes) else str(value)

    return {as_text(key): as_text(value) for key, value in fields.items()}


class GatewayStreamConsumer:
    def __init__(
        self,
        redis: Redis,
        handler: EnvelopeHandler,
        *,
        consumer_name: str,
        consumer_group: str,
        stream_key: str = DOMAIN_EVENTS_STREAM,
        config: StreamingConfig | None = None,
    ) -> None:
        self._redis = redis
        self._handler = handler
        self._consumer_name = consumer_name
        self._consumer_group = consumer_group
        self._stream_key = stream_key
        self._config = config or StreamingConfig.from_env()
        self._running = False

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self._stream_key,
                self._consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run(self) -> None:
        self._running = True
        await self.ensure_group()
        while self._running:
            try:
                processed = await self._process_once()
                if processed == 0:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gateway stream consumer loop failed")
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        self._running = False

    async def _process_once(self) -> int:
        # Redis streams can be recreated independently of the API process. Reconcile
        # the group before every read so a transient NOGROUP does not strand the
        # gateway after a Redis restart or data reset.
        await self.ensure_group()
        response = await self._redis.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            streams={self._stream_key: ">"},
            count=20,
            block=self._config.consumer_block_ms,
        )
        if not response:
            return 0

        processed = 0
        for _stream, messages in cast(StreamReadResponse, response):
            for message_id, raw_fields in messages:
                fields = _coerce_redis_fields(raw_fields)
                envelope = redis_fields_to_envelope(fields)
                envelope = envelope.model_copy(update={"stream_message_id": message_id})
                await self._handler(envelope)
                await self._redis.xack(self._stream_key, self._consumer_group, message_id)
                processed += 1
        return processed
