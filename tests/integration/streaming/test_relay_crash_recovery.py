"""Integration tests for relay crash recovery."""

from __future__ import annotations

import pytest
from aegis_event_streaming.config import StreamingConfig
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run


@pytest.mark.asyncio
async def test_stale_claims_are_republished(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAC", seed=9)
    await unit_of_work.append_event(
        make_test_event(event_id=sample_event_id(1), run_id=run.id, sequence=1)
    )
    await unit_of_work.commit()

    config = StreamingConfig.from_env()
    config = StreamingConfig(
        stream_maxlen=config.stream_maxlen,
        outbox_claim_ttl_seconds=1,
        outbox_batch_size=config.outbox_batch_size,
        outbox_poll_interval_seconds=config.outbox_poll_interval_seconds,
        outbox_retry_delay_seconds=1,
        consumer_max_attempts=config.consumer_max_attempts,
        consumer_block_ms=config.consumer_block_ms,
        consumer_pending_idle_ms=500,
    )
    relay = PostgresOutboxRelay(session_maker, redis_client, config=config)

    async with session_maker() as session:
        from aegis_persistence.repositories.streaming import PostgresOutboxRepository

        outbox = PostgresOutboxRepository(session)
        claims = await outbox.claim_batch(
            claim_owner="crash-simulator",
            batch_size=10,
            claim_ttl_seconds=3600,
        )
        await session.commit()
        assert len(claims) == 1

    import asyncio

    await asyncio.sleep(1.1)
    published = await relay.publish_until_empty()
    assert published == 1
