# Phase 02 Handoff — Database Foundation

## Status

`READY FOR VALIDATION`

This handoff is factual evidence for an independent validation agent. The implementation agent does not self-approve.

## Implemented

Phase 02 deliverables per `docs/AEGIS-v1.0-Agent-Specs/foundation/02-database-foundation.md`:

- `packages/persistence` (`aegis_persistence`): SQLAlchemy 2 async engine, ORM tables, mappers, repository protocols, PostgreSQL adapters, `PostgresUnitOfWork`, errors, health checks, deterministic seed
- Root Alembic configuration (`alembic.ini`, `migrations/`) with initial schema migration `001_initial_schema`
- Tables for scenarios, versions, runs, assets, relationships, events, outbox, alerts, incidents, evidence, hypotheses, agents, tools, proposals, approvals, actions, models, objects, snapshots, idempotency records
- New durable contracts `IdempotencyRecordV1` and `ObjectMetadataReferenceV1` in Python and TypeScript with golden fixtures
- `AegisSettings.postgres_async_dsn` and sync `postgres_dsn` (`postgresql+psycopg`) for Alembic
- API `/ready` PostgreSQL health probe (fail closed with HTTP 503)
- Integration test harness with real PostgreSQL (`tests/integration/conftest.py`, `tests/integration/db/*`)
- `docs/database.md`, ADR 0003, CI integration job

## Files added

| Area                | Key paths                                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Persistence package | `packages/persistence/`                                                                                            |
| Migrations          | `alembic.ini`, `migrations/env.py`, `migrations/versions/001_initial_schema.py`                                    |
| API DB wiring       | `apps/api/src/aegis_api/db/`                                                                                       |
| Contracts           | `packages/contracts-python/src/aegis_contracts/persistence.py`, `packages/contracts-ts/src/persistence.ts`         |
| Fixtures/schemas    | `tests/contract/fixtures/valid/idempotency_record_v1.json`, `object_metadata_reference_v1.json`, generated schemas |
| Integration tests   | `tests/integration/conftest.py`, `tests/integration/db/*.py`                                                       |
| Unit tests          | `tests/unit/test_persistence_errors.py`, `tests/unit/test_persistence_contracts.py`                                |
| Docs/ADR            | `docs/database.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0003-postgresql-persistence-and-outbox.md`                   |

## Files modified

| File                                                                                       | Reason                                                    |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| `pyproject.toml`                                                                           | Workspace member, import-linter, pytest-asyncio, dev deps |
| `apps/api/pyproject.toml`, `apps/api/src/aegis_api/main.py`                                | Persistence dependency and DB readiness                   |
| `packages/contracts-python/src/aegis_contracts/{settings,versioning,fixtures,__init__}.py` | Async DSN, new contracts                                  |
| `packages/contracts-ts/src/{index,versioning}.ts`                                          | New contracts and exports                                 |
| `package.json`                                                                             | `typecheck:py`, `test:integration`                        |
| `.github/workflows/ci.yml`                                                                 | Integration test job with PostgreSQL service              |
| `tests/unit/test_api_health.py`                                                            | Ready endpoint DB probe behavior                          |
| `tests/contract/fixtures/compatibility-manifest.json`                                      | Updated hashes (50 artifacts)                             |
| `docs/engineering-standards.md`                                                            | Database commands and docs link                           |

## Files removed

None.

## Contracts introduced or changed

| Contract                            | Version         | Description                               |
| ----------------------------------- | --------------- | ----------------------------------------- |
| `WORKSPACE_VERSION`                 | `0.0.0-phase02` | Workspace metadata constant               |
| `IdempotencyRecordV1`               | schema v1       | Durable idempotency record                |
| `ObjectMetadataReferenceV1`         | schema v1       | Object storage metadata reference         |
| `AegisSettings.postgres_async_dsn`  | v1 (implicit)   | Async SQLAlchemy connection URL           |
| `AegisSettings.postgres_dsn`        | v1 (behavior)   | Now uses `postgresql+psycopg` for Alembic |
| Repository protocols / `UnitOfWork` | v1 (Python)     | Owned by `aegis_persistence`              |

## Database migrations

| Revision             | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `001_initial_schema` | Full initial PostgreSQL schema (21 domain tables + Alembic version) |

## Environment and configuration changes

- No new environment variables; existing `POSTGRES_*` from Phase 00 used
- `alembic.ini` at repository root
- CI `integration` job runs `alembic upgrade head` and `pytest tests/integration`

## Generated artifacts and fixtures

- 2 new valid golden fixtures + 2 generated JSON Schemas
- Updated `compatibility-manifest.json` (50 artifact hashes)
- `uv.lock` updated with SQLAlchemy, asyncpg, psycopg, alembic

## Tests added

| Test                                                  | Proves                                                                     |
| ----------------------------------------------------- | -------------------------------------------------------------------------- |
| `tests/integration/db/test_migrations.py`             | Schema reproducible from migrations                                        |
| `tests/integration/db/test_unit_of_work.py`           | Failed txn leaves no partial state/orphan outbox; successful atomic commit |
| `tests/integration/db/test_event_uniqueness.py`       | `(run_id, sequence)` and `event_id` uniqueness                             |
| `tests/integration/db/test_optimistic_concurrency.py` | `STALE_REVISION` on stale updates                                          |
| `tests/integration/db/test_idempotency.py`            | Idempotency record round-trip and duplicate rejection                      |
| `tests/integration/db/test_repositories.py`           | Repositories return Pydantic contracts, not ORM                            |
| `tests/unit/test_persistence_errors.py`               | Error code mapping                                                         |
| `tests/unit/test_persistence_contracts.py`            | New contract fixture parsing                                               |
| `tests/unit/test_api_health.py` (extended)            | `/ready` fail-closed when DB unavailable                                   |

**Totals:** 145 pytest passed; 62 Vitest passed (after Phase 02 contract additions).

## Commands executed and results

Executed on branch `cursor/database-foundation-9069`.

| Command                                     | Result                                                                                                                                                                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `uv run ruff check .`                       | **PASS**                                                                                                                                                                                                           |
| `pnpm typecheck:py`                         | **PASS** (45 source files)                                                                                                                                                                                         |
| `uv run pytest -q`                          | **PASS** (145 passed)                                                                                                                                                                                              |
| `uv run alembic upgrade head`               | **PASS**                                                                                                                                                                                                           |
| `uv run pytest tests/integration -q`        | **PASS** (11 passed)                                                                                                                                                                                               |
| `pnpm check-contracts`                      | **PASS**                                                                                                                                                                                                           |
| `uv run lint-imports`                       | **PASS** (4 contracts kept)                                                                                                                                                                                        |
| `pnpm test`                                 | **PASS** (62 Vitest tests)                                                                                                                                                                                         |
| `docker compose up -d postgres redis minio` | **FAIL** — Docker daemon not available in implementation VM (`docker: command not found`). Local PostgreSQL 16 used for integration tests. CI `integration` job is expected to validate against service container. |

## Architecture decisions and ADRs

- **Created:** [0003-postgresql-persistence-and-outbox.md](../AEGIS-v1.0-Agent-Specs/adrs/0003-postgresql-persistence-and-outbox.md) (Status: **Proposed**)
- **Unchanged:** ADR 0001, ADR 0002

## Known limitations

- Outbox relay to Redis Streams not implemented (Phase 11)
- `tools` table uses minimal JSONB row shape; full tool registry contract deferred
- Docker Compose validation command in phase spec references `object-storage`; canonical Compose service name is `minio` (documented in `docs/database.md`)
- Route handlers do not expose domain persistence APIs yet (later phases)

## Deferred work

- Phase 11: outbox relay, Redis Streams, WebSocket deltas
- Phase 03+: simulation runtime, graph engine, feature logic, auth
- Full tool registry contract cross-language fixtures

## Risks for dependent phases

- All state+event writes must use `PostgresUnitOfWork.append_event()` for outbox atomicity
- Import domain types only from `aegis_contracts`; map via `aegis_persistence` repositories
- Incident/alert IDs are **authored** IDs (`incident:...`, `alert:...`), not runtime `inc_`/`alt_` prefixes
- Changing applied migrations requires new revisions, not edits to `001_initial_schema`

## Acceptance criteria evidence

| Criterion                                                   | Evidence                                                                                |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Failed transaction leaves no partial state or orphan outbox | `test_unit_of_work.py::test_failed_transaction_leaves_no_partial_state_or_outbox`       |
| Entire schema reproducible from migrations                  | `test_migrations.py::test_schema_reproducible_from_migrations` + `alembic upgrade head` |
| Repositories hide ORM details                               | `test_repositories.py` asserts `RunV1` / `ObjectMetadataReferenceV1` return types       |
| Uniqueness/index/concurrency integration-tested             | `test_event_uniqueness.py`, `test_optimistic_concurrency.py`, `test_idempotency.py`     |

## Prohibited-shortcut confirmation

- No Redis publication, WebSockets, scenario execution, auth, or route-to-table writes
- No SQLite substitution for integration tests
- No Silent Relay values in platform seed data
- No tests deleted or weakened
- Validation results recorded honestly; Docker Compose startup not claimed as passed
- Implementation agent does not self-approve
