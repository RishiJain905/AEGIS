# AEGIS Database Foundation

> Phase 02 — PostgreSQL persistence, migrations, repositories, and transactional outbox.

## Overview

PostgreSQL is the authoritative durable store for AEGIS v1.0. The `aegis_persistence` package provides:

- SQLAlchemy 2 async access (`asyncpg`)
- Alembic migrations at the repository root
- Repository protocols returning `aegis_contracts` domain types
- `PostgresUnitOfWork` for atomic state + domain event + outbox commits

Redis publication of outbox rows is implemented in Phase 11 — see [realtime-streaming.md](realtime-streaming.md).

## Schema tables

| Table | Purpose |
| ----- | ------- |
| `scenarios`, `scenario_versions` | Published scenario identity and versions |
| `runs` | Scenario execution instances with optimistic `revision` |
| `asset_instances`, `relationship_instances` | Run-scoped topology |
| `domain_events` | Append-only event envelopes; unique `(run_id, sequence)` |
| `outbox` | Transactional outbox with relay claim/retry columns (`003_event_streaming`) |
| `consumer_receipts` | Idempotent consumer deduplication by `(consumer_id, event_id)` |
| `consumer_cursors` | Per-consumer stream cursor state |
| `dead_letters` | Durable poison-message records |
| `alerts`, `incidents`, `evidence`, `hypotheses` | Investigation domain state |
| `agent_sessions` | Agent runtime audit records |
| `tools` | Allowlisted tool registry metadata |
| `action_proposals`, `approvals`, `executed_actions` | Proposal/approval/execution audit |
| `model_manifests`, `model_scores` | ML artifact metadata and scores |
| `stored_objects` | Object storage metadata references |
| `graph_snapshots` | Replay acceleration snapshots |
| `idempotency_records` | Durable idempotency keys scoped per operation |

## JSONB vs normalized columns

- **Normalized columns** store foreign keys, filter fields, uniqueness keys, revisions, and timestamps.
- **JSONB `payload` / `envelope`** stores validated contract documents (camelCase wire format).
- Repositories parse JSONB through `aegis_contracts.parse_contract()` on read and validate before write.

## Transaction ownership

All durable state changes that emit events must use `PostgresUnitOfWork`:

1. Mutate state through repository methods on the active UoW.
2. Call `append_event(envelope)` to insert `domain_events` and `outbox` in the same transaction.
3. Commit via `async with uow:` or explicit `commit()`.

Route handlers must not write domain tables directly.

On failure, the session rolls back — no partial state or orphan outbox rows.

## Optimistic concurrency and idempotency

- Mutable rows (`runs`, `incidents`, `action_proposals`, assets) use `revision` compare-and-swap updates.
- Stale updates raise `StaleRevisionError` (`STALE_REVISION`).
- Event inserts enforce unique `event_id` and `(run_id, sequence)` (`DUPLICATE_EVENT`).
- Idempotency records are unique on `(scope, idempotency_key)`.

## Environment variables

See [`.env.example`](../.env.example):

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Connection URLs:

- Async runtime: `postgresql+asyncpg://` via `AegisSettings.postgres_async_dsn`
- Alembic CLI: `postgresql+psycopg://` via `AegisSettings.postgres_dsn`

## Operational commands

```bash
# Start local infrastructure (Compose service for object storage is named minio)
docker compose up -d postgres redis minio

# Apply migrations
uv run alembic upgrade head

# Roll back one revision (initial schema downgrade drops all tables)
uv run alembic downgrade -1

# Deterministic local seed (synthetic IDs only)
uv run aegis-seed

# Integration tests (require PostgreSQL; streaming tests also require Redis)
uv run pytest tests/integration -q
uv run pytest tests/integration/streaming -q
```

See [realtime-streaming.md](realtime-streaming.md) for outbox relay, Redis Streams, and backfill operations.

## Migration policy

- Every schema change requires a new Alembic revision.
- Do not edit migrations that have been applied in shared environments.
- Prefer expand/contract for breaking changes.
- Test upgrades from the previous schema and from an empty database.

## Backup and restore (local development)

```bash
pg_dump -h localhost -U aegis -d aegis -Fc -f aegis-dev.dump
pg_restore -h localhost -U aegis -d aegis --clean aegis-dev.dump
```

## Package boundaries

- `aegis_persistence` depends on `aegis_contracts` only.
- `aegis_contracts` must not import `aegis_persistence`.
- ORM types must not leak past repository adapters.
