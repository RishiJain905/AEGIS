"""Integration tests for idempotency record persistence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import IdempotencyRecordV1
from aegis_contracts.versioning import IDEMPOTENCY_RECORD_SCHEMA_VERSION
from aegis_persistence.errors import DuplicateIdempotencyKeyError
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _record(key: str = "idem_integration_001") -> IdempotencyRecordV1:
    return IdempotencyRecordV1(
        schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
        scope="api:test",
        idempotency_key=key,
        request_hash="sha256:abc",
        response_ref="run:run_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        created_at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
        replayed=False,
    )


@pytest.mark.asyncio
async def test_idempotency_record_round_trip(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    record = _record()
    stored = await unit_of_work.idempotency.add(record)
    assert stored.idempotency_key == record.idempotency_key

    fetched = await unit_of_work.idempotency.get(
        scope=record.scope,
        idempotency_key=record.idempotency_key,
    )
    assert fetched is not None
    assert fetched.response_ref == record.response_ref
    assert fetched.schema_version == IDEMPOTENCY_RECORD_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_rejected(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    record = _record("idem_duplicate_key")

    async with PostgresUnitOfWork(session_maker) as uow:
        await uow.idempotency.add(record)

    with pytest.raises(DuplicateIdempotencyKeyError):
        async with PostgresUnitOfWork(session_maker) as uow:
            await uow.idempotency.add(record)
