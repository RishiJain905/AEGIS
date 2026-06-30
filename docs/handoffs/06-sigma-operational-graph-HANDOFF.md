# Phase 06 Handoff — Sigma.js Operational Graph

## Status

`READY FOR VALIDATION`

## Implemented

Phase 06 deliverables per `docs/AEGIS-v1.0-Agent-Specs/graph-platform/06-sigma-operational-graph.md`:

- Sigma.js operational graph mounted in command-centre `VisualizationSlot` (dynamic import, SSR disabled)
- `OperationalGraphAdapter` projecting `@aegis/graph-domain` `GraphStore` to presentation Graphology + Sigma.js
- Pan, zoom, fit, focus, hover, selection, keyboard-accessible entity list
- Search, layer/filter controls, legend, camera controls, overlay toggles (risk/status/evidence/incident)
- Neighborhood isolation, path tracing, incident context inspector integration
- Semantic styling from canonical node/edge fields via `@aegis/ui` risk/status tokens
- Stable deterministic initial layout with position cache (ref-based, no layout worker)
- Renderer lifecycle with `dispose()` on unmount
- Enriched shell fixture (12 nodes, 11 edges, 3 clusters)
- ADR 0007, feature documentation, unit and E2E tests

## Files added

| Area | Key paths |
| --- | --- |
| Operational graph | `apps/web/features/operational-graph/**` |
| Inspector | `apps/web/features/inspector/**` |
| Graph controls | `packages/ui/src/graph-controls/index.tsx` |
| E2E | `tests/e2e/operational-graph.spec.ts` |
| Screenshots | `apps/web/scripts/capture-operational-graph-screenshots.mjs` |
| Docs | `docs/frontend/operational-graph.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0007-sigma-operational-graph.md` |

## Files modified

| File | Reason |
| --- | --- |
| `apps/web/features/shell/components/visualization-slot.tsx` | Mount Sigma operational graph; remove harness from production path |
| `apps/web/features/shell/components/inspector-panel.tsx` | Graph entity and incident context sections |
| `apps/web/stores/workspace-ui-store.ts` | Reset graph visual state on run change |
| `apps/web/fixtures/shell-dataset.json` | Connected multi-node graph for demos/E2E |
| `apps/web/package.json` | Add sigma, graphology dependencies |
| `packages/ui/src/index.ts` | Export graph controls |
| `packages/contracts-ts/src/versioning.ts` | `WORKSPACE_VERSION` → `0.0.0-phase06` |
| `packages/contracts-python/src/aegis_contracts/versioning.py` | Parity bump |
| `packages/graph-domain/src/aegis_graph_domain/__init__.py` | Stub parity bump |
| `apps/web/vitest.config.ts` | JSX automatic for component tests |
| `tests/e2e/graph-domain-harness.spec.ts` | Assert Sigma canvas instead of placeholder |
| `pnpm-lock.yaml` | New dependencies |

## Files removed

None (Phase 05 harness component retained in repo but not mounted in production visualization slot).

## Contracts introduced or changed

| Contract | Version | Description |
| --- | --- | --- |
| `OperationalGraphAdapter` | v1 (web-local) | Sigma renderer adapter interface |
| `GraphVisualState` | v1 (web-local) | Ephemeral filter, selection, highlight, overlay, camera state |
| `GraphSelection` | v1 (web-local) | Primary/secondary node and edge selection |
| `GraphCameraBookmark` | v1 (web-local) | Camera position bookmark |
| Semantic style mapping | v1 (web-local) | Canonical field → visual token mapping |
| `WORKSPACE_VERSION` | `0.0.0-phase06` | Workspace metadata |

Phase 01 wire contracts unchanged. `GraphFilterSet` reused from `@aegis/graph-domain`.

## Database migrations

None.

## Environment and configuration changes

None.

## Generated artifacts and fixtures

- Enriched `apps/web/fixtures/shell-dataset.json` graph snapshot (12 nodes, 11 edges, 3 clusters)
- Screenshot artifacts under `/opt/cursor/artifacts/screenshots/06-*.png`

## Tests added

| Test | Proves |
| --- | --- |
| `features/operational-graph/contracts/contracts.test.ts` | Schema validation |
| `features/operational-graph/layout/initial-layout.test.ts` | Deterministic layout |
| `features/operational-graph/semantic/graph-semantic-styles.test.ts` | Style from canonical fields |
| `features/operational-graph/adapters/sigma-operational-graph-adapter.test.ts` | Store projection, dispose |
| `features/operational-graph/components/sigma-canvas.test.tsx` | Mount/unmount lifecycle |
| `stores/workspace-ui-store.test.ts` | Graph visual reset on run change |
| `tests/e2e/operational-graph.spec.ts` | Search, select, isolate, path, overlay, responsive, reduced motion |
| `tests/e2e/graph-domain-harness.spec.ts` | Sigma canvas replaces placeholder |

## Commands executed and results

| Command | Result |
| --- | --- |
| `pnpm format:check` | PASS |
| `pnpm lint` | PASS (ESLint + dependency-cruiser: 0 violations) |
| `pnpm typecheck` | PASS |
| `pnpm test` | PASS (144 tests: 60 contracts + 31 graph-domain + 20 ui + 33 web) |
| `pnpm build` | PASS |
| `pnpm check-contracts` | PASS |
| `CI=1 pnpm --filter @aegis/web test:e2e` | PASS (21 Playwright tests) |

Visual evidence commands:

```bash
pnpm --filter @aegis/web build
pnpm --filter @aegis/web start
# http://localhost:3000/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV

SCREENSHOT_BASE_URL=http://127.0.0.1:3000 node apps/web/scripts/capture-operational-graph-screenshots.mjs
```

## Architecture decisions and ADRs

- **ADR 0007** (`docs/AEGIS-v1.0-Agent-Specs/adrs/0007-sigma-operational-graph.md`): Sigma/renderer vs GraphStore boundary, presentation Graphology in web adapter only, web-local interaction contracts, SSR-disabled dynamic mount, Phase 07 layout deferral.
- No changes to `architecture.md` non-negotiable rules.

## Known limitations

- Initial layout is deterministic circular/cluster placement, not ForceAtlas2 (Phase 07).
- Edge rendering uses Sigma `line` type only; custom dashed/arrow edge programs deferred.
- Live WebSocket delta streaming not wired (Phases 11–13).
- Medium-graph (2500 node) performance budgets validated in graph-domain only, not Sigma renderer.
- Playwright e2e requires fresh webServer (`CI=1` or no stale process on port 3000).

## Deferred work

- ForceAtlas2 worker layout and large-graph performance (Phase 07)
- Backend `GET /api/v1/runs/{id}/graph` route
- Three.js cinematic view (Phase 27)
- Custom Sigma edge programs for dashed/inferred edges

## Risks for dependent phases

- Phase 07 must extend adapter/layout without duplicating domain algorithms or moving GraphStore into React.
- Realtime phases must call `GraphStore.applyDelta()` then adapter sync; preserve gap detection semantics.
- Do not export domain Graphology types; presentation Graphology stays in `apps/web` adapter.
- Preserve `GraphVisualState` contract fields or version-bump with migration notes.

## Acceptance criteria evidence

| Criterion | Evidence |
| --- | --- |
| User can search, isolate, trace, inspect, and restore full graph | E2E `operational-graph.spec.ts`; screenshots `06-search-filter.png`, `06-neighborhood-isolation.png`, `06-path-highlight.png`, `06-selected-node-inspector.png` |
| Visual state derives only from semantic contracts | `graph-semantic-styles.test.ts`; adapter reads `GraphStore.exportSnapshot()` only |
| Keyboard/reduced-motion alternatives remain useful | E2E entity list + reduced motion test; accessible list in `OperationalGraphView` |
| Unmounting cleans renderer resources | `sigma-canvas.test.tsx`, `sigma-operational-graph-adapter.test.ts` dispose |

## Prohibited-shortcut confirmation

- No scaffolding-only renderer; production-path Sigma integration with full interaction surface.
- No duplicate Phase 01 graph wire contracts.
- No graph algorithms in React components or Sigma adapter beyond projection.
- No Phase 07 worker layout or Three.js implemented.
- All listed validation commands executed with results recorded above.
- No tests deleted or weakened.
