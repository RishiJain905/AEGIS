"""Integration tests for stale pending message recovery."""

from __future__ import annotations

import asyncio

import pytest
from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.consumer import IdempotentStreamConsumer
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run


@pytest.mark.asyncio
async def test_pending_messages_reclaimed_after_idle(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAD", seed=11)
    await unit_of_work.append_event(
        make_test_event(event_id=sample_event_id(2), run_id=run.id, sequence=1)
    )
    await unit_of_work.commit()

    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()

    config = StreamingConfig.from_env()
    config = StreamingConfig(
        stream_maxlen=config.stream_maxlen,
        outbox_claim_ttl_seconds=config.outbox_claim_ttl_seconds,
        outbox_batch_size=config.outbox_batch_size,
        outbox_poll_interval_seconds=config.outbox_poll_interval_seconds,
        outbox_retry_delay_seconds=config.outbox_retry_delay_seconds,
        consumer_max_attempts=config.consumer_max_attempts,
        consumer_block_ms=100,
        consumer_pending_idle_ms=500,
    )

    processed = {"value": 0}

    async def handler(_envelope) -> None:
        processed["value"] += 1

    consumer_a = IdempotentStreamConsumer(
        session_maker,
        redis_client,
        handler,
        consumer_name="pending-consumer-a",
        config=config,
    )
    await consumer_a.ensure_group()
    await redis_client.xreadgroup(
        groupname=consumer_a._consumer_group,
        consumername=consumer_a._consumer_name,
        streams={consumer_a._stream_key: ">"},
        count=1,
        block=1000,
    )

    await asyncio.sleep(0.7)
    consumer_b = IdempotentStreamConsumer(
        session_maker,
        redis_client,
        handler,
        consumer_name="pending-consumer-b",
        config=config,
    )
    reclaimed = await consumer_b.reclaim_pending()
    assert reclaimed >= 1
    assert processed["value"] >= 1
