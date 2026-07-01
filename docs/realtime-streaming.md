# AEGIS Event Persistence and Streaming

> Phase 11 — transactional outbox relay, Redis Streams delivery, idempotent consumers, and PostgreSQL backfill.

## Authority model

- **PostgreSQL** (`domain_events`, `outbox`) is the durable source of truth for domain-event history.
- **Redis Streams** (`aegis:stream:domain-events`) provides at-least-once live delivery and coordination.
- Redis loss or stream truncation does **not** destroy authoritative history; use PostgreSQL backfill to rebuild delivery state.

## Durable event schema

Domain events are stored in `domain_events.envelope` as validated `DomainEventEnvelopeV1` JSONB (camelCase wire format).

| Constraint | Rule |
|------------|------|
| Identity | Unique `event_id`; unique `(run_id, sequence)` |
| Ordering | `sequence` is monotonic per run |
| Atomicity | State mutations + `domain_events` + `outbox` commit in one PostgreSQL transaction |

## Outbox relay

`PostgresOutboxRelay` (`packages/event-streaming`):

1. **Claim** unpublished outbox rows (`FOR UPDATE SKIP LOCKED`) in a short transaction.
2. **Publish** `RealtimeMessageEnvelopeV1` to Redis via `XADD` (outside any DB transaction).
3. **Acknowledge** by setting `outbox.published_at` and `redis_message_id` in a new transaction.

Outbox columns added in migration `003_event_streaming`: `claimed_at`, `claim_owner`, `publish_attempts`, `last_error`, `next_retry_at`, `redis_message_id`.

Stale claims are reclaimed after `AEGIS_OUTBOX_CLAIM_TTL_SECONDS` (default 60s).

## Redis Streams conventions

| Name | Purpose |
|------|---------|
| `aegis:stream:domain-events` | Primary domain-event stream |
| `aegis:stream:domain-events:dlq` | Dead-letter stream |
| `aegis-domain-events` | Default consumer group |

Wire format: `RealtimeMessageEnvelopeV1` serialized in the `payload` Redis hash field.

Retention: approximate `MAXLEN` via `AEGIS_STREAM_MAXLEN` (default 100000).

## Idempotent consumers

`IdempotentStreamConsumer` records processing in `consumer_receipts` keyed by `(consumer_id, event_id)` — distinct from API `idempotency_records`.

Consumers must:

- Check receipts before applying side effects (or make handlers idempotent).
- `XACK` only after successful processing and receipt persistence.
- Use `XAUTOCLAIM` for stale pending messages.
- Route poison messages to `dead_letters` (PostgreSQL) and the DLQ stream after `AEGIS_CONSUMER_MAX_ATTEMPTS`.

## Backfill / reconciliation

`PostgresBackfillService` reads `domain_events` ordered by `run_id, sequence` and republishes missing entries to Redis.

API: `POST /api/v1/realtime/backfill` with `BackfillRequestV1`.

## Observability

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/realtime/streaming/status` | Outbox age, stream length, pending, DLQ counts |
| `GET /api/v1/realtime/runs/{run_id}/events` | Authoritative PG event history |
| `GET /realtime/observability` | HTML status page (HTTP only; not WebSocket) |

## Operational commands

```bash
# Infrastructure
sudo service postgresql start   # or: docker compose up -d postgres redis
sudo service redis-server start
uv run alembic upgrade head

# Persist simulation events
uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 100

# Start outbox relay worker
uv run aegis-worker --mode outbox-relay

# API + observability
uv run aegis-api

# Validation
uv run pytest tests/integration/streaming -q
```

## Phase 12–13 constraints

- Phase 12 WebSocket gateway: see [websocket-protocol.md](./websocket-protocol.md).
- Phase 12 consumes `RealtimeMessageEnvelopeV1` and uses PostgreSQL for reconnect gaps.
- Phase 13 live frontend reducers must treat PostgreSQL/backfill as authoritative; do not treat Redis as sole source of truth.
- Do not hold database transactions open across Redis or WebSocket I/O.
