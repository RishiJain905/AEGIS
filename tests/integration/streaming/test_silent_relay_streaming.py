"""End-to-end streaming test with persisted simulation."""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import BackfillRequestV1
from aegis_contracts.versioning import BACKFILL_REQUEST_SCHEMA_VERSION
from aegis_event_streaming.backfill import PostgresBackfillService
from aegis_event_streaming.consumer import IdempotentStreamConsumer
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository

FIXTURE = Path("scenarios/_fixtures/valid-minimal")


@pytest.mark.asyncio
async def test_persisted_simulation_events_reach_redis(
    session_maker,
    redis_client,
) -> None:
    from aegis_simulation.runner import _run_persisted

    result = await _run_persisted(FIXTURE, seed=42, steps=10)
    run_id = str(result["runId"])
    assert result["persisted"] is True

    async with session_maker() as session:
        events = await PostgresEventQueryRepository(session).list_by_run(run_id)
    assert len(events) > 0

    relay = PostgresOutboxRelay(session_maker, redis_client)
    published = await relay.publish_until_empty()
    assert published == len(events)
    assert await redis_client.xlen(DOMAIN_EVENTS_STREAM) == len(events)

    processed = {"count": 0}

    async def handler(_envelope) -> None:
        processed["count"] += 1

    consumer = IdempotentStreamConsumer(
        session_maker,
        redis_client,
        handler,
        consumer_name="silent-relay-test",
    )
    while await consumer.process_once():
        pass
    assert processed["count"] == len(events)

    await redis_client.delete(DOMAIN_EVENTS_STREAM)
    backfill = PostgresBackfillService(session_maker, redis_client)
    backfill_result = await backfill.backfill(
        BackfillRequestV1(
            schema_version=BACKFILL_REQUEST_SCHEMA_VERSION,
            run_id=run_id,
            force=True,
        )
    )
    assert backfill_result.events_published == len(events)
