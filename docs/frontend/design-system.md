# AEGIS Command-Centre Design System

> Phase 03 baseline — tokens, primitives, composed components, motion policy, and composition rules.

## Ownership

| Area                                          | Package / path                                                                                                                   |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Design tokens (CSS variables + typed exports) | [`packages/ui/src/tokens/`](../packages/ui/src/tokens/)                                                                          |
| Global styles for the web app                 | [`apps/web/src/app/globals.css`](../apps/web/src/app/globals.css)                                                                |
| UI primitives and composed components         | [`packages/ui/src/`](../packages/ui/src/)                                                                                        |
| Storybook catalogue                           | [`apps/web/.storybook/`](../apps/web/.storybook/), [`apps/web/components/design-system/`](../apps/web/components/design-system/) |
| Live showcase route                           | [`apps/web/src/app/design-system/`](../apps/web/src/app/design-system/)                                                          |

Import UI from `@aegis/ui`. Do not create parallel styling systems in feature code.

## Design tokens

### Surfaces

| Token              | CSS variable               | Usage                    |
| ------------------ | -------------------------- | ------------------------ |
| `surface-base`     | `--aegis-surface-base`     | App background           |
| `surface-elevated` | `--aegis-surface-elevated` | Cards, secondary panels  |
| `surface-panel`    | `--aegis-surface-panel`    | Primary workspace panels |
| `surface-rail`     | `--aegis-surface-rail`     | Operations rail          |
| `surface-overlay`  | `--aegis-surface-overlay`  | Tooltips, overlays       |

### Typography

| Token                                            | Usage                       |
| ------------------------------------------------ | --------------------------- |
| `--aegis-font-sans`                              | UI copy                     |
| `--aegis-font-mono`                              | IDs, logs, technical values |
| `text-primary` / `text-secondary` / `text-muted` | Semantic text colors        |

### Spacing

4px grid via `--aegis-space-1` … `--aegis-space-16`.

### Borders and depth

| Category | Tokens                                                                     |
| -------- | -------------------------------------------------------------------------- |
| Borders  | `--aegis-border-default`, `--aegis-border-subtle`, `--aegis-border-strong` |
| Radius   | `--aegis-radius-sm` … `--aegis-radius-xl`                                  |
| Shadows  | `--aegis-shadow-panel`, `--aegis-shadow-dialog`, `--aegis-shadow-rail`     |

### Focus

`--aegis-focus-ring` and `--aegis-focus-width` must remain visible on all interactive controls. Never remove focus outlines.

### Risk bands

| Band     | Token classes   |
| -------- | --------------- |
| Low      | `risk-low`      |
| Medium   | `risk-medium`   |
| High     | `risk-high`     |
| Critical | `risk-critical` |

### Status (maps to Phase 01 `NodeStatus`)

| `NodeStatus`          | Label               | Non-color indicator       |
| --------------------- | ------------------- | ------------------------- |
| `normal`              | Normal              | check + circle            |
| `suspicious`          | Suspicious          | alert-triangle + triangle |
| `under_investigation` | Under investigation | search + diamond          |
| `contained`           | Contained           | shield + hexagon          |
| `compromised`         | Compromised         | x-octagon + square        |

Operational UI states (`loading`, `error`, `disconnected`, `empty`) use distinct icons and `aria-label` text.

### Density

| Mode          | Usage                                 |
| ------------- | ------------------------------------- |
| `compact`     | Constrained layouts (`md` breakpoint) |
| `comfortable` | Default laptop layout                 |
| `spacious`    | Large desktop (`xl` breakpoint)       |

## Motion and reduced motion

| Duration | Variable                          | Default |
| -------- | --------------------------------- | ------- |
| Instant  | `--aegis-motion-duration-instant` | 0ms     |
| Fast     | `--aegis-motion-duration-fast`    | 120ms   |
| Normal   | `--aegis-motion-duration-normal`  | 200ms   |
| Slow     | `--aegis-motion-duration-slow`    | 320ms   |

`prefers-reduced-motion: reduce` sets animation/transition durations to 0ms. Essential status text and icons remain visible; pulse animations are disabled.

Use `useReducedMotion()` from `@aegis/ui` when JavaScript-driven animation is required.

## Component contracts

### Primitives

| Component           | Key props / behavior                                             |
| ------------------- | ---------------------------------------------------------------- |
| `Button`            | `variant`, `size`, keyboard activatable, visible focus           |
| `Badge`             | `nodeStatus`, `operationalStatus`, icon + label (not color-only) |
| `Alert`             | `variant`, `title`, `role="alert"`                               |
| `Dialog` / `Drawer` | Radix focus trap, Escape to close                                |
| `DropdownMenu`      | Keyboard navigation, destructive item styling                    |
| `Tooltip`           | Supplementary information only                                   |
| `Tabs`              | Arrow-key navigation via Radix                                   |
| `Skeleton`          | `animate` respects reduced motion                                |

### Composed

| Component                                                          | Purpose                                         |
| ------------------------------------------------------------------ | ----------------------------------------------- |
| `Panel`                                                            | Titled workspace section with density variants  |
| `Rail`                                                             | Collapsible operations navigation               |
| `Card`                                                             | Elevated content container                      |
| `DataTable`                                                        | Semantic table with keyboard-focusable rows     |
| `MetricTile`                                                       | KPI display with optional risk/status semantics |
| `TimelineMark`                                                     | Incident/event timeline entry                   |
| `LoadingState` / `EmptyState` / `ErrorState` / `DisconnectedState` | Standard shell states for Phase 04              |

## Responsive breakpoints

| Breakpoint | Min width | Behavior                                |
| ---------- | --------- | --------------------------------------- |
| `md`       | 1024px    | Stacked panels, compact density default |
| `lg`       | 1280px    | Collapsible rail                        |
| `xl`       | 1536px    | Full rail + side panels                 |

## Composition rules

1. Import primitives from `@aegis/ui`; use `cn()` for class composition.
2. Map domain status through `getNodeStatusPresentation()` — do not hard-code colors.
3. Use semantic HTML first; augment with Radix primitives where needed.
4. State-changing actions use `Button` variants (`destructive` is never the default focused action in dialogs).
5. Do not store authoritative domain state in component styling alone.

## Commands

```bash
pnpm --filter @aegis/ui test          # unit + a11y component tests
pnpm --filter @aegis/web storybook    # component catalogue (dev)
pnpm --filter @aegis/web build-storybook
pnpm --filter @aegis/web test:e2e     # Playwright design-system path
```

## Deferred to later phases

- Sigma.js graph controls (Phase 06)
