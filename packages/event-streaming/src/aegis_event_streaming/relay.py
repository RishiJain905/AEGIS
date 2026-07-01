"""PostgreSQL outbox relay to Redis Streams."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from aegis_persistence.repositories.streaming import PostgresOutboxRepository
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.envelope import build_realtime_envelope, envelope_to_redis_fields
from aegis_event_streaming.metrics import StreamingMetrics
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM

logger = logging.getLogger(__name__)


class PostgresOutboxRelay:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        redis: Redis,
        *,
        config: StreamingConfig | None = None,
        metrics: StreamingMetrics | None = None,
        stream_key: str = DOMAIN_EVENTS_STREAM,
    ) -> None:
        self._session_maker = session_maker
        self._redis = redis
        self._config = config or StreamingConfig.from_env()
        self._metrics = metrics
        self._stream_key = stream_key
        self._claim_owner = f"relay-{uuid.uuid4().hex[:12]}"

    async def publish_batch(self) -> int:
        claims: list = []
        async with self._session_maker() as session:
            outbox = PostgresOutboxRepository(session)
            claims = await outbox.claim_batch(
                claim_owner=self._claim_owner,
                batch_size=self._config.outbox_batch_size,
                claim_ttl_seconds=self._config.outbox_claim_ttl_seconds,
            )
            await session.commit()

        if not claims:
            await self._refresh_outbox_metrics()
            return 0

        published = 0
        for claim in claims:
            started = time.perf_counter()
            try:
                envelope = build_realtime_envelope(claim.envelope, channel=claim.channel)
                message_id = await self._redis.xadd(
                    self._stream_key,
                    envelope_to_redis_fields(envelope),
                    maxlen=self._config.stream_maxlen,
                    approximate=True,
                )
                published_at = datetime.now(UTC)
                async with self._session_maker() as session:
                    outbox = PostgresOutboxRepository(session)
                    await outbox.mark_published(
                        outbox_id=claim.outbox_id,
                        redis_message_id=message_id,
                        published_at=published_at,
                    )
                    await session.commit()
                published += 1
                if self._metrics is not None:
                    self._metrics.record_publish(
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
            except Exception as exc:
                logger.exception(
                    "Failed to publish outbox row",
                    extra={"eventId": claim.event_id, "outboxId": claim.outbox_id},
                )
                async with self._session_maker() as session:
                    outbox = PostgresOutboxRepository(session)
                    await outbox.record_publish_failure(
                        outbox_id=claim.outbox_id,
                        error_message=str(exc),
                        retry_delay_seconds=self._config.outbox_retry_delay_seconds,
                    )
                    await session.commit()
                if self._metrics is not None:
                    self._metrics.record_publish_retry()

        await self._refresh_outbox_metrics()
        return published

    async def publish_until_empty(self, *, max_batches: int = 100) -> int:
        total = 0
        for _ in range(max_batches):
            count = await self.publish_batch()
            total += count
            if count == 0:
                break
        return total

    async def _refresh_outbox_metrics(self) -> None:
        if self._metrics is None:
            return
        async with self._session_maker() as session:
            outbox = PostgresOutboxRepository(session)
            unpublished = await outbox.count_unpublished()
            oldest_age = await outbox.oldest_unpublished_age_seconds()
        self._metrics.update_outbox_stats(
            unpublished=unpublished,
            oldest_age_seconds=oldest_age,
        )
