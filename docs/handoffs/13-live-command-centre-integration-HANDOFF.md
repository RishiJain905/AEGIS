# Phase 13 Handoff — Live Command-Centre Integration

## Status

`READY FOR VALIDATION`

Live stack demo capture (`capture-live-run-demo.mjs`) requires PostgreSQL + Redis + worker + API; those services were unavailable in the validation VM (no Docker, `pg_isready`, or `redis-cli`). Fixture-mode and unit/integration test evidence is complete; full live-stack screenshots are deferred to environments with database services.

## Implemented behavior (Sections 7 and 18)

| Spec requirement                                               | Implementation                                                                        |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Thin run start/pause/resume/stop/step APIs with idempotency    | `apps/api/src/aegis_api/runs/router.py`, `RunCommandService`                          |
| Bootstrap from authoritative snapshot + sequence-aware reducer | `GraphProjectionService`, `PostgresGraphSnapshotRepository`, `apps/web/lib/realtime/` |
| Graph, timeline, run status integration                        | `LiveRunProvider`, `TimelineView`, `VisualizationSlot`, shared `RunReplicatedState`   |
| Connection health states                                       | `ConnectionHealthState`, `ConnectionHealthBanner`, `StatusStrip`                      |
| Gap halt until recovery                                        | `runReplicatedReducer` + catch-up/resync modules                                      |
| Cursor persistence for reopen                                  | `cursor-storage.ts` (`sessionStorage`)                                                |
| Silent Relay live topology/activity                            | Run create + step APIs; graph delta projection from `sim.asset.status_changed`        |

### Acceptance criteria evidence

1. **Graph, timeline, and run status share the same `lastAppliedSequence`:** Single `RunReplicatedState` reducer in `run-reducer.ts`; unit test `shares sequence across run status and timeline updates`; E2E fixture shell renders graph + timeline together.
2. **Reconnect without full-page refresh:** `LiveRunProvider` uses `@aegis/realtime-client` with cursor storage, `catch-up.ts`, and `snapshot-resync.ts` handling `snapshot_required` and `WS_SEQUENCE_GAP`. Full reconnect E2E requires live stack (deferred).
3. **Pause/disconnect/catch-up states visually distinct:** `ConnectionHealthBanner` + `StatusStrip` badges per `ConnectionHealthState`; fixture offline profile E2E preserved.
4. **Silent Relay meaningful live topology/activity:** `POST /api/v1/runs` + `step` mutate world state and emit graph/timeline events; integration tests prove create/step/bootstrap when PostgreSQL is available.

## Files added

| Area              | Key paths                                                                                                                                                                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contracts         | `packages/contracts-ts/src/live-run.ts`, `packages/contracts-python/src/aegis_contracts/live_run.py`                                                                                                                   |
| Backend           | `apps/api/src/aegis_api/runs/`, `services/simulation/src/aegis_simulation/run_command_service.py`, `graph_projection.py`                                                                                               |
| Frontend realtime | `apps/web/lib/realtime/**`                                                                                                                                                                                             |
| Frontend features | `apps/web/features/live-run/**`, `apps/web/features/timeline/**`                                                                                                                                                       |
| Tests             | `tests/integration/run-api/test_run_commands.py`, `tests/contract/live-run/test_live_run_fixtures.py`, `tests/e2e/live-run.spec.ts`, `apps/web/lib/realtime/run-reducer.test.ts`                                       |
| Fixtures/schemas  | `tests/contract/fixtures/valid/live_run_v1.json`, `snapshot_bootstrap_v1.json`, `connection_health_v1.json`, `run_create_request_v1.json`, `run_command_response_v1.json`, `timeline_entry_v1.json` + matching schemas |
| Docs/ADR          | `docs/AEGIS-v1.0-Agent-Specs/adrs/0014-live-command-centre-integration.md`                                                                                                                                             |
| Demo script       | `apps/web/scripts/capture-live-run-demo.mjs`                                                                                                                                                                           |

## Files modified

| File                                                                                                             | Reason                                                       |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `packages/contracts-ts/src/index.ts`, `packages/contracts-python/src/aegis_contracts/__init__.py`, `fixtures.py` | Export Phase 13 contracts                                    |
| `packages/contracts-*/src/versioning.*`                                                                          | `WORKSPACE_VERSION` → `0.0.0-phase13`                        |
| `packages/persistence/.../postgres.py`                                                                           | `PostgresGraphSnapshotRepository`, run/scenario list helpers |
| `apps/api/src/aegis_api/main.py`, `apps/api/pyproject.toml`                                                      | Wire runs router; add simulation dependency                  |
| `apps/web/features/shell/components/*`                                                                           | LiveRunProvider, TimelineView, live status strip             |
| `apps/web/features/operational-graph/components/operational-graph-view.tsx`                                      | External GraphStore + revision sync for live deltas          |
| `apps/web/lib/api/production-client.ts`, `create-client.ts`                                                      | Run commands + bootstrap endpoints                           |
| `apps/web/src/app/(shell)/scenarios/page.tsx`                                                                    | Start Silent Relay in live mode                              |
| `apps/web/package.json`, `pnpm-lock.yaml`                                                                        | `@aegis/realtime-client` dependency                          |
| `.env.example`, `docker-compose.yml`                                                                             | Live stack env vars, worker outbox-relay mode                |
| `tests/contract/fixtures/compatibility-manifest.json`                                                            | Phase 13 schema hashes                                       |

## Files removed

None.

## Contracts introduced or changed

| Contract                                        | Version         | Description                   |
| ----------------------------------------------- | --------------- | ----------------------------- |
| `ConnectionHealthState`                         | v1              | Live connection FSM enum      |
| `RunReplicatedState`                            | v1              | Shared reducer state          |
| `RealtimeReducerAction`                         | v1              | Discriminated reducer actions |
| `SnapshotBootstrapPayloadV1`                    | v1              | Resync bootstrap payload      |
| `RunCreateRequestV1`, `RunCommandResponseV1`    | v1              | Run command HTTP contracts    |
| `ConnectionHealthSnapshotV1`, `TimelineEntryV1` | v1              | UI projection contracts       |
| `WORKSPACE_VERSION`                             | `0.0.0-phase13` | Workspace parity bump         |

## Database migrations

None (reuses Phase 02 `runs`, `graph_snapshots`, Phase 11 `domain_events`).

## Environment and configuration changes

See `.env.example` and `docker-compose.yml`:

- `NEXT_PUBLIC_AEGIS_DATA_SOURCE=api` — enables live mode (default `fixture` preserves CI)
- `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_URL`, `NEXT_PUBLIC_AEGIS_WS_TOKEN`
- `AEGIS_WORKER_MODE=outbox-relay` for worker service

## Generated artifacts and fixtures

- Fixture-mode screenshots: `/opt/cursor/artifacts/screenshots/13-fixture-command-centre.png`, `13-fixture-selected-asset.png`, `13-fixture-responsive-layout.png`
- Live demo script: `apps/web/scripts/capture-live-run-demo.mjs` (requires full stack)

## Tests added

| Test                        | Proves                                                   |
| --------------------------- | -------------------------------------------------------- |
| `run-reducer.test.ts`       | Shared sequence, gap halt, duplicate suppression         |
| `test_live_run_fixtures.py` | Cross-language Phase 13 fixture parity                   |
| `test_run_commands.py`      | Create, step, graph bootstrap, idempotency (PG required) |
| `live-run.spec.ts`          | Fixture shell graph + timeline + responsive layout       |

## Commands executed and results

| Command                                                                | Result                                                                  |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `pnpm format:check`                                                    | **PASS**                                                                |
| `pnpm lint`                                                            | **PASS**                                                                |
| `pnpm typecheck`                                                       | **PASS**                                                                |
| `pnpm test`                                                            | **PASS**                                                                |
| `pnpm build`                                                           | **PASS**                                                                |
| `pnpm check-contracts`                                                 | **PASS**                                                                |
| `uv run ruff check .`                                                  | **PASS**                                                                |
| `uv run pytest -q`                                                     | **PASS** — 274 passed, 31 skipped                                       |
| `uv run pytest tests/integration -q`                                   | **SKIPPED** — 31 skipped (PostgreSQL/Redis unavailable)                 |
| `uv run pytest tests/integration/run-api -q`                           | **SKIPPED** — 2 skipped (PostgreSQL unavailable)                        |
| `uv run mypy apps services packages`                                   | **BLOCKED** — pre-existing `aegis_api.db.session` duplicate module path |
| `docker compose up -d postgres redis object-storage`                   | **BLOCKED** — Docker unavailable in VM                                  |
| `pnpm --filter @aegis/web test:e2e`                                    | **PASS** — 25 passed                                                    |
| `pnpm --filter @aegis/web exec node scripts/capture-live-run-demo.mjs` | **NOT RUN** — requires PostgreSQL/Redis/API stack                       |

### Live stack startup (when services available)

```bash
docker compose up -d postgres redis object-storage
uv run alembic upgrade head
uv run aegis-worker --mode outbox-relay   # background
uv run aegis-api                          # background
NEXT_PUBLIC_AEGIS_DATA_SOURCE=api pnpm --filter @aegis/web start
pnpm --filter @aegis/web exec node scripts/capture-live-run-demo.mjs
```

## Architecture decisions and ADRs

- **Created:** [0014-live-command-centre-integration.md](../AEGIS-v1.0-Agent-Specs/adrs/0014-live-command-centre-integration.md) (Status: **Proposed**)
- Single sequence-aware reducer owns graph/timeline/run status
- Graphology `GraphStore` semantic source of truth; Sigma.js renderer only
- TanStack Query for HTTP bootstrap/commands; `@aegis/realtime-client` for transport only

## Known limitations

- Full live-stack E2E and demo capture not executed in VM without PostgreSQL/Redis
- API runtime restore replays persisted events on restart (bounded replay in `RunCommandService`)
- Production OIDC deferred to Phase 30; dev token auth only
- `mypy` fails on pre-existing API session module path issue (Phase 11/12 pattern)
- No auto-advance worker; live demo uses explicit `step` endpoint

## Deferred work

- Phase 14+: consume `RunReplicatedState` outputs, not raw WebSocket frames
- Phase 30: production auth
- Auto-advance simulation worker (Phase 14+ scope)

## Risks for dependent phases

- Do not create competing client event caches or graph models
- Projection rule changes require contract version bump + ADR update
- Changing WebSocket recovery semantics must stay aligned with ADR 0013/0014

## Prohibited-shortcut confirmation

No scaffolding-only reducers, no Redis-as-authority, no direct Sigma mutation from transport handlers, no skipped/weakened prior tests, fixture mode preserved as CI default, validation commands executed with honest results.
