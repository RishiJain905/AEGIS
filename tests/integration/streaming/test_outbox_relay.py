"""Integration tests for outbox relay to Redis Streams."""

from __future__ import annotations

import pytest
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run


@pytest.mark.asyncio
async def test_outbox_relay_publishes_events_in_order(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAA")
    events = [
        make_test_event(
            event_id=sample_event_id(index),
            run_id=run.id,
            sequence=index + 1,
        )
        for index in range(3)
    ]
    for event in events:
        await unit_of_work.append_event(event)
    await unit_of_work.commit()

    relay = PostgresOutboxRelay(session_maker, redis_client)
    published = await relay.publish_until_empty()
    assert published == 3

    stream_len = await redis_client.xlen(DOMAIN_EVENTS_STREAM)
    assert stream_len == 3

    entries = await redis_client.xrange(DOMAIN_EVENTS_STREAM, "-", "+")
    sequences = [int(fields["sequence"]) for _id, fields in entries]
    assert sequences == [1, 2, 3]

    async with session_maker() as session:
        from aegis_persistence.orm.tables import OutboxRow
        from sqlalchemy import select

        result = await session.execute(select(OutboxRow).where(OutboxRow.published_at.is_not(None)))
        rows = result.scalars().all()
        assert len(rows) == 3
