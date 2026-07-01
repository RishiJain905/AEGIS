# Phase 12 Handoff — WebSocket Gateway

## Status

`READY FOR VALIDATION`

## Implemented

Phase 12 deliverables per `docs/AEGIS-v1.0-Agent-Specs/realtime-platform/12-websocket-gateway.md`:

- WebSocket protocol v1 contracts (`WebSocketFrameV1`, typed payloads, `WebSocketErrorCode`) in Python and TypeScript
- FastAPI gateway at `apps/api/src/aegis_api/websocket/` with auth hooks, bounded queues, Redis fan-out, PG recovery
- `@aegis/realtime-client` typed transport with jittered reconnect
- Diagnostic page `GET /realtime/websocket-demo`
- Documentation `docs/websocket-protocol.md`, ADR 0013
- Integration, unit, and contract tests mapping to all acceptance criteria

## Files added

| Area        | Key paths                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| Contracts   | `packages/contracts-python/src/aegis_contracts/websocket.py`, `packages/contracts-ts/src/websocket.ts`                    |
| Gateway     | `apps/api/src/aegis_api/websocket/**`                                                                                     |
| TS client   | `packages/realtime-client/**`                                                                                             |
| Tests       | `tests/unit/websocket/**`, `tests/integration/websocket/**`, `tests/contract/websocket/**`                                |
| Fixtures    | `tests/contract/fixtures/valid/websocket_frame_v1.json`, `tests/contract/fixtures/schemas/websocket_frame_v1.schema.json` |
| Docs/ADR    | `docs/websocket-protocol.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0013-websocket-gateway.md`                                |
| Demo script | `apps/web/scripts/capture-websocket-gateway-demo.mjs`                                                                     |

## Files modified

| File                                                          | Reason                                                                  |
| ------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `packages/contracts-python/src/aegis_contracts/versioning.py` | `WEBSOCKET_FRAME_SCHEMA_VERSION`, `WORKSPACE_VERSION` → `0.0.0-phase12` |
| `packages/contracts-ts/src/versioning.ts`                     | Mirror                                                                  |
| `packages/contracts-python/src/aegis_contracts/settings.py`   | WebSocket env vars                                                      |
| `apps/api/src/aegis_api/main.py`                              | Gateway lifespan + routes                                               |
| `apps/api/src/aegis_api/realtime/status.py`                   | Gateway metrics in streaming status                                     |
| `apps/api/src/aegis_api/realtime/observability.py`            | Link to WS demo                                                         |
| `tests/integration/conftest.py`                               | Shared `redis_client` fixture                                           |
| `.env.example`                                                | WebSocket configuration                                                 |
| `docs/realtime-streaming.md`                                  | Cross-link to protocol doc                                              |
| `tests/contract/fixtures/compatibility-manifest.json`         | New fixture hashes                                                      |

## Files removed

None.

## Contracts introduced or changed

| Contract                 | Version         | Description                                             |
| ------------------------ | --------------- | ------------------------------------------------------- |
| `WebSocketFrameV1`       | schema v1       | Versioned WS wire frame                                 |
| WebSocket payload models | v1              | hello, subscribe, event, error, snapshot_required, etc. |
| `WebSocketErrorCode`     | v1              | Stable gateway error codes                              |
| `WORKSPACE_VERSION`      | `0.0.0-phase12` | Workspace parity bump                                   |

## Database migrations

None (reuses Phase 11 `domain_events` + Redis streams).

## Environment and configuration changes

See `.env.example`: `AEGIS_WS_PATH`, `AEGIS_WS_ENABLED`, `AEGIS_WS_MAX_CONNECTIONS`, `AEGIS_WS_MAX_QUEUE_DEPTH`, `AEGIS_WS_MAX_MESSAGE_BYTES`, `AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS`, `AEGIS_WS_IDLE_TIMEOUT_SECONDS`, `AEGIS_WS_DEV_AUTH_ENABLED`, `AEGIS_WS_DEV_AUTH_TOKEN`, `AEGIS_WS_GATEWAY_CONSUMER_GROUP`, `AEGIS_WS_SNAPSHOT_GAP_THRESHOLD`.

## Generated artifacts and fixtures

- Screenshots: `/opt/cursor/artifacts/screenshots/12-*.png`
- Evidence HTML: `/opt/cursor/artifacts/screenshots/12-websocket-validation-evidence.html`

## Tests added

| Test                                                         | Proves                                    |
| ------------------------------------------------------------ | ----------------------------------------- |
| `test_gateway_domain.py`                                     | Auth hooks, dedup, frame validation       |
| `test_websocket_frames.py`                                   | Cross-language protocol fixtures          |
| `test_connect_and_subscribe_delivers_events`                 | Authorized delivery in order              |
| `test_unauthorized_subscription_rejected`                    | Server-side auth rejection                |
| `test_unknown_run_rejected`                                  | Invalid subscription rejected             |
| `test_reconnect_with_cursor`                                 | Cursor-based catch-up without silent gaps |
| `test_duplicate_events_suppressed`                           | Idempotent duplicate handling             |
| `test_pg_backfill_on_subscribe`                              | PostgreSQL authoritative recovery         |
| `test_slow_client_queue_overflow_triggers_snapshot_required` | Bounded queues / backpressure             |
| `test_invalid_message_rejected`                              | Safe rejection of invalid frames          |
| `realtime-client` vitest                                     | Reconnect backoff + frame validation      |

## Commands executed and results

| Command                                                                                                    | Result                                                                  |
| ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `pnpm format:check`                                                                                        | **PASS**                                                                |
| `pnpm lint`                                                                                                | **PASS**                                                                |
| `pnpm typecheck`                                                                                           | **PASS**                                                                |
| `pnpm test`                                                                                                | **PASS**                                                                |
| `pnpm build`                                                                                               | **PASS**                                                                |
| `pnpm check-contracts`                                                                                     | **PASS**                                                                |
| `uv run ruff check .`                                                                                      | **PASS** (after `--fix`)                                                |
| `uv run pytest -q`                                                                                         | **PASS** — 280 passed                                                   |
| `uv run lint-imports`                                                                                      | **PASS**                                                                |
| `uv run pytest tests/integration -q`                                                                       | **PASS** — 29 passed                                                    |
| `uv run pytest tests/integration/websocket -q`                                                             | **PASS** — 8 passed                                                     |
| `uv run pytest tests/contract/websocket -q`                                                                | **PASS** — 4 passed                                                     |
| `uv run mypy apps services packages`                                                                       | **BLOCKED** — pre-existing `aegis_api.db.session` duplicate module path |
| `docker compose up -d postgres redis minio`                                                                | **BLOCKED** — Docker unavailable; local PostgreSQL/Redis used           |
| `uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 100` | **PASS**                                                                |
| `uv run python scripts/publish-outbox-once.py`                                                             | **PASS** — `published: 101`                                             |
| `pnpm --filter @aegis/web exec node scripts/capture-websocket-gateway-demo.mjs`                            | **PASS** — 7 screenshots                                                |

### Demo startup sequence

```bash
sudo service postgresql start && sudo service redis-server start
uv run alembic upgrade head
uv run aegis-simulator run-persisted --scenario scenarios/operation-silent-relay --seed 1000 --steps 100
uv run python scripts/publish-outbox-once.py
uv run aegis-worker --mode outbox-relay   # background
uv run aegis-api                          # background
pnpm --filter @aegis/web exec node scripts/capture-websocket-gateway-demo.mjs
```

## Architecture decisions and ADRs

- **Created:** [0013-websocket-gateway.md](../AEGIS-v1.0-Agent-Specs/adrs/0013-websocket-gateway.md) (Status: **Proposed**)
- **Unchanged:** ADR 0003, 0012 event delivery semantics; no competing event store

## Known limitations

- Production OIDC deferred to Phase 30; dev token auth only in Phase 12
- Command-centre live reducers deferred to Phase 13 (fixture UI unchanged)
- `mypy` fails on pre-existing API session module path issue
- Docker Compose validation not executed in VM (local PostgreSQL/Redis used)

## Deferred work

- Phase 13: Wire `@aegis/realtime-client` into command-centre shell reducers
- Phase 30: Replace dev auth hooks with OIDC

## Risks for dependent phases

- Phase 13 must consume `WebSocketFrameV1` / `@aegis/realtime-client`; do not duplicate protocol
- Phase 13 must treat PostgreSQL as authoritative for reducers; gateway cursor is transport-only
- Changing protocol or stream semantics requires ADR + version bump

## Acceptance criteria evidence

1. **Reconnect repairs state without silent gaps or reordering:** `test_reconnect_with_cursor`, `test_pg_backfill_on_subscribe`; demo reconnect screenshot
2. **Unauthorized subscriptions rejected server-side:** `test_unauthorized_subscription_rejected`, `test_unknown_run_rejected`; demo bad-auth screenshot
3. **Slow clients cannot cause unbounded memory growth:** `test_slow_client_queue_overflow_triggers_snapshot_required`; `AEGIS_WS_MAX_QUEUE_DEPTH` bounded queue
4. **Protocol versioned and cross-language tested:** `websocket_frame_v1` fixtures; `test_websocket_frames.py`; `pnpm check-contracts`

## Prohibited-shortcut confirmation

No scaffolding-only gateway, no Redis-as-authority, no Phase 13 reducers absorbed, no competing event store, no skipped/weakened tests, validation commands executed with honest results.
