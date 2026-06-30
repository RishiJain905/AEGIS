# ADR 0008: Graph Performance and Worker Layouts

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 07 hardens the Sigma.js operational graph for hundreds to low thousands of elements. Phase 05 (`@aegis/graph-domain`) remains semantic truth. Phase 06 established the Sigma adapter, ephemeral `GraphVisualState`, and deterministic initial placement on the main thread (ADR 0007).

`architecture.md` requires ForceAtlas2 in a Web Worker, batched graph updates, level of detail, and position preservation as presentation optimization.

## Decision

1. **ForceAtlas2 in dedicated Web Worker:** Layout runs in `apps/web/workers/layout/` using `graphology-layout-forceatlas2`. The main thread orchestrates requests via `LayoutCoordinator`.

2. **Web-local versioned worker protocol:** `LayoutWorkerRequest` / `LayoutWorkerResult` v1 live in `apps/web/features/operational-graph/contracts/`. They are not durable cross-language contracts.

3. **Stale-result rejection:** Layout results apply only when `requestId` and `graphRevision` (`runId`, `sequence`, `revision`) match the active coordinator state.

4. **LOD and cluster collapse are presentation projections:** `LodPolicy` and collapsed cluster super-nodes affect Sigma rendering only. Domain `GraphClusterV1` membership is unchanged.

5. **Position cache is optimization only:** `nodePositions` in `GraphVisualState` and worker output are not replay truth and are not written to PostgreSQL.

6. **Controlled relayout:** Filter/selection/hover changes do not restart global layout. Topology-visible-set changes trigger incremental or full worker passes.

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| ForceAtlas2 on main thread | Violates architecture and blocks UI under load |
| Layout in `@aegis/graph-domain` | Domain package must stay renderer-independent (ADR 0006) |
| Durable layout wire contract | Positions are browser presentation state only |
| Global relayout on every delta | Violates Phase 07 spec mental-map preservation |

## Consequences

- `apps/web` adds `graphology-layout-forceatlas2` and worker entry modules.
- Phase 11+ realtime integrations call domain delta apply, then coordinator incremental layout.
- Benchmarks live in `tests/performance/graph/**` with manifest budgets in `docs/graph-performance.md`.
- Unmount/run change must cancel and terminate workers.

## Security and reliability

- Worker payloads exclude secrets and network access.
- Stale/cancelled results fail closed (no position mutation).
- Renderer and worker cleanup required on teardown.

## Approval

- [ ] Project owner
