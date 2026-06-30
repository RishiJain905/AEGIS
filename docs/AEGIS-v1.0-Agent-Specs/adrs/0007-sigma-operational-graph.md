# ADR 0007: Sigma.js Operational Graph

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 06 requires the primary 2D operational investigation graph in the command-centre shell. Phase 05 established `@aegis/graph-domain` as the renderer-independent semantic engine (ADR 0006). Phase 04 established shell layout and workspace state (ADR 0005).

Sigma.js must render and handle interaction without duplicating graph domain truth. `architecture.md` designates Sigma.js as the primary WebGL graph and Graphology as the in-browser operational model; Three.js remains a later derived presentation mode.

## Decision

1. **Semantic source of truth:** All path, neighborhood, incident subgraph, dependency, and filter queries call `@aegis/graph-domain` `GraphStore`. Sigma.js and presentation-layer Graphology in `apps/web` are derived projections only.

2. **Presentation Graphology boundary:** `apps/web/features/operational-graph/adapters/` may construct a private Graphology `Graph` for Sigma.js rendering. This graph is rebuilt from canonical entities via `GraphStore.applyFilters()` and `exportSnapshot()`. Domain Graphology inside `@aegis/graph-domain` remains private (ADR 0006).

3. **Web-local interaction contracts:** `OperationalGraphAdapter`, `GraphVisualState`, `GraphSelection`, and `GraphCameraBookmark` live in `apps/web/features/operational-graph/contracts/`. They are ephemeral UI contracts, not durable cross-language wire shapes.

4. **Shell integration:** `OperationalGraphView` mounts in `VisualizationSlot` via `next/dynamic` with `ssr: false` to avoid Sigma WebGL SSR failures. Phase 05 `GraphDomainHarnessPanel` is removed from the production visualization path.

5. **Graph controls in `@aegis/ui`:** Search, layer toggles, legend, camera, isolation, and overlay controls are shared UI primitives without Sigma imports.

6. **Inspector linkage:** Selected graph entities drive `GraphEntityInspector` and `IncidentContextInspector` sections via `selectedEntityId` in the workspace store.

7. **Layout:** Phase 06 uses deterministic cluster-aware initial placement cached in a component ref. ForceAtlas2 worker layout is deferred to Phase 07.

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| Sigma owns graph state | Violates architecture; duplicates domain engine |
| Export domain Graphology to web | Leaks ADR 0006 private boundary |
| Per-node React components | Forbidden by spec and bestPractices §12 |
| ForceAtlas2 in Phase 06 | Explicitly Phase 07 scope |
| Cross-language GraphVisualState wire contract | Ephemeral UI state; not durable domain data |

## Consequences

- `apps/web` depends on `sigma`, `graphology`, and `graphology-types` for presentation only.
- Phase 07 must preserve adapter boundary and extend layout/performance without moving algorithms into React.
- Phase 11+ realtime deltas call `GraphStore.applyDelta()` then adapter sync; gap detection remains fail-closed.
- Unmounting `SigmaCanvas` must call `adapter.dispose()` to release WebGL resources.

## Security and reliability

- No architecture non-negotiable rules are changed.
- Visual overlays reflect canonical risk/status fields; they do not invent domain facts.
- Filtering distinguishes hidden from deleted (Phase 05 semantics preserved).
- No offensive capability introduced.

## Approval

- [ ] Project owner
