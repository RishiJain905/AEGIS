"""Integration tests for idempotent stream consumers."""

from __future__ import annotations

import pytest
from aegis_event_streaming.consumer import IdempotentStreamConsumer
from aegis_event_streaming.envelope import build_realtime_envelope, envelope_to_redis_fields
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_duplicate_effects(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAB", seed=7)
    event = make_test_event(event_id=sample_event_id(0), run_id=run.id, sequence=1)
    await unit_of_work.append_event(event)
    await unit_of_work.commit()

    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()

    effect_count = {"value": 0}

    async def handler(envelope) -> None:
        effect_count["value"] += 1

    consumer = IdempotentStreamConsumer(
        session_maker,
        redis_client,
        handler,
        consumer_name="dup-test-consumer",
    )
    await consumer.ensure_group()
    await consumer.process_once()
    assert effect_count["value"] == 1

    envelope = build_realtime_envelope(event)
    await redis_client.xadd(DOMAIN_EVENTS_STREAM, envelope_to_redis_fields(envelope))
    await consumer.process_once()
    assert effect_count["value"] == 1
