# Phase 07 Handoff — Graph Performance and Worker Layouts

## Status

`READY FOR VALIDATION`

## Implemented

Phase 07 deliverables per `docs/AEGIS-v1.0-Agent-Specs/graph-platform/07-graph-performance-and-worker-layouts.md`:

- Versioned Web Worker ForceAtlas2 layout protocol (`LayoutWorkerRequest`/`LayoutWorkerResult` v1)
- Cancellation and stale-result rejection by graph revision (`runId:sequence:revision`)
- Incremental seeding via `computeInitialLayout()` + strongest-neighbor offsets; pinning support in protocol
- `LayoutCoordinator`, `UpdateBatcher`, `LodController`, cluster presentation collapse/expand
- Batched adapter sync with frame-budget instrumentation (`GraphPerformanceSample` v1)
- Deterministic target (500 nodes) and stress (2500 nodes) graph generators
- Benchmark manifest, performance tests, extended E2E, documentation, ADR 0008

## Files added

| Area        | Key paths                                                                                                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Worker      | `apps/web/workers/layout/layout.worker.ts`, `force-atlas2-runner.ts`                                                                                                                                 |
| Contracts   | `apps/web/features/operational-graph/contracts/layout-worker-protocol.ts`, `graph-revision.ts`, `lod-policy.ts`, `graph-performance-sample.ts`, `benchmark-manifest.ts`, `phase07-contracts.test.ts` |
| Performance | `apps/web/features/operational-graph/performance/**`                                                                                                                                                 |
| Fixtures    | `packages/graph-domain/src/fixtures/graph-performance-snapshots.ts`, `scripts/generate_graph_fixture.ts`                                                                                             |
| Tests       | `tests/performance/graph/**`, `tests/unit/graph-fixtures/generator.test.ts`                                                                                                                          |
| Screenshots | `apps/web/scripts/capture-graph-performance-screenshots.mjs`                                                                                                                                         |
| Docs/ADR    | `docs/graph-performance.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0008-graph-performance-and-worker-layouts.md`                                                                                         |

## Files modified

| File                                                                              | Reason                                                       |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `apps/web/features/operational-graph/adapters/sigma-operational-graph-adapter.ts` | LOD, cluster presentation, worker positions                  |
| `apps/web/features/operational-graph/components/operational-graph-view.tsx`       | Coordinator, batcher, collapse controls                      |
| `apps/web/features/operational-graph/contracts/graph-visual-state.ts`             | `pinnedNodeIds`, `collapsedClusterIds`, `layoutStatus`       |
| `apps/web/features/operational-graph/contracts/operational-graph-adapter.ts`      | `SyncFromStoreOptions`, `LodRenderHints`                     |
| `apps/web/features/operational-graph/stores/graph-visual-store.ts`                | Cluster/layout store actions                                 |
| `apps/web/lib/api/fixture-client.ts`                                              | Runtime stress snapshot for `run_01ARZ3NDEKTSV4RRFFQ69G5FAW` |
| `apps/web/fixtures/shell-dataset.json`                                            | Stress demo run entry                                        |
| `apps/web/package.json`                                                           | `graphology-layout-forceatlas2` dependency                   |
| `apps/web/vitest.config.ts`                                                       | Performance test paths and aliases                           |
| `packages/graph-domain/src/fixtures/medium-graph-snapshot.ts`                     | Cluster metadata                                             |
| `packages/graph-domain/src/index.ts`                                              | Export performance snapshots                                 |
| `packages/contracts-ts/src/versioning.ts`                                         | `WORKSPACE_VERSION` → `0.0.0-phase07`                        |
| `packages/contracts-python/src/aegis_contracts/versioning.py`                     | Parity bump                                                  |
| `packages/graph-domain/src/aegis_graph_domain/__init__.py`                        | Stub parity bump                                             |
| `docs/frontend/operational-graph.md`                                              | Link to graph performance docs                               |
| `tests/e2e/operational-graph.spec.ts`                                             | Stress run and cluster collapse E2E                          |
| `package.json`                                                                    | `generate:graph-fixtures` script                             |
| `.gitignore`                                                                      | Generated fixture output path                                |

## Files removed

| File                                                   | Reason                                                                                                               |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `tests/performance/graph/renderer-interaction.test.ts` | Moved to `apps/web/features/operational-graph/performance/renderer-interaction.test.ts` for Sigma mock compatibility |

## Contracts introduced or changed

| Contract                                     | Version         | Description                                             |
| -------------------------------------------- | --------------- | ------------------------------------------------------- |
| `LayoutWorkerRequest` / `LayoutWorkerResult` | v1 (web-local)  | Versioned worker protocol with cancel/shutdown messages |
| `GraphRevision`                              | v1 (web-local)  | Stale layout rejection key                              |
| `LodPolicy` / `LodRenderHints`               | v1 (web-local)  | Tiered edge/label/cluster degradation                   |
| `GraphPerformanceSample`                     | v1 (web-local)  | Frame/sync/worker instrumentation                       |
| `GraphBenchmarkManifest`                     | v1 (web-local)  | Target/stress budgets                                   |
| `GraphVisualState`                           | v1 additive     | `pinnedNodeIds`, `collapsedClusterIds`, `layoutStatus`  |
| `WORKSPACE_VERSION`                          | `0.0.0-phase07` | Workspace metadata                                      |

Phase 01 durable wire contracts unchanged.

## Database migrations

None.

## Environment and configuration changes

None.

## Generated artifacts and fixtures

- `scripts/generate_graph_fixture.ts` → `apps/web/fixtures/generated/*.json` (gitignored)
- Runtime stress snapshot via `buildStressGraphSnapshot()` for run `run_01ARZ3NDEKTSV4RRFFQ69G5FAW`
- Screenshots under `/opt/cursor/artifacts/screenshots/07-*.png`

## Tests added

| Test                                               | Proves                                                                   |
| -------------------------------------------------- | ------------------------------------------------------------------------ |
| `phase07-contracts.test.ts`                        | Protocol/LOD/sample/manifest validation                                  |
| `performance/*.test.ts`                            | Coordinator stale rejection, LOD, batching, clusters, acceptance mapping |
| `tests/performance/graph/worker-layout.test.ts`    | FA2 target budget + cancellation                                         |
| `features/.../renderer-interaction.test.ts`        | Adapter sync budget on target graph                                      |
| `tests/performance/graph/resource-cleanup.test.ts` | Worker terminate + batcher dispose                                       |
| `tests/unit/graph-fixtures/generator.test.ts`      | Deterministic fixture topology                                           |
| `tests/e2e/operational-graph.spec.ts` (extended)   | Stress run interactivity, cluster collapse, responsive                   |

## Commands executed and results

| Command                                  | Result                                            |
| ---------------------------------------- | ------------------------------------------------- |
| `pnpm format:check`                      | PASS                                              |
| `pnpm lint`                              | PASS (ESLint + dependency-cruiser: 0 violations)  |
| `pnpm typecheck`                         | PASS                                              |
| `pnpm test`                              | PASS (graph-domain + contracts + ui + web suites) |
| `pnpm build`                             | PASS                                              |
| `CI=1 pnpm --filter @aegis/web test:e2e` | PASS (23 Playwright tests)                        |

### Benchmark commands (Node 22, linux)

```bash
cd apps/web
pnpm exec vitest run ../../tests/performance/graph/worker-layout.test.ts features/operational-graph/performance/renderer-interaction.test.ts
```

| Dataset  | Metric                                             |  Budget | Measured |
| -------- | -------------------------------------------------- | ------: | -------: |
| `target` | Worker layout complete                             | 8000 ms | ~1108 ms local / ~4618 ms CI |
| `target` | Adapter sync                                       |  300 ms |  ~150 ms local / ~169 ms CI |
| `stress` | Cancellation path (500-node fixture, early cancel) |     n/a |  ~684 ms |

### Visual evidence commands

```bash
pnpm --filter @aegis/web build
pnpm --filter @aegis/web start
SCREENSHOT_BASE_URL=http://127.0.0.1:3000 node apps/web/scripts/capture-graph-performance-screenshots.mjs
```

Screenshots:

- `07-desktop-command-centre-graph.png`
- `07-large-stress-graph.png`
- `07-cluster-collapsed-lod.png`
- `07-expanded-cluster-region.png`
- `07-selected-node-inspector-post-layout.png`
- `07-responsive-graph.png`

## Architecture decisions and ADRs

- **ADR 0008** (`docs/AEGIS-v1.0-Agent-Specs/adrs/0008-graph-performance-and-worker-layouts.md`): ForceAtlas2 worker, web-local protocol, stale rejection, presentation-only LOD/clusters/positions.
- No changes to `architecture.md` non-negotiable rules.

## Known limitations

- Pinning UI toggle not exposed (protocol + store fields ready).
- Stress layout completion for 2500 nodes can take multiple seconds on first load; LOD keeps canvas interactive during worker runs.
- Playwright browsers must be installed (`pnpm exec playwright install chromium`) in fresh environments.
- `next start` warns with standalone output; e2e uses `pnpm start` successfully.

## Deferred work

- Phase 08 Scenario SDK
- Live WebSocket delta streaming (Phases 11–13)
- Three.js cinematic view (Phase 27)
- Backend `GET /api/v1/runs/{id}/graph`

## Risks for dependent phases

- Realtime phases must preserve `graphRevision` stale rejection when applying layout results after deltas.
- Do not write worker coordinates into `@aegis/graph-domain` or durable contracts.
- Preserve `dispose()` + worker `shutdown()` on route/run teardown.
- Cluster collapse is presentation-only; domain `GraphClusterV1` remains authoritative for membership queries.

## Acceptance criteria evidence

| Criterion                                             | Evidence                                                                                               |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Target fixtures interactive within documented budgets | `worker-layout.test.ts`, `renderer-interaction.test.ts`, benchmark table above                         |
| Small updates preserve mental map                     | `relayout-triggers` + `acceptance-criteria.test.ts` (`none` trigger on unchanged visible set)          |
| Workers/renderers do not leak resources               | `resource-cleanup.test.ts`, view unmount `dispose()` effect, worker `shutdown()`                       |
| Degradation preserves investigation usefulness        | LOD/cluster tests, stress E2E, screenshots `07-cluster-collapsed-lod.png`, `07-large-stress-graph.png` |

## Prohibited-shortcut confirmation

No scaffolding-only paths, no domain semantic changes, no Phase 08+ features, no skipped/weakened prior tests, and all listed validation commands were executed in the current tree.
