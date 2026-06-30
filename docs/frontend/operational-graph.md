# AEGIS Operational Graph (Sigma.js)

> Phase 06 — 2D operational investigation graph renderer and interaction layer.

## Purpose

The operational graph is the primary analysis surface for AEGIS Command. It renders canonical graph snapshots from `@aegis/graph-domain` using Sigma.js, with search, filtering, selection, path tracing, neighborhood isolation, and inspector integration.

## Architecture boundary

```text
GraphSnapshotV1 (TanStack Query)
        ↓
GraphStore.loadSnapshot()          ← semantic truth (@aegis/graph-domain)
        ↓
OperationalGraphAdapter.syncFromStore()
        ↓
Presentation Graphology + Sigma.js   ← renderer only (apps/web)
        ↓
GraphVisualState (Zustand)         ← ephemeral UI (positions, highlights, camera)
```

**Rules:**

- Do not duplicate graph algorithms in React or Sigma adapters.
- Do not treat coordinates, colors, or camera state as domain facts.
- Hidden entities (filters) are not deleted from canonical state.

## Key modules

| Path                                                        | Role                                                     |
| ----------------------------------------------------------- | -------------------------------------------------------- |
| `apps/web/features/operational-graph/`                      | Adapter, canvas, view, contracts, semantic styling       |
| `apps/web/features/inspector/`                              | Asset and incident context inspector sections            |
| `packages/ui/src/graph-controls/`                           | Shared search, layer, legend, camera, isolation controls |
| `apps/web/features/shell/components/visualization-slot.tsx` | Shell mount point (dynamic import, SSR disabled)         |

## Interaction modes

| Mode                   | Domain API                                   | UI trigger                    |
| ---------------------- | -------------------------------------------- | ----------------------------- |
| Search                 | Client-side label/ID filter on visible nodes | `GraphSearchInput`            |
| Layer filter           | `GraphStore.applyFilters()`                  | `GraphLayerControls`          |
| Neighborhood isolation | `GraphStore.getNeighborhood()`               | Isolate / Restore buttons     |
| Path trace             | `GraphStore.queryPaths()`                    | Path mode + two node picks    |
| Incident focus         | `GraphStore.getIncidentSubgraph()`           | Incident route + selection    |
| Dependencies           | `GraphStore.getDependencies()`               | Highlight mode (programmatic) |

## Accessibility

- Keyboard-accessible entity list (`graph-entity-list`) mirrors canvas selection.
- Reduced motion disables camera animation duration (`useReducedMotion`).
- Inspector panels provide text equivalents for risk, status, and path results.

## Renderer lifecycle

1. `SigmaCanvas` mounts adapter in `useEffect`.
2. `OperationalGraphView` syncs on filter/selection/highlight changes.
3. Unmount calls `adapter.dispose()` (Sigma `kill()` + graph clear).

## Deferred to Phase 07+

- ForceAtlas2 Web Worker layout
- Label culling, edge reduction, frame budgets at 2500+ nodes
- Live WebSocket delta streaming (Phase 11–13)
- Three.js cinematic view (Phase 27)

## Development

```bash
pnpm --filter @aegis/web dev
# http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
```

E2E: `CI=1 pnpm --filter @aegis/web test:e2e`
