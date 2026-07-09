# Phase 27 Handoff — Three.js Semantic Renderer

## Status

`READY FOR VALIDATION`

## Implemented

Mapped to Phase 27 spec Sections 7 and 18:

| Spec item                                                                           | Implementation                                                                              |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Map canonical nodes/edges/clusters/risk/status/evidence into derived scene state    | `SemanticSceneAdapter` + `semantic-mapping.ts` over `GraphStore.exportSnapshot()` / filters |
| Instanced nodes, efficient edges, cluster spatialization, camera focus              | `CinematicSceneCanvas` (InstancedMesh + Line + OrbitControls + `focusNode`)                 |
| Deterministic/stable positions across replay and mode switches                      | `stable-positions.ts` maps Phase 07 XY + cluster Z; never written to domain                 |
| Bridge 2D↔3D selection via stable entity IDs                                       | `selectedEntityId` workspace store + graph visual selection                                 |
| Quality tiers, capability detection, reduced motion, pause-when-hidden, 2D fallback | `capability.ts`, `CapabilityFallbackNotice`, demand frameloop, visibility gate              |
| Dispose geometries/materials/listeners/frame loops                                  | Adapter `dispose()` + R3F unmount + `gl.setAnimationLoop(null)`                             |
| Target-size performance tests                                                       | `tests/performance/cinematic/semantic-scene-perf.test.ts`                                   |
| **AC1** 2D and 3D same semantic state at same cursor                                | Shared `GraphStore`; acceptance + e2e parity                                                |
| **AC2** Unsupported devices fall back cleanly                                       | `fallback2d` + capability notice; unit + visual                                             |
| **AC3** Mode switch preserves selection; no GPU leaks                               | Selection bridge + dispose tests + e2e                                                      |
| **AC4** Reduced-motion remains understandable                                       | Medium tier, no easing, alert + inspector/list                                              |

**Explicitly not implemented:** Phase 28 directed cinematic cameras/cutscenes, Phase 29 scoring/after-action UX, production auth.

## Files added

| Path                                                                 | Reason                                                   |
| -------------------------------------------------------------------- | -------------------------------------------------------- |
| `apps/web/features/cinematic-graph/**`                               | Contracts, adapter, R3F view, capability, store, shaders |
| `apps/web/scripts/capture-cinematic-renderer-demo.mjs`               | Visual evidence harness                                  |
| `tests/unit/cinematic/acceptance.test.ts`                            | AC1–AC4 mapping                                          |
| `tests/performance/cinematic/semantic-scene-perf.test.ts`            | Sync budget + dispose cycles                             |
| `tests/e2e/cinematic-graph.spec.ts`                                  | Playwright mode toggle / parity / replay                 |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/0028-threejs-semantic-renderer.md` | ADR                                                      |
| `docs/frontend/cinematic-renderer.md`                                | Operator/architecture notes                              |
| `docs/handoffs/27-threejs-semantic-renderer-HANDOFF.md`              | This handoff                                             |
| `docs/handoffs/evidence/27-threejs-semantic-renderer/*`              | Screenshots + recording                                  |

## Files modified

| Path                                                           | Reason                                                             |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `apps/web/package.json` / `pnpm-lock.yaml`                     | `three`, `@react-three/fiber`, `@react-three/drei`, `@types/three` |
| `apps/web/features/shell/components/visualization-slot.tsx`    | Live 2D/3D toggle mount                                            |
| `apps/web/features/replay/components/replay-visualization.tsx` | Historical 2D/3D toggle mount                                      |
| `apps/web/vitest.config.ts`                                    | Include cinematic unit/perf suites                                 |
| `docs/AEGIS-v1.0-Agent-Specs/adrs/README.md`                   | Point to ADR 0028                                                  |
| `docs/frontend/operational-graph.md`                           | Phase 27 related note                                              |

## Files removed

None.

## Contracts introduced or changed

Web-local ephemeral contracts only (not durable cross-language wire schemas):

- `SemanticSceneAdapter`, `SceneProjection`, `SyncSceneOptions`
- `SceneNode` / `SceneEdge`
- `CameraBookmark3D`
- `RenderQualityTier` (`high` \| `medium` \| `low` \| `fallback2d`)
- `CapabilityReport`
- `GraphViewMode` (`2d` \| `3d`)

No Phase 01 wire contract version bumps. No Python contract changes.

## Database migrations

None.

## Environment and configuration changes

None required. Fixture mode uses existing `NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture`.

Dependencies added to `@aegis/web` only (pnpm):

- `three@0.178.0`
- `@react-three/fiber@9.2.0`
- `@react-three/drei@10.4.2`
- `@types/three@0.178.0` (dev)

## Generated artifacts and fixtures

Visual evidence under:

- `/opt/cursor/artifacts/phase27-screenshots/`
- `docs/handoffs/evidence/27-threejs-semantic-renderer/`

Including PNGs for command centre, 2D/3D Silent Relay, selection/inspector, camera reset, reduced motion, narrow layout, replay historical 3D, and `27-cinematic-navigation.webm`.

## Tests added

| Test                                                      | Proves                                                                                |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `semantic-scene-adapter.test.ts`                          | Canonical id projection; risk/status/evidence mapping; fallback empty; dispose; focus |
| `capability.test.ts`                                      | WebGL unavailable → fallback; reduced motion tier; DPR caps; stable Z                 |
| `tests/unit/cinematic/acceptance.test.ts`                 | AC1–AC4                                                                               |
| `tests/performance/cinematic/semantic-scene-perf.test.ts` | Sync budget + dispose cycles                                                          |
| `tests/e2e/cinematic-graph.spec.ts`                       | Toggle, 3D render, selection bridge, narrow viewport, replay                          |

## Commands executed and results

```text
pnpm format:check          PASS
pnpm lint                  PASS (eslint + dependency-cruiser)
pnpm typecheck             PASS
pnpm test                  PASS (turbo; @aegis/web 31 files / 91 tests)
pnpm build                 PASS (Next.js production build)

pnpm --filter @aegis/web exec vitest run features/cinematic-graph ../../tests/unit/cinematic ../../tests/performance/cinematic
  PASS 15 tests

NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web exec playwright test cinematic-graph
  PASS 5 tests

NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web dev --port 3000
SCREENSHOT_BASE_URL=http://127.0.0.1:3000 pnpm --filter @aegis/web exec node scripts/capture-cinematic-renderer-demo.mjs
  PASS (12 PNGs + webm)
```

Stack start for visual verification:

```bash
NEXT_PUBLIC_AEGIS_DATA_SOURCE=fixture pnpm --filter @aegis/web dev --port 3000
# Open http://127.0.0.1:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
# Toggle 3D; replay at /replay/run_01ARZ3NDEKTSV4RRFFQ69G5FAV
```

## Architecture decisions and ADRs

- Created [`docs/AEGIS-v1.0-Agent-Specs/adrs/0028-threejs-semantic-renderer.md`](../AEGIS-v1.0-Agent-Specs/adrs/0028-threejs-semantic-renderer.md).
- No other ADRs superseded. Architecture rule 6 preserved (Sigma primary; Three.js derived).

## Known limitations

- Headless Chromium WebGL quality varies; scene uses medium tier in this environment.
- jsdom cannot fully probe WebGL; unit tests force unavailable WebGL / use `recommendQualityTier` for reduced-motion AC.
- Invalid graph export fails via `SemanticSceneAdapterError`; UI surfaces structured error + return-to-2D (unit-covered; visual demo emphasizes fallback/2D availability).
- Directed cinematic camera sequences intentionally deferred to Phase 28.

## Deferred work

- Phase 28 cinematic incident replay / directed cameras
- Phase 29 scoring and after-action experience
- Production auth

## Risks for dependent phases

Phase 28 must:

- Consume the same `GraphStore` / replay cursor; no second reconstruction path
- Not invent domain facts for drama
- Keep Sigma as default analysis unless an approved ADR changes architecture
- Reuse `SemanticSceneAdapter` / selection bridge and dispose lifecycle

## Acceptance criteria evidence

| Criterion                                     | Evidence                                                                                                                                                                  |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC1 same semantic state at same cursor        | Acceptance test compares filtered GraphStore ids to scene projection; live/replay screenshots show sequence 500 / revision 12 / 12 nodes / 11 edges; e2e selection bridge |
| AC2 unsupported devices fall back             | `probeCapabilityReport({ forceWebglUnavailable: true })` → `fallback2d`; `CapabilityFallbackNotice` UI                                                                    |
| AC3 mode switch preserves selection; no leaks | e2e 2D→3D→2D inspector still shows API Gateway; dispose clears last projection; perf dispose cycles                                                                       |
| AC4 reduced motion understandable             | Screenshot `27-reduced-motion-or-fallback.png` shows reduced-motion alert; recommendQualityTier medium; inspector/list remain                                             |

## Prohibited-shortcut confirmation

- No mocks on production render path; fixture data uses approved shell/replay fixtures
- No competing graph/risk/replay model
- No Phase 28/29 scope absorbed
- No npm/Yarn/Bun package management
- Validation commands were executed in this tree and recorded above
- `@aegis/graph-domain` does not depend on Three.js
