"""Streaming-related persistence repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aegis_contracts import (
    ConsumerCursorV1,
    DeadLetterRecordV1,
    DomainEventEnvelopeV1,
)
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import domain_to_payload, event_to_domain
from aegis_persistence.orm.tables import (
    ConsumerCursorRow,
    ConsumerReceiptRow,
    DeadLetterRow,
    DomainEventRow,
    OutboxRow,
)


@dataclass(frozen=True)
class OutboxClaim:
    outbox_id: int
    event_id: str
    channel: str
    envelope: DomainEventEnvelopeV1


class PostgresOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_batch(
        self,
        *,
        claim_owner: str,
        batch_size: int,
        claim_ttl_seconds: int,
    ) -> list[OutboxClaim]:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=claim_ttl_seconds)
        result = await self._session.execute(
            select(OutboxRow, DomainEventRow)
            .join(DomainEventRow, OutboxRow.event_id == DomainEventRow.event_id)
            .where(
                OutboxRow.published_at.is_(None),
                or_(
                    OutboxRow.claimed_at.is_(None),
                    OutboxRow.claimed_at < stale_before,
                ),
                or_(
                    OutboxRow.next_retry_at.is_(None),
                    OutboxRow.next_retry_at <= now,
                ),
            )
            .order_by(OutboxRow.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        claims: list[OutboxClaim] = []
        for outbox_row, event_row in result.all():
            outbox_row.claimed_at = now
            outbox_row.claim_owner = claim_owner
            outbox_row.publish_attempts += 1
            claims.append(
                OutboxClaim(
                    outbox_id=outbox_row.id,
                    event_id=outbox_row.event_id,
                    channel=outbox_row.channel,
                    envelope=event_to_domain(event_row),
                )
            )
        if claims:
            await self._session.flush()
        return claims

    async def mark_published(
        self,
        *,
        outbox_id: int,
        redis_message_id: str,
        published_at: datetime,
    ) -> None:
        await self._session.execute(
            update(OutboxRow)
            .where(OutboxRow.id == outbox_id)
            .values(
                published_at=published_at,
                redis_message_id=redis_message_id,
                claimed_at=None,
                claim_owner=None,
                last_error=None,
                next_retry_at=None,
            )
        )

    async def record_publish_failure(
        self,
        *,
        outbox_id: int,
        error_message: str,
        retry_delay_seconds: int,
    ) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(OutboxRow)
            .where(OutboxRow.id == outbox_id)
            .values(
                claimed_at=None,
                claim_owner=None,
                last_error=error_message[:2048],
                next_retry_at=now + timedelta(seconds=retry_delay_seconds),
            )
        )

    async def count_unpublished(self) -> int:
        result = await self._session.execute(
            select(OutboxRow.id).where(OutboxRow.published_at.is_(None))
        )
        return len(result.all())

    async def oldest_unpublished_age_seconds(self) -> float | None:
        result = await self._session.execute(
            select(OutboxRow.created_at)
            .where(OutboxRow.published_at.is_(None))
            .order_by(OutboxRow.created_at)
            .limit(1)
        )
        created_at = result.scalar_one_or_none()
        if created_at is None:
            return None
        return (datetime.now(UTC) - created_at).total_seconds()


class PostgresConsumerReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_receipt(self, *, consumer_id: str, event_id: str) -> bool:
        result = await self._session.execute(
            select(ConsumerReceiptRow.id).where(
                ConsumerReceiptRow.consumer_id == consumer_id,
                ConsumerReceiptRow.event_id == event_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def try_record(
        self,
        *,
        consumer_id: str,
        event_id: str,
        stream_message_id: str | None,
        processed_at: datetime,
    ) -> bool:
        if await self.has_receipt(consumer_id=consumer_id, event_id=event_id):
            return False
        row = ConsumerReceiptRow(
            consumer_id=consumer_id,
            event_id=event_id,
            stream_message_id=stream_message_id,
            processed_at=processed_at,
            payload={
                "consumerId": consumer_id,
                "eventId": event_id,
                "streamMessageId": stream_message_id,
                "processedAt": processed_at.isoformat().replace("+00:00", "Z"),
            },
        )
        self._session.add(row)
        await self._session.flush()
        return True


class PostgresConsumerCursorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, cursor: ConsumerCursorV1) -> ConsumerCursorV1:
        payload = domain_to_payload(cursor)
        result = await self._session.execute(
            select(ConsumerCursorRow).where(
                ConsumerCursorRow.consumer_group == cursor.consumer_group,
                ConsumerCursorRow.consumer_name == cursor.consumer_name,
                ConsumerCursorRow.stream_key == cursor.stream_key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ConsumerCursorRow(
                consumer_group=cursor.consumer_group,
                consumer_name=cursor.consumer_name,
                stream_key=cursor.stream_key,
                last_event_id=cursor.last_event_id,
                last_run_id=cursor.last_run_id,
                last_sequence=cursor.last_sequence,
                updated_at=cursor.updated_at,
                payload=payload,
            )
            self._session.add(row)
        else:
            row.last_event_id = cursor.last_event_id
            row.last_run_id = cursor.last_run_id
            row.last_sequence = cursor.last_sequence
            row.updated_at = cursor.updated_at
            row.payload = payload
        await self._session.flush()
        return cursor

    async def get(
        self,
        *,
        consumer_group: str,
        consumer_name: str,
        stream_key: str,
    ) -> ConsumerCursorV1 | None:
        result = await self._session.execute(
            select(ConsumerCursorRow).where(
                ConsumerCursorRow.consumer_group == consumer_group,
                ConsumerCursorRow.consumer_name == consumer_name,
                ConsumerCursorRow.stream_key == stream_key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        from aegis_contracts import parse_contract

        return parse_contract(ConsumerCursorV1, row.payload)


class PostgresDeadLetterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: DeadLetterRecordV1) -> DeadLetterRecordV1:
        payload = domain_to_payload(record)
        row = DeadLetterRow(
            event_id=record.event_id,
            run_id=record.run_id,
            sequence=record.sequence,
            consumer_id=record.consumer_id,
            stream_key=record.stream_key,
            stream_message_id=record.stream_message_id,
            error_code=record.error_code,
            created_at=record.created_at,
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    async def count_all(self) -> int:
        result = await self._session.execute(select(DeadLetterRow.id))
        return len(result.all())


class PostgresEventQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_run(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int = 1000,
    ) -> list[DomainEventEnvelopeV1]:
        query = select(DomainEventRow).where(DomainEventRow.run_id == run_id)
        if from_sequence is not None:
            query = query.where(DomainEventRow.sequence >= from_sequence)
        if to_sequence is not None:
            query = query.where(DomainEventRow.sequence <= to_sequence)
        query = query.order_by(DomainEventRow.sequence).limit(limit)
        result = await self._session.execute(query)
        return [event_to_domain(row) for row in result.scalars().all()]

    async def list_for_backfill(
        self,
        *,
        run_id: str | None = None,
        from_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int = 10_000,
    ) -> list[DomainEventEnvelopeV1]:
        query = select(DomainEventRow)
        if run_id is not None:
            query = query.where(DomainEventRow.run_id == run_id)
        if from_sequence is not None:
            query = query.where(DomainEventRow.sequence >= from_sequence)
        if to_sequence is not None:
            query = query.where(DomainEventRow.sequence <= to_sequence)
        query = query.order_by(DomainEventRow.run_id, DomainEventRow.sequence).limit(limit)
        result = await self._session.execute(query)
        return [event_to_domain(row) for row in result.scalars().all()]
