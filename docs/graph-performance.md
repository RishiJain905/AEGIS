# Graph Performance (Phase 07)

> Worker layouts, LOD, cluster presentation, and measurable renderer budgets for the Sigma.js operational graph.

## Architecture boundary

```text
GraphStore (semantic truth)
        ↓
LayoutCoordinator + Layout Web Worker (ForceAtlas2)
        ↓
UpdateBatcher + LodController + ClusterPresentation
        ↓
SigmaOperationalGraphAdapter → Sigma.js
        ↓
GraphVisualState.nodePositions (presentation cache only)
```

Worker coordinates, collapsed clusters, and LOD tiers are **presentation-only**. They are never written to `@aegis/graph-domain` or durable contracts.

## Worker protocol (v1)

| Message | Direction | Purpose |
| --- | --- | --- |
| `LayoutWorkerRequest` | main → worker | Nodes, edges, seed positions, settings, `graphRevision` |
| `LayoutWorkerResult` (`progress`/`complete`/`cancelled`/`error`) | worker → main | Positions and timing |
| `cancel` | main → worker | Stop active `requestId` |
| `shutdown` | main → worker | Terminate worker |

### Stale-result protection

Results are applied only when:

1. `result.requestId === activeRequestId`
2. `result.graphRevision` matches the current snapshot revision (`runId:sequence:revision`)

Stale results increment `droppedWorkerResults` in `GraphPerformanceSample` and are ignored.

### Cancellation

Run changes, unmount, and superseding layout requests call `cancel` on the active worker request. Cancelled results do not mutate positions.

## Layout modes and relayout triggers

| Trigger | Mode |
| --- | --- |
| Initial load / run change / revision change | `full` |
| Small visible-set delta (≤5 nodes) | `incremental` (20 FA2 iterations) |
| Filter/selection/hover-only changes | no relayout |

Seed order:

1. Persisted `nodePositions`
2. `computeInitialLayout()` cluster placement
3. Strongest-neighbor offsets for new nodes

## LOD tiers

| Tier | Approx. density | Behavior |
| --- | --- | --- |
| `detail` | <200 nodes | All labels, all edges |
| `balanced` | 200+ nodes / 400+ edges | Selected labels, edge cap 1500 |
| `overview` | 800+ nodes / 1600+ edges | Selected labels, edge cap 600, cluster collapse threshold 20 |
| `dense` | 1500+ nodes / 3000+ edges | No labels, edge cap 300, cluster collapse threshold 10 |

Highlighted edges are prioritized when edge caps apply.

## Cluster collapse

Collapsed clusters render as presentation super-nodes (`presentation:cluster:*`). Clicking a super-node expands the cluster by removing it from `collapsedClusterIds`. Domain cluster membership is unchanged.

## Position persistence

- Session cache: `positionsRef` + `GraphVisualState.nodePositions`
- Pinning: `pinnedNodeIds` (future UI toggle; protocol supports pinned nodes)
- Reset on run change via `resetVisualState()`

## Benchmark datasets

| Dataset | Nodes | Edges | Worker budget | Adapter sync budget |
| --- | ---: | ---: | ---: | ---: |
| `target` | 500 | ~900 | 8000 ms | 300 ms |
| `stress` | 2500 | 5000 | 15000 ms | 250 ms |

Generate fixtures:

```bash
pnpm generate:graph-fixtures
```

Stress demo route: `/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAW`

## Validation commands

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm --filter @aegis/web test:e2e
```

## Constraints for later phases

- Do not move layout into `@aegis/graph-domain`
- Realtime deltas must call `GraphStore.applyDelta()` then adapter sync; layout coordinator handles incremental worker passes
- Preserve worker stale rejection and renderer `dispose()` semantics
- Do not treat presentation coordinates as replay truth
