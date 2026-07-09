# ADR 0028: Three.js Semantic Renderer

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 27 requires a read-only React Three Fiber / Three.js adapter over the same semantic graph consumed by Sigma.js. Architecture rule 6 and ADR 0007 designate Sigma.js as the primary analysis surface; Three.js is a later derived presentation mode. Phase 26 established historical replay UI isolation and sequence-primary cursor semantics that Phase 27 must preserve when rendering reconstructed state.

## Decision

1. **Secondary presentation only:** The Three.js renderer lives in `apps/web/features/cinematic-graph/**` and never becomes domain truth. Sigma.js remains the default investigation tool (`graphViewMode` defaults to `2d`).

2. **Same semantic source:** `SemanticSceneAdapter.syncFromStore()` consumes `@aegis/graph-domain` `GraphStore` (filters + `exportSnapshot()`). Live and replay paths pass the same store/snapshot/revision already used by `OperationalGraphView`. No second graph model, risk model, or reconstruction path.

3. **Web-local scene contracts:** `SemanticSceneAdapter`, `SceneNode`, `SceneEdge`, `CameraBookmark3D`, `RenderQualityTier`, `CapabilityReport`, and `GraphViewMode` are ephemeral UI contracts in `apps/web`. They are not durable cross-language wire schemas.

4. **Selection bridge:** 2D↔3D selection uses stable entity IDs via `useWorkspaceUiStore.selectedEntityId` and `useGraphVisualStore` selection. Mode switches preserve selection; camera/navigation never mutate domain state.

5. **Capability and fallback:** `probeCapabilityReport()` recommends `high` / `medium` / `low` / `fallback2d`. Unsupported WebGL forces 2D with an operator-visible notice. Reduced motion disables camera easing and prefers demand frameloop.

6. **Lifecycle:** Adapters and R3F canvases dispose geometries, materials, listeners, and animation loops on unmount/mode switch. DPR is capped. Rendering pauses when the document is hidden.

7. **Positions are presentation-only:** 3D positions derive from Phase 07 `nodePositions` / deterministic layout with cluster-based Z. Coordinates are never written to `@aegis/graph-domain` or PostgreSQL.

8. **Phase 28 boundary:** Directed cinematic camera sequences, incident cutscenes, and narrative story direction remain Phase 28. Scoring/after-action UX remains Phase 29.

## Alternatives considered

| Alternative | Why not chosen |
| --- | --- |
| Three.js owns graph state | Violates architecture; duplicates GraphStore |
| Cross-language SceneNode wire contract | Ephemeral presentation; no cross-process need |
| Replace Sigma as default | Forbidden by architecture and Phase 27 scope |
| Absorb Phase 28 cinematic direction | Explicitly out of scope |

## Consequences

- `apps/web` depends on `three`, `@react-three/fiber`, and `@react-three/drei` for presentation only.
- `@aegis/graph-domain` must not depend on Three.js (existing acceptance tests preserved).
- Phase 28 must consume the same `SemanticSceneAdapter` / selection bridge without inventing domain facts or forking reconstruction.
- Visual evidence and e2e cover mode toggle, fallback, and 2D/3D parity.

## Security and reliability

- No architecture non-negotiable rules are changed.
- Invalid/malformed graph export fails closed with structured adapter errors.
- No remote model/texture loading; shaders are local and reviewed.
- No offensive capability introduced.

## Approval

- [ ] Project owner
