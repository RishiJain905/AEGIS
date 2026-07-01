"""Integration tests for PostgreSQL backfill after Redis loss."""

from __future__ import annotations

import pytest
from aegis_contracts import BackfillRequestV1
from aegis_contracts.versioning import BACKFILL_REQUEST_SCHEMA_VERSION
from aegis_event_streaming.backfill import PostgresBackfillService
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.streaming.helpers import make_test_event, seed_run, sample_event_id


@pytest.mark.asyncio
async def test_redis_rebuilt_from_postgresql_history(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
) -> None:
    run = await seed_run(unit_of_work, run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAF", seed=17)
    for index in range(5):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(index),
                run_id=run.id,
                sequence=index + 1,
            )
        )
    await unit_of_work.commit()

    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()
    assert await redis_client.xlen(DOMAIN_EVENTS_STREAM) == 5

    await redis_client.delete(DOMAIN_EVENTS_STREAM)
    assert await redis_client.xlen(DOMAIN_EVENTS_STREAM) == 0

    backfill = PostgresBackfillService(session_maker, redis_client)
    result = await backfill.backfill(
        BackfillRequestV1(
            schema_version=BACKFILL_REQUEST_SCHEMA_VERSION,
            run_id=run.id,
            force=True,
        )
    )
    assert result.events_published == 5
    assert await redis_client.xlen(DOMAIN_EVENTS_STREAM) == 5
