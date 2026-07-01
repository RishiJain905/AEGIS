"""PostgreSQL backfill republication to Redis Streams."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aegis_contracts import BackfillRequestV1, BackfillResultV1
from aegis_contracts.versioning import BACKFILL_RESULT_SCHEMA_VERSION
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.envelope import build_realtime_envelope, envelope_to_redis_fields
from aegis_event_streaming.metrics import StreamingMetrics
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM

logger = logging.getLogger(__name__)


class PostgresBackfillService:
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

    async def backfill(self, request: BackfillRequestV1) -> BackfillResultV1:
        stream_key = request.stream_key or self._stream_key
        existing_event_ids: set[str] = set()
        if not request.force:
            existing_event_ids = await self._load_existing_event_ids(stream_key)

        async with self._session_maker() as session:
            events = await PostgresEventQueryRepository(session).list_for_backfill(
                run_id=request.run_id,
                from_sequence=request.from_sequence,
                to_sequence=request.to_sequence,
            )

        published = 0
        skipped = 0
        for event in events:
            if not request.force and event.event_id in existing_event_ids:
                skipped += 1
                continue
            envelope = build_realtime_envelope(event)
            await self._redis.xadd(
                stream_key,
                envelope_to_redis_fields(envelope),
                maxlen=self._config.stream_maxlen,
                approximate=True,
            )
            published += 1
            existing_event_ids.add(event.event_id)

        if self._metrics is not None:
            self._metrics.record_backfill()

        return BackfillResultV1(
            schema_version=BACKFILL_RESULT_SCHEMA_VERSION,
            run_id=request.run_id,
            events_scanned=len(events),
            events_published=published,
            events_skipped=skipped,
            completed_at=datetime.now(UTC),
        )

    async def _load_existing_event_ids(self, stream_key: str) -> set[str]:
        event_ids: set[str] = set()
        last_id = "-"
        while True:
            entries = await self._redis.xrange(stream_key, min=last_id, max="+", count=100)
            if not entries:
                break
            for message_id, fields in entries:
                if message_id == last_id and last_id != "-":
                    continue
                event_id = fields.get("eventId")
                if event_id:
                    event_ids.add(event_id)
                last_id = message_id
            if len(entries) < 100:
                break
        return event_ids
