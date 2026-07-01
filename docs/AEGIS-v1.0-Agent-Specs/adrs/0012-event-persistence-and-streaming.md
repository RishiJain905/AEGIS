# ADR 0012: Event Persistence and Streaming

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 11 implements the read/delivery path deferred from ADR 0003. Phases 09–10 persist simulation events via `PostgresUnitOfWork.append_event()`. Redis was configured in Phase 00 but unused for event delivery until this phase.

`architecture.md` requires:

- PostgreSQL as authoritative durable event history
- Redis Streams for short-term delivery (not sole source of truth)
- At-least-once delivery with idempotent consumers
- Recovery from PostgreSQL when Redis state is lost

## Decision

1. **New package `packages/event-streaming` (`aegis_event_streaming`)** owns outbox relay, Redis adapter, idempotent consumer framework, backfill, and streaming metrics. It depends on `aegis_contracts` and `aegis_persistence` only.

2. **Canonical contracts** in `aegis_contracts` / `@aegis/contracts-ts`:
   - `RealtimeMessageEnvelopeV1`
   - `ConsumerCursorV1`
   - `DeadLetterRecordV1`
   - `BackfillRequestV1` / `BackfillResultV1`

3. **Stream naming:**
   - Primary: `aegis:stream:domain-events`
   - DLQ: `aegis:stream:domain-events:dlq`
   - Consumer group: `aegis-domain-events`

4. **Transaction boundaries:** Claim and acknowledge outbox rows in short PostgreSQL transactions. Redis `XADD` occurs between transactions — never inside an open DB transaction.

5. **Consumer idempotency:** `consumer_receipts` table with `UNIQUE(consumer_id, event_id)` — separate from API command idempotency records.

6. **Migration `003_event_streaming`:** Extends `outbox` with claim/retry columns; adds `consumer_receipts`, `consumer_cursors`, `dead_letters`.

7. **Worker:** `aegis-worker --mode outbox-relay` polls and publishes unpublished outbox rows.

8. **Backfill:** `PostgresBackfillService` republishes from `domain_events` when Redis history is missing.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Redis as authoritative store | Violates architecture; PG is durable truth |
| Kafka | Out of Phase 11 scope; Redis Streams already in baseline |
| Extend `idempotency_records` for consumers | Different semantics and scope boundaries |
| Single transaction across PG + Redis | Violates reliability boundary; risks long locks |

## Consequences

- Phase 12 WebSocket gateway consumes streams/backfill APIs defined here.
- Duplicate Redis delivery is expected; all consumers must be idempotent.
- Outbox relay crash may duplicate stream entries; receipts prevent duplicate effects.
- Stream retention trimming does not delete PostgreSQL history.

## Approval

- [ ] Project owner
