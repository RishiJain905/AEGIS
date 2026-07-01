"""Streaming observability status endpoint."""

from __future__ import annotations

from typing import Any

from aegis_event_streaming.metrics import GLOBAL_METRICS
from aegis_event_streaming.redis_client import create_redis_client
from aegis_event_streaming.stream_names import (
    DOMAIN_EVENTS_CONSUMER_GROUP,
    DOMAIN_EVENTS_DLQ_STREAM,
    DOMAIN_EVENTS_STREAM,
)
from aegis_persistence.repositories.streaming import (
    PostgresDeadLetterRepository,
    PostgresOutboxRepository,
)
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aegis_api.db.session import db_session

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


class StreamingStatusResponse(BaseModel):
    outbox_unpublished: int = Field(alias="outboxUnpublished")
    outbox_oldest_age_seconds: float | None = Field(alias="outboxOldestAgeSeconds")
    stream_length: int = Field(alias="streamLength")
    stream_key: str = Field(alias="streamKey")
    consumer_group: str = Field(alias="consumerGroup")
    pending_messages: int = Field(alias="pendingMessages")
    dlq_stream_length: int = Field(alias="dlqStreamLength")
    dlq_count: int = Field(alias="dlqCount")
    metrics: dict[str, Any]

    model_config = {"populate_by_name": True}


@router.get("/streaming/status", response_model=StreamingStatusResponse)
async def streaming_status(request: Request) -> StreamingStatusResponse:
    settings = request.app.state.settings
    redis = create_redis_client(settings)
    try:
        stream_length = int(await redis.xlen(DOMAIN_EVENTS_STREAM))
        dlq_stream_length = int(await redis.xlen(DOMAIN_EVENTS_DLQ_STREAM))
        pending = 0
        try:
            pending_info = await redis.xpending(DOMAIN_EVENTS_STREAM, DOMAIN_EVENTS_CONSUMER_GROUP)
            pending = int(pending_info["pending"]) if pending_info else 0
        except Exception:
            pending = 0
    finally:
        await redis.aclose()

    async with db_session() as session:
        outbox = PostgresOutboxRepository(session)
        unpublished = await outbox.count_unpublished()
        oldest_age = await outbox.oldest_unpublished_age_seconds()
        dlq_count = await PostgresDeadLetterRepository(session).count_all()

    GLOBAL_METRICS.update_outbox_stats(unpublished=unpublished, oldest_age_seconds=oldest_age)
    GLOBAL_METRICS.update_consumer_stats(lag=stream_length, pending=pending)
    GLOBAL_METRICS.update_dlq_count(dlq_count)

    return StreamingStatusResponse(
        outbox_unpublished=unpublished,
        outbox_oldest_age_seconds=oldest_age,
        stream_length=stream_length,
        stream_key=DOMAIN_EVENTS_STREAM,
        consumer_group=DOMAIN_EVENTS_CONSUMER_GROUP,
        pending_messages=pending,
        dlq_stream_length=dlq_stream_length,
        dlq_count=dlq_count,
        metrics=GLOBAL_METRICS.snapshot(),
    )
