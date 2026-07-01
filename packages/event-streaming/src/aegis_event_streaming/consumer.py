"""Idempotent Redis Streams consumer with DLQ support."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

from aegis_contracts import (
    ConsumerCursorV1,
    DeadLetterRecordV1,
    RealtimeMessageEnvelopeV1,
    StreamingErrorCode,
)
from aegis_contracts.versioning import (
    CONSUMER_CURSOR_SCHEMA_VERSION,
    DEAD_LETTER_RECORD_SCHEMA_VERSION,
)
from aegis_persistence.repositories.streaming import (
    PostgresConsumerCursorRepository,
    PostgresConsumerReceiptRepository,
    PostgresDeadLetterRepository,
)
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.envelope import (
    build_realtime_envelope,
    envelope_to_redis_fields,
    redis_fields_to_envelope,
)
from aegis_event_streaming.errors import StreamingError
from aegis_event_streaming.metrics import StreamingMetrics
from aegis_event_streaming.stream_names import (
    DOMAIN_EVENTS_CONSUMER_GROUP,
    DOMAIN_EVENTS_DLQ_STREAM,
    DOMAIN_EVENTS_STREAM,
)

logger = logging.getLogger(__name__)

MessageHandler = Callable[[RealtimeMessageEnvelopeV1], Awaitable[None]]
StreamReadResponse = list[tuple[str, list[tuple[str, dict[str, Any]]]]]


def _coerce_redis_fields(fields: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in fields.items()}


class IdempotentStreamConsumer:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        redis: Redis,
        handler: MessageHandler,
        *,
        consumer_name: str,
        consumer_group: str = DOMAIN_EVENTS_CONSUMER_GROUP,
        stream_key: str = DOMAIN_EVENTS_STREAM,
        dlq_stream_key: str = DOMAIN_EVENTS_DLQ_STREAM,
        config: StreamingConfig | None = None,
        metrics: StreamingMetrics | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._redis = redis
        self._handler = handler
        self._consumer_name = consumer_name
        self._consumer_group = consumer_group
        self._stream_key = stream_key
        self._dlq_stream_key = dlq_stream_key
        self._config = config or StreamingConfig.from_env()
        self._metrics = metrics
        self._attempt_counts: dict[str, int] = {}

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

    async def process_once(self) -> int:
        await self.ensure_group()
        response = await self._redis.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            streams={self._stream_key: ">"},
            count=10,
            block=self._config.consumer_block_ms,
        )
        if not response:
            await self._refresh_consumer_metrics()
            return 0

        processed = 0
        for _stream, messages in cast(StreamReadResponse, response):
            for message_id, raw_fields in messages:
                fields = _coerce_redis_fields(raw_fields)
                if await self._process_message(str(message_id), fields):
                    processed += 1
        await self._refresh_consumer_metrics()
        return processed

    async def reclaim_pending(self) -> int:
        await self.ensure_group()
        result = await self._redis.xautoclaim(
            self._stream_key,
            self._consumer_group,
            self._consumer_name,
            min_idle_time=self._config.consumer_pending_idle_ms,
            start_id="0-0",
            count=10,
        )
        reclaimed = 0
        if result and len(result) >= 2:
            messages = cast(list[tuple[str, dict[str, Any]]], result[1])
            for message_id, raw_fields in messages:
                if raw_fields and await self._process_message(
                    str(message_id),
                    _coerce_redis_fields(raw_fields),
                ):
                    reclaimed += 1
        await self._refresh_consumer_metrics()
        return reclaimed

    async def _process_message(self, message_id: str, fields: dict[str, str]) -> bool:
        envelope = redis_fields_to_envelope(fields)
        envelope = envelope.model_copy(update={"stream_message_id": message_id})
        consumer_id = f"{self._consumer_group}:{self._consumer_name}"

        async with self._session_maker() as session:
            receipts = PostgresConsumerReceiptRepository(session)
            if await receipts.has_receipt(
                consumer_id=consumer_id,
                event_id=envelope.event.event_id,
            ):
                await self._redis.xack(self._stream_key, self._consumer_group, message_id)
                await session.commit()
                return False

        try:
            await self._handler(envelope)
        except Exception as exc:
            attempts = self._attempt_counts.get(message_id, 0) + 1
            self._attempt_counts[message_id] = attempts
            if attempts >= self._config.consumer_max_attempts:
                await self._send_to_dlq(envelope, message_id, consumer_id, exc, attempts)
                await self._redis.xack(self._stream_key, self._consumer_group, message_id)
                self._attempt_counts.pop(message_id, None)
                return False
            raise StreamingError(
                code=StreamingErrorCode.STREAM_POISON_MESSAGE,
                message=f"Handler failed for {envelope.event.event_id}",
                details={"eventId": envelope.event.event_id, "attempts": attempts},
            ) from exc

        now = datetime.now(UTC)
        async with self._session_maker() as session:
            receipts = PostgresConsumerReceiptRepository(session)
            recorded = await receipts.try_record(
                consumer_id=consumer_id,
                event_id=envelope.event.event_id,
                stream_message_id=message_id,
                processed_at=now,
            )
            if recorded:
                cursor = ConsumerCursorV1(
                    schema_version=CONSUMER_CURSOR_SCHEMA_VERSION,
                    consumer_group=self._consumer_group,
                    consumer_name=self._consumer_name,
                    stream_key=self._stream_key,
                    last_event_id=envelope.event.event_id,
                    last_run_id=envelope.event.run_id,
                    last_sequence=envelope.event.sequence,
                    updated_at=now,
                )
                await PostgresConsumerCursorRepository(session).upsert(cursor)
            await session.commit()

        await self._redis.xack(self._stream_key, self._consumer_group, message_id)
        self._attempt_counts.pop(message_id, None)
        return True

    async def _send_to_dlq(
        self,
        envelope: RealtimeMessageEnvelopeV1,
        message_id: str,
        consumer_id: str,
        exc: Exception,
        attempts: int,
    ) -> None:
        now = datetime.now(UTC)
        record = DeadLetterRecordV1(
            schema_version=DEAD_LETTER_RECORD_SCHEMA_VERSION,
            event_id=envelope.event.event_id,
            run_id=envelope.event.run_id,
            sequence=envelope.event.sequence,
            consumer_id=consumer_id,
            stream_key=self._stream_key,
            stream_message_id=message_id,
            error_code=StreamingErrorCode.STREAM_POISON_MESSAGE.value,
            error_message=str(exc)[:2048],
            attempt_count=attempts,
            original_envelope=envelope.model_dump(mode="json", by_alias=True),
            created_at=now,
        )
        async with self._session_maker() as session:
            await PostgresDeadLetterRepository(session).insert(record)
            await session.commit()

        dlq_envelope = build_realtime_envelope(
            envelope.event,
            channel="dlq",
            stream_message_id=message_id,
            published_at=now,
        )
        dlq_fields: dict[str, str] = {
            **envelope_to_redis_fields(dlq_envelope),
            "errorCode": record.error_code,
            "errorMessage": record.error_message,
            "attemptCount": str(attempts),
        }
        await self._redis.xadd(
            self._dlq_stream_key,
            cast(dict[Any, Any], dlq_fields),
            maxlen=self._config.stream_maxlen,
            approximate=True,
        )
        if self._metrics is not None:
            async with self._session_maker() as session:
                count = await PostgresDeadLetterRepository(session).count_all()
            self._metrics.update_dlq_count(count)

    async def _refresh_consumer_metrics(self) -> None:
        if self._metrics is None:
            return
        try:
            pending_info = await self._redis.xpending(self._stream_key, self._consumer_group)
            pending = int(pending_info["pending"]) if pending_info else 0
            stream_len = await self._redis.xlen(self._stream_key)
            self._metrics.update_consumer_stats(lag=stream_len, pending=pending)
        except Exception:
            logger.debug("Unable to refresh consumer metrics", exc_info=True)
