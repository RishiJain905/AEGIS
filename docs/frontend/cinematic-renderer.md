# AEGIS Cinematic Semantic Renderer (Three.js)

> Phase 27 — read-only React Three Fiber presentation over the same semantic graph as Sigma.js.

## Purpose

Provide a secondary 3D semantic view of AEGIS graph state for cinematic/presentation use. The Sigma.js operational graph remains the primary investigation tool.

**Not in this phase:** directed incident cutscenes, story cameras, scoring, or after-action UX (Phases 28–29).

## Architecture boundary

```text
GraphSnapshotV1 / live deltas / ReplayStateV1.graph
        ↓
GraphStore (semantic truth — @aegis/graph-domain)
        ↓
┌───────────────────────────┬────────────────────────────┐
│ SigmaOperationalGraphAdapter │ SemanticSceneAdapter     │
│ → Sigma.js 2D (default)      │ → R3F / Three.js 3D      │
└───────────────────────────┴────────────────────────────┘
        ↓
selectedEntityId (workspace) + GraphVisualState (ephemeral)
```

Rules:

- Do not invent nodes, edges, risk, evidence, incidents, or replay facts.
- Do not write 3D coordinates into domain stores or PostgreSQL.
- Hidden (filtered) entities are not deleted from canonical state.
- Camera controls never mutate domain state.

## Key modules

| Path                                                           | Role                                                        |
| -------------------------------------------------------------- | ----------------------------------------------------------- |
| `apps/web/features/cinematic-graph/adapters/`                  | `SemanticSceneAdapter` projection + dispose                 |
| `apps/web/features/cinematic-graph/contracts/`                 | SceneNode/Edge, CameraBookmark3D, quality tiers, capability |
| `apps/web/features/cinematic-graph/components/`                | R3F canvas, view, mode toggle, fallback notice              |
| `apps/web/features/cinematic-graph/lib/`                       | Capability probe, stable positions, semantic mapping        |
| `apps/web/features/shell/components/visualization-slot.tsx`    | Live 2D/3D mount                                            |
| `apps/web/features/replay/components/replay-visualization.tsx` | Historical 2D/3D mount                                      |

## Visual mapping

| Canonical field                   | 3D presentation                                      |
| --------------------------------- | ---------------------------------------------------- |
| `assetType`                       | Node base color (shared with Sigma semantic styles)  |
| `status`                          | Status marker sphere when status overlay enabled     |
| `riskScore` / risk band           | Risk halo color when risk overlay enabled            |
| `clusterId`                       | Deterministic Z offset for cluster spatialization    |
| `eventCount` / `riskContribution` | Edge width/opacity                                   |
| Evidence / incident overlays      | Marker cubes when overlay toggles + id sets provided |
| Selection                         | Enlarged instance + HTML label                       |

## Camera and navigation

- OrbitControls for pan/rotate/zoom (presentation only).
- `CameraBookmark3D` stores position/target/fov ephemerally.
- `focusNode(id)` frames a selected entity; `resetCamera()` restores default.
- Reduced motion: damping off, demand frameloop, static readable scene + accessible entity list.

## Capability, quality, fallback

| Tier         | Behavior                                    |
| ------------ | ------------------------------------------- |
| `high`       | Full antialias, DPR ≤ 1.75                  |
| `medium`     | DPR ≤ 1.25 (also used under reduced motion) |
| `low`        | DPR = 1, demand frameloop                   |
| `fallback2d` | Force Sigma 2D + capability notice          |

## Lifecycle and cleanup

1. Create `SemanticSceneAdapter` on mount; probe capability.
2. Sync on `graphRevision`, selection, overlays, and snapshot sequence/revision.
3. On unmount/mode switch: `adapter.dispose()`, R3F tears down WebGL resources, visibility listener removed, animation loop cleared.

## Live and replay consumption

- **Live:** same `LiveRunProvider` bootstrap snapshot + `graphStore` + `graphRevision` as Sigma.
- **Replay:** same Phase 25 reconstructed `state.graph` and isolated replay `graphStore` at `ReplayCursorV1.sequence`. No client-side reconstruction. No live mutation.

## Performance limits

- Instanced node meshes; shared materials; Line-based edges.
- Cap device pixel ratio; pause when document hidden.
- Unit/perf suites assert Silent Relay fixture sync budget and dispose clearing last projection.

## Accessibility

- Keyboard-accessible entity list mirrors 3D selection.
- Inspector continues to show domain text for the selected entity.
- Unsupported devices keep the 2D operational graph available.

## Constraints Phase 28 must preserve

- Do not treat Three.js as authoritative analysis or invent domain facts for drama.
- Reuse `SemanticSceneAdapter` / selection bridge; do not fork GraphStore or replay reconstruction.
- Keep Sigma as the default investigation surface unless an approved ADR changes architecture rule 6.
- Directed cinematic sequences must remain derived presentation over structured replay state.

See also: [`cinematic-replay.md`](cinematic-replay.md) (Phase 28).

## Development

```bash
pnpm --filter @aegis/web dev
# http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
# Toggle 2D / 3D in the visualization slot
```

Unit: `pnpm --filter @aegis/web exec vitest run features/cinematic-graph ../../tests/unit/cinematic ../../tests/performance/cinematic`

E2E: `CI=1 pnpm --filter @aegis/web exec playwright test tests/e2e/cinematic-graph.spec.ts`
