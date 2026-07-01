# Phase 11 Handoff — Event Persistence and Streaming

## Status

`READY FOR VALIDATION`

## Implemented

Phase 11 deliverables per `docs/AEGIS-v1.0-Agent-Specs/realtime-platform/11-event-persistence-and-streaming.md`:

- Canonical streaming contracts (`RealtimeMessageEnvelopeV1`, `ConsumerCursorV1`, `DeadLetterRecordV1`, `BackfillRequestV1`, `BackfillResultV1`) in Python and TypeScript with golden fixtures
- Migration `003_event_streaming`: outbox relay columns, `consumer_receipts`, `consumer_cursors`, `dead_letters`
- `packages/event-streaming` (`aegis_event_streaming`): Redis adapter, outbox relay, idempotent consumer, backfill, metrics
- `PostgresOutboxRelay` with claim → publish → acknowledge (no DB transaction across Redis I/O)
- `IdempotentStreamConsumer` with receipts, `XAUTOCLAIM`, poison → DLQ path
- `PostgresBackfillService` for PostgreSQL → Redis republication
- Outbox relay worker: `uv run aegis-worker --mode outbox-relay`
- API routes: backfill, streaming status, run events, HTML observability page
- `aegis-simulator run-persisted` for durable simulation runs
- Integration test matrix with real PostgreSQL + Redis
- Documentation: `docs/realtime-streaming.md`, ADR 0012

## Files added

| Area              | Key paths                                                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Contracts         | `packages/contracts-python/src/aegis_contracts/realtime.py`, `packages/contracts-ts/src/realtime.ts`                              |
| Migration         | `migrations/versions/003_event_streaming.py`                                                                                      |
| Event streaming   | `packages/event-streaming/**`                                                                                                     |
| Persistence repos | `packages/persistence/src/aegis_persistence/repositories/streaming.py`                                                            |
| Worker            | `services/workers/src/aegis_workers/outbox/**`                                                                                    |
| API               | `apps/api/src/aegis_api/realtime/**`                                                                                              |
| Tests             | `tests/integration/streaming/**`, `tests/unit/streaming/**`                                                                       |
| Scripts           | `scripts/publish-outbox-once.py`, `scripts/capture-event-streaming-demo.mjs`, `apps/web/scripts/capture-event-streaming-demo.mjs` |
| Docs/ADR          | `docs/realtime-streaming.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0012-event-persistence-and-streaming.md`                          |

## Files modified

| File                                                       | Reason                                             |
| ---------------------------------------------------------- | -------------------------------------------------- |
| `pyproject.toml`                                           | Workspace member, import-linter, pytest pythonpath |
| `packages/contracts-python/**`, `packages/contracts-ts/**` | Streaming contracts, WORKSPACE_VERSION             |
| `packages/persistence/src/aegis_persistence/orm/tables.py` | Outbox + streaming tables                          |
| `services/workers/**`                                      | Outbox relay mode                                  |
| `services/simulation/src/aegis_simulation/runner.py`       | `run-persisted` CLI                                |
| `apps/api/**`                                              | Realtime routes                                    |
| `tests/integration/conftest.py`                            | Truncate streaming tables                          |
| `.github/workflows/ci.yml`                                 | Redis service for integration job                  |
| `docs/database.md`, `docs/engineering-standards.md`        | Phase 11 references                                |
| `tests/contract/fixtures/compatibility-manifest.json`      | New artifact hashes                                |

## Files removed

None.

## Contracts introduced or changed

| Contract                                 | Version         | Description                   |
| ---------------------------------------- | --------------- | ----------------------------- |
| `RealtimeMessageEnvelopeV1`              | schema v1       | Redis/WebSocket wire envelope |
| `ConsumerCursorV1`                       | schema v1       | Consumer offset state         |
| `DeadLetterRecordV1`                     | schema v1       | Poison message diagnostics    |
| `BackfillRequestV1` / `BackfillResultV1` | schema v1       | PG → Redis republication      |
| `StreamingErrorCode`                     | v1              | Stable streaming error codes  |
| `WORKSPACE_VERSION`                      | `0.0.0-phase11` | Workspace parity bump         |

## Database migrations

| Revision              | Description                                                             |
| --------------------- | ----------------------------------------------------------------------- |
| `003_event_streaming` | Outbox relay columns; consumer_receipts, consumer_cursors, dead_letters |

## Environment and configuration changes

Optional streaming env vars (defaults in `StreamingConfig.from_env()`):

- `AEGIS_STREAM_MAXLEN` (default 100000)
- `AEGIS_OUTBOX_CLAIM_TTL_SECONDS` (default 60)
- `AEGIS_OUTBOX_BATCH_SIZE` (default 50)
- `AEGIS_OUTBOX_POLL_INTERVAL_SECONDS` (default 1.0)
- `AEGIS_OUTBOX_RETRY_DELAY_SECONDS` (default 5)
- `AEGIS_CONSUMER_MAX_ATTEMPTS` (default 3)
- `AEGIS_CONSUMER_BLOCK_MS` (default 1000)
- `AEGIS_CONSUMER_PENDING_IDLE_MS` (default 1000)
- `AEGIS_WORKER_MODE=outbox-relay` for worker process

## Generated artifacts and fixtures

- Golden fixtures: `tests/contract/fixtures/valid/*realtime*`, `consumer_cursor_v1.json`, `dead_letter_record_v1.json`, `backfill_*`
- Generated schemas for new contracts
- Screenshots: `/opt/cursor/artifacts/screenshots/11-*.png`

## Tests added

| Test                             | Proves                                        |
| -------------------------------- | --------------------------------------------- |
| `test_outbox_relay.py`           | Events reach Redis; ordering preserved        |
| `test_idempotent_consumer.py`    | Duplicate delivery does not double effects    |
| `test_relay_crash_recovery.py`   | Stale claims republished; events not lost     |
| `test_stale_pending_recovery.py` | `XAUTOCLAIM` reclaims pending messages        |
| `test_dead_letter.py`            | Poison messages → `dead_letters` + DLQ stream |
| `test_redis_rebuild.py`          | Redis rebuilt from PostgreSQL via backfill    |
| `test_silent_relay_streaming.py` | End-to-end persisted simulation streaming     |
| `test_envelope.py`               | Envelope mapping round-trip                   |

## Commands executed and results

| Command                                                                                                   | Result                                                                  |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `uv run ruff check .`                                                                                     | **PASS**                                                                |
| `uv run mypy apps services packages`                                                                      | **BLOCKED** — pre-existing `aegis_api.db.session` duplicate module path |
| `uv run pytest -q`                                                                                        | **PASS** — 257 passed                                                   |
| `sudo service postgresql start && sudo service redis-server start`                                        | **PASS** (Docker unavailable in VM; local services used)                |
| `uv run alembic upgrade head`                                                                             | **PASS**                                                                |
| `uv run pytest tests/integration -q`                                                                      | **PASS** — 21 passed                                                    |
| `uv run pytest tests/integration/streaming -q`                                                            | **PASS** — 7 passed                                                     |
| `pnpm check-contracts`                                                                                    | **PASS**                                                                |
| `uv run lint-imports`                                                                                     | **PASS**                                                                |
| `uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 50` | **PASS** — 51 events, `persisted: true`                                 |
| `uv run python scripts/publish-outbox-once.py`                                                            | **PASS** — `published: 51`                                              |
| `pnpm --filter @aegis/web exec node scripts/capture-event-streaming-demo.mjs`                             | **PASS** — 5 screenshots                                                |

## Architecture decisions and ADRs

- **Created:** [0012-event-persistence-and-streaming.md](../AEGIS-v1.0-Agent-Specs/adrs/0012-event-persistence-and-streaming.md) (Status: **Proposed**)
- **Unchanged:** ADR 0003 write-path outbox semantics preserved; ADR 0001, 0002, 0004–0011

## Known limitations

- WebSocket gateway deferred to Phase 12
- Live frontend reducers deferred to Phase 13 (command-centre uses static fixtures for timeline)
- `mypy` fails on pre-existing API session module path issue
- Docker Compose validation not executed in VM (local PostgreSQL/Redis used; CI adds Redis service)

## Deferred work

- Phase 12: WebSocket gateway with `last_applied_sequence` reconnect
- Phase 13: Live command-centre event reducers
- Phase 31: Full OpenTelemetry metrics export (in-memory registry only in Phase 11)

## Risks for dependent phases

- Phase 12 must consume `RealtimeMessageEnvelopeV1` and call backfill on gaps
- Phase 13 must not treat Redis as authoritative; use PG event history API
- Consumer handlers must remain idempotent under at-least-once delivery
- Changing stream names requires ADR and contract version bump

## Acceptance criteria evidence

1. **Committed events cannot be permanently lost by relay failure:** `test_relay_crash_recovery.py`; outbox rows remain until `published_at`; stale claim republish
2. **Duplicate delivery does not duplicate effects:** `test_idempotent_consumer.py`; `consumer_receipts` dedup
3. **Redis can be rebuilt from PostgreSQL:** `test_redis_rebuild.py`; `PostgresBackfillService`; demo `published: 51` after flush
4. **Lag, retries, and DLQ observable:** `GET /api/v1/realtime/streaming/status`; observability page; `test_dead_letter.py`; metrics snapshot

## Prohibited-shortcut confirmation

No scaffolding-only relay, no Redis-as-authority, no WebSocket scope absorbed, no skipped/weakened tests, no unexecuted validation claims for commands that passed in this tree.
