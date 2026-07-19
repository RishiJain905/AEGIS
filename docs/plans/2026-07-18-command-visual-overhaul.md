# AEGIS Command Visual Overhaul Implementation Plan

> **For Codex:** Execute this plan in the current checkout with `superpowers:test-driven-development`, `superpowers:systematic-debugging`, and `superpowers:verification-before-completion`. Do not branch or commit.

**Goal:** Make the semantic 3D scene visibly cinematic, make Sigma a legible investigation graph, and elevate the shared shell into a production-quality SOC command centre.

**Architecture:** Keep `GraphStore` and all existing contracts authoritative. Add pure presentation helpers for camera framing and Three color/opacity resolution, enrich the existing Three and Sigma adapters, then improve shared tokens/primitives so route-level UIs inherit a coherent system.

**Tech Stack:** Next.js 15, React 19, React Three Fiber/Three.js, Sigma.js 3, Graphology, Tailwind CSS 4, Vitest, Testing Library, vitest-axe.

---

### Task 1: Prove and fix semantic-scene framing

**Files:**

- Create: `apps/web/features/cinematic-graph/lib/camera-framing.ts`
- Create: `apps/web/features/cinematic-graph/lib/camera-framing.test.ts`
- Modify: `apps/web/features/cinematic-graph/adapters/semantic-scene-adapter.ts`
- Modify: `apps/web/features/cinematic-graph/adapters/semantic-scene-adapter.test.ts`

1. Write a failing test using the 38-node fixture that asserts the default camera distance exceeds the projected bounding radius and targets the projected centre.
2. Run `corepack pnpm --filter @aegis/web exec vitest run features/cinematic-graph/lib/camera-framing.test.ts` and confirm the red result.
3. Implement a deterministic bounds-to-bookmark helper and automatic/manual camera mode inside the adapter without changing contract shapes.
4. Re-run the focused camera and adapter tests until green.

### Task 2: Remove Three color warnings and add tier-aware scene depth

**Files:**

- Create: `apps/web/features/cinematic-graph/lib/three-color.ts`
- Create: `apps/web/features/cinematic-graph/lib/three-color.test.ts`
- Modify: `apps/web/features/cinematic-graph/components/cinematic-scene-canvas.tsx`
- Modify: `apps/web/features/cinematic-graph/components/cinematic-graph-view.tsx`

1. Write failing tests asserting `rgba()` and alpha-hex inputs resolve to an opaque cached `THREE.Color` plus numeric opacity without logging a Three warning.
2. Run the focused test and confirm it fails for the missing resolver.
3. Implement cached parsing, then build tier-gated geometry/materials, fog, glow shells, depth grid, purposeful lighting, and camera easing.
4. Ensure low tier and reduced motion use static demand rendering with no easing or decorative animation.
5. Run cinematic graph tests and typecheck.

### Task 3: Build a legible Sigma visual language

**Files:**

- Modify: `apps/web/features/operational-graph/semantic/graph-semantic-styles.ts`
- Modify: `apps/web/features/operational-graph/semantic/graph-semantic-styles.test.ts`
- Modify: `apps/web/features/operational-graph/layout/initial-layout.ts`
- Modify: `apps/web/features/operational-graph/layout/initial-layout.test.ts`
- Modify: `apps/web/features/operational-graph/adapters/sigma-operational-graph-adapter.ts`
- Modify: `apps/web/features/operational-graph/adapters/sigma-operational-graph-adapter.test.ts`
- Modify: `apps/web/features/operational-graph/components/operational-graph-view.tsx`

1. Add failing tests for opaque edge colors plus separate opacity, wider multi-cluster spread, risk emphasis, semantic node type attributes, and priority labels.
2. Confirm focused red results.
3. Implement distinct type palette/size treatment, risk and status emphasis supported by Sigma, clear hover/selection reducers, readable label colors/density, and fit-to-view after stable layout.
4. Refine the toolbar and legend so every promised encoding is visible and described.
5. Run all operational graph tests.

### Task 4: Establish the SOC surface/type/elevation system

**Files:**

- Modify: `packages/ui/src/styles/tokens.css`
- Modify: `packages/ui/src/styles/motion.css`
- Modify: `packages/ui/src/primitives/button.tsx`
- Modify: `packages/ui/src/primitives/badge.tsx`
- Modify: `packages/ui/src/primitives/alert.tsx`
- Modify: `packages/ui/src/composed/panel.tsx`
- Modify: `packages/ui/src/composed/card.tsx`
- Modify: `packages/ui/src/composed/metric-tile.tsx`
- Modify: `packages/ui/src/composed/data-table.tsx`
- Modify: `packages/ui/src/composed/timeline-mark.tsx`
- Modify: `packages/ui/src/composed/state-shells.tsx`
- Modify: `packages/ui/src/graph-controls/index.tsx`
- Modify: `apps/web/src/app/globals.css`

1. Add or extend component assertions for minimum hit-area classes, panel header/body hierarchy, and semantic status text.
2. Run UI component and axe tests to establish red/green behavior.
3. Introduce layered blue-black surfaces, restrained cyan focus, semantic green/amber/vermilion, tabular mono data, component elevation, explicit transitions, and reduced-motion overrides.
4. Re-run UI tests and `vitest-axe`.

### Task 5: Apply the system to the command shell

**Files:**

- Modify: `apps/web/features/shell/components/command-centre-shell.tsx`
- Modify: `apps/web/features/shell/components/status-strip.tsx`
- Modify: `apps/web/features/shell/components/visualization-slot.tsx`
- Modify: `apps/web/features/shell/components/inspector-panel.tsx`
- Modify: `apps/web/features/shell/components/timeline-area.tsx`
- Modify as needed: route-level panels under `apps/web/src/app` and `apps/web/features/*`

1. Add targeted accessibility assertions only where behavior changes.
2. Apply clear workspace hierarchy, telemetry grouping, intentional panel dimensions, inspector/list treatment, and refined timeline rail/markers.
3. Preserve keyboard operation, live-region behavior, and all data/query contracts.
4. Run scoped shell and web tests.

### Task 6: Visual and repository verification

1. Run scoped cinematic, operational graph, shell, UI, and axe tests.
2. Run web typecheck.
3. Rebuild/restart the web service only if the running container does not pick up the checkout.
4. Inspect 2D and 3D in a real browser, verify visible graph content, console warning count, selection/hover, and reduced-motion behavior.
5. Run `scripts\\verify.ps1` and read the complete output through the final `VERIFY: PASS` line.
6. Review `git diff --check`, `git diff --stat`, and `git status --short`; leave every change uncommitted.
