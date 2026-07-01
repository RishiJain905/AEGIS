"""Integration tests for dead-letter handling."""

from __future__ import annotations

import pytest
from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.consumer import IdempotentStreamConsumer
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_DLQ_STREAM
from aegis_persistence.repositories.streaming import PostgresDeadLetterRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.streaming.helpers import make_test_event, seed_run, sample_event_id


@pytest.mark.asyncio
async def test_poison_message_reaches_dead_letter_path(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAE", seed=13)
    await unit_of_work.append_event(
        make_test_event(event_id=sample_event_id(3), run_id=run.id, sequence=1)
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
        consumer_max_attempts=1,
        consumer_block_ms=1000,
        consumer_pending_idle_ms=config.consumer_pending_idle_ms,
    )

    async def poison_handler(_envelope) -> None:
        raise RuntimeError("intentional poison")

    consumer = IdempotentStreamConsumer(
        session_maker,
        redis_client,
        poison_handler,
        consumer_name="poison-consumer",
        config=config,
    )
    await consumer.ensure_group()
    await consumer.process_once()

    dlq_len = await redis_client.xlen(DOMAIN_EVENTS_DLQ_STREAM)
    assert dlq_len >= 1

    async with session_maker() as session:
        count = await PostgresDeadLetterRepository(session).count_all()
        assert count >= 1
