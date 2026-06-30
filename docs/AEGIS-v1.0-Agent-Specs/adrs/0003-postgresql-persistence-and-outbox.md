# ADR 0003: PostgreSQL Persistence Package and Transactional Outbox

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 02 introduces durable PostgreSQL persistence for AEGIS v1.0. Phase 00 established the monorepo toolchain; Phase 01 established canonical cross-language contracts. No ORM, migrations, repositories, or unit-of-work semantics existed prior to this phase.

`architecture.md` requires:

- PostgreSQL as authoritative durable state
- Append-only domain events with unique `(run_id, sequence)`
- State changes and outbox rows committed atomically in one transaction
- JSONB for versioned flexible payloads; normalized columns for filters and constraints
- Repositories that return domain contracts, not ORM entities

## Decision

1. **New package `packages/persistence` (`aegis_persistence`)** holds SQLAlchemy 2 async access, ORM table definitions, mappers, repository protocols, PostgreSQL adapters, and `PostgresUnitOfWork`. Domain packages and `aegis_contracts` must not import ORM types.

2. **Root-level Alembic** at `alembic.ini` + `migrations/` with explicit table metadata in `aegis_persistence.orm.tables`. Migration scripts do not import live application models.

3. **Runtime access** uses `postgresql+asyncpg://` via `AegisSettings.postgres_async_dsn`. Alembic CLI uses sync `postgresql://` via `AegisSettings.postgres_dsn`.

4. **Transactional outbox (write path only)** — `PostgresUnitOfWork.append_event()` inserts into `domain_events` and `outbox` in the same database transaction as any state mutations. Redis publication and outbox relay are deferred to Phase 11.

5. **JSONB boundaries** — versioned contract payloads are validated on read/write using `aegis_contracts` Pydantic models and `parse_contract()`. Filtered or constrained fields use normalized columns with database indexes and foreign keys.

6. **New durable contracts** `IdempotencyRecordV1` and `ObjectMetadataReferenceV1` live in `aegis_contracts` / `@aegis/contracts-ts` with golden fixtures and generated JSON Schemas.

7. **Optimistic concurrency** — mutable rows carry `revision`; updates use compare-and-swap and raise `STALE_REVISION` on conflict. Event inserts enforce unique `event_id` and `(run_id, sequence)` with `DUPLICATE_EVENT` on conflict.

8. **Integration tests** use real PostgreSQL only; SQLite is not substituted for release-critical persistence tests.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| ORM models in `apps/api` | Violates package boundaries; persistence is shared by services |
| SQLite for integration tests | Behaviorally different; spec forbids substitution |
| Outbox relay in Phase 02 | Explicitly out of scope; Phase 11 owns Redis Streams delivery |
| Contracts only in persistence package | Cross-language durable contracts require contracts packages per ADR 0002 |

## Consequences

- All schema changes require Alembic migrations reviewed as production code.
- State + event + outbox writes must go through `PostgresUnitOfWork`; route handlers must not write domain tables directly.
- `pnpm typecheck:py` and import-linter must include `aegis_persistence`.
- Phase 11 depends on the outbox table shape and `published_at` column defined here.

## Security and reliability

- Failed transactions roll back all state, event, and outbox inserts — no partial commits.
- Database constraints supplement application validation.
- No secrets in migration files or seed data.

## Approval

- [ ] Project owner
