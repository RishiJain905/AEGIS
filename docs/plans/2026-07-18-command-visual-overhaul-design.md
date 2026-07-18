# AEGIS Command visual overhaul design

## Outcome

AEGIS Command will read as a dense, professional SOC workspace. Sigma remains the primary analysis renderer and Three.js remains a read-only semantic projection over the same `GraphStore`. Existing graph, capability, quality-tier, camera-bookmark, LOD, and visual-state contracts remain intact.

## Visual system

The palette uses blue-black layered surfaces, cool cyan for operator focus, green for healthy state, amber for elevated risk, and vermilion for critical state. Depth comes from tonal surface steps, inset highlights, restrained shadows, and sparse borders rather than glow-heavy RGB effects. Sans-serif type carries commands and explanation; IDs, timestamps, sequences, and changing metrics use tabular mono typography. A 4 px spacing rhythm remains the base, with 40 px minimum interactive targets.

## Three-dimensional presentation

The semantic adapter derives a camera bookmark from the actual projected bounds when it is in automatic framing mode. This fixes the current static camera, which sits inside an approximately 960 px-wide ring layout and looks at its empty centre. Node and edge data remain canonical; only their presentation is enriched.

The renderer resolves CSS colors once into cached opaque `THREE.Color` instances plus a separate opacity value. No `rgba()` or alpha-hex string is passed to `THREE.Color`. High and medium tiers use lit standard/physical materials, fog, depth cues, risk glow shells, and purposeful key/fill/rim lighting. Low tier uses reduced geometry, static demand rendering, and simpler materials. Reduced motion disables continuous rendering and camera easing while preserving risk/status meaning.

## Two-dimensional analysis

The Sigma adapter maps asset type to distinct hue, criticality to size, risk to an explicit halo/ring presentation, and interaction state to z-order, emphasis, and label priority. Labels are rendered only when selected, hovered, highlighted, sufficiently important, or allowed by the current LOD tier; renderer density and thresholds prevent the initial overlap. The deterministic initial layout uses wider cluster separation and non-concentric node placement, then fits after worker completion. Hover, selection, neighborhood, and path states are visually distinct and keyboard-equivalent entity-list controls remain available.

## Shell and component system

Shared tokens and primitives provide the main elevation system so route-level features improve without bespoke wrappers. Panels receive deliberate headers and separated bodies; cards, tables, badges, buttons, alerts, loading/empty/error states, inspector sections, and the timeline gain consistent hierarchy. The shell adds a subtle environmental backdrop, clearer status telemetry, and more intentional workspace proportions without changing data flow.

## Accessibility and security

Text and interactive-state combinations target WCAG AA contrast. Focus rings remain visible, controls retain semantic roles, interactive hit areas reach at least 40 px, dynamic status regions remain announced, and motion is fully suppressed under `prefers-reduced-motion`. No external assets, inline scripts, new CSP origins, or backend changes are introduced.

## Verification

Pure utilities receive red/green tests for camera framing, cached color/opacity resolution, semantic styles, and layout spread. Existing Sigma adapter/component and UI `vitest-axe` suites remain green. The live app is checked in both 2D and 3D, including console output and reduced-motion behavior, before the repository verification script is run to the required `VERIFY: PASS` line.
