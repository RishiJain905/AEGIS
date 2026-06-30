# AEGIS Graph Domain Engine

> Phase 05 — renderer-independent graph state, deltas, and algorithms.

## Purpose

`@aegis/graph-domain` implements the operational graph domain engine consumed by Phase 06 (Sigma.js), replay tooling, and future 3D adapters. Canonical wire shapes remain in `@aegis/contracts-ts`; this package owns in-process domain behavior.

## Package boundaries

| Allowed | Forbidden |
| ------- | --------- |
| `@aegis/contracts-ts` | React, Next.js, Sigma.js, Three.js |
| `graphology` (private) | Redefining `GraphSnapshotV1` / `GraphDeltaV1` |
| | Importing `apps/*` or `services/*` |

Graphology types are **not exported**. Consumers interact with `GraphStore` and canonical contract types only.

## Core interfaces

### `GraphStore`

- `loadSnapshot(snapshot)` — replace in-memory state from `GraphSnapshotV1`
- `applyDelta(delta)` / `applyDeltas(deltas)` — sequence/revision-aware mutation
- `exportSnapshot()` — canonical projection for replay and renderers
- `validateConsistency()` — structural integrity report
- `queryPaths(query)` — returns `GraphPathResultV1`
- `getNeighborhood(nodeId, options)` — k-hop expansion with hop rings
- `getIncidentSubgraph(seedNodeIds, options)` — investigation-focused induced subgraph
- `getConnectedComponents()`, `getClusterMembers()`, `getDependencies()`
- `applyFilters(filterSet)` — non-destructive visibility (hidden ≠ deleted)

### `GraphDeltaApplyResult`

Statuses: `applied`, `duplicate`, `rejected`, `gap_detected`.

## Delta semantics

| Condition | Behavior |
| --------- | -------- |
| `delta.runId !== store.runId` | Reject (`GRAPH_RUN_MISMATCH`) |
| `delta.sequence <= lastAppliedSequence` | Idempotent duplicate — no mutation |
| `delta.sequence > lastAppliedSequence + 1` | Reject (`GRAPH_SEQUENCE_GAP`) — no partial apply |
| `delta.sequence === lastAppliedSequence + 1` | Apply if revision valid |
| Entity revision older than stored | Reject (`GRAPH_STALE_REVISION`) |
| `delete_node` | Cascade-remove incident edges |
| `delete_edge` / missing delete target | Idempotent no-op |
| Edge upsert with missing endpoint | Reject (`GRAPH_CONSISTENCY_VIOLATION`) |

Snapshot load skips edges whose endpoints are missing rather than inserting orphan topology.

## Pathfinding

- BFS over filtered edges up to `maxHops`
- Optional `relationshipTypes` and `directedOnly` filters
- Paths sorted **lexicographically** by node ID tuple
- `explanation` includes `pathsConsidered`, `pathsFound`, `hopCount`, `ordering`

## Graph layers (filtering)

| Layer | Visibility rule (summary) |
| ----- | ------------------------- |
| `infrastructure` | device, service, database, control asset types |
| `activity` | nodes with incident edges where `eventCount > 0` |
| `security_state` | `riskScore > 0` or non-normal status |
| `investigation` | suspicious / under_investigation / contained / compromised |
| `presentation` | always passes; use `hiddenNodeIds` / `hiddenEdgeIds` for local toggles |

Filters return a `FilteredGraphView`; `exportSnapshot()` always returns full canonical state.

## Performance assumptions

Medium fixture (`packages/graph-domain/fixtures/medium-graph-snapshot.json`):

- 2,500 nodes, 5,000 edges
- CI budgets: load & batch delta apply < 5s; path query < 3s; 2-hop neighborhood < 1s

## Consumers

- **Phase 06:** mount Sigma.js over the same `GraphStore` instance; do not fork graph state
- **Phase 11–13:** apply WebSocket deltas through `applyDelta`; on gap, fetch snapshot before continuing
- **Phase 27:** read-only 3D adapter from `exportSnapshot()` or filtered view

## Related documents

- ADR 0006: `docs/AEGIS-v1.0-Agent-Specs/adrs/0006-graph-domain-engine.md`
- Phase 05 spec: `docs/AEGIS-v1.0-Agent-Specs/graph-platform/05-graph-domain-engine.md`
- Canonical contracts: `docs/contracts/versioning.md`
