# Phase 03 Handoff — Command-Centre Design System

## Status

`READY FOR VALIDATION`

## Implemented

Phase 03 deliverables per `docs/AEGIS-v1.0-Agent-Specs/product-shell/03-command-centre-design-system.md`:

- Design tokens for surfaces, typography, spacing, borders, depth, focus, risk, status, and density (`packages/ui/src/tokens/`, `packages/ui/src/styles/tokens.css`)
- Motion durations/easings and global reduced-motion rules (`packages/ui/src/styles/motion.css`, `useReducedMotion`)
- Accessible Radix-based primitives: Button, Badge, Alert, Skeleton, Separator, Dialog, Drawer, DropdownMenu, Tooltip, Tabs
- Composed components: Panel, Rail, Card, DataTable, MetricTile, TimelineMark, LoadingState, EmptyState, ErrorState, DisconnectedState
- Semantic status/risk presentation mapping Phase 01 `NodeStatus` with icons and shapes (non-color-only)
- Storybook catalogue with primitive and composed stories (`apps/web/.storybook/`, `apps/web/components/design-system/*.stories.tsx`)
- Responsive density/breakpoint tokens (`md` 1024px, `lg` 1280px, `xl` 1536px)
- Live showcase route at `/design-system`
- Documentation: `docs/frontend/design-system.md`
- ADR 0004: command-centre design system package and token ownership

## Files added

| Area       | Key paths                                                                                                                                                                                       |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI package | `packages/ui/src/tokens/`, `styles/`, `lib/`, `semantic/`, `motion/`, `primitives/`, `composed/`, `tailwind.preset.ts`                                                                          |
| Web app    | `apps/web/src/app/globals.css`, `apps/web/src/app/design-system/`, `apps/web/components/design-system/`, `apps/web/.storybook/`, `apps/web/postcss.config.mjs`, `apps/web/playwright.config.ts` |
| Tests      | `packages/ui/tests/**`, `tests/a11y/design-system.test.tsx`, `tests/e2e/design-system.spec.ts`                                                                                                  |
| Docs       | `docs/frontend/design-system.md`, `docs/AEGIS-v1.0-Agent-Specs/adrs/0004-command-centre-design-system.md`                                                                                       |

## Files modified

| File                                                                                                     | Reason                                                             |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `packages/ui/package.json`, `src/index.ts`, `README.md`, `tsconfig.json`, `vitest.config.ts`             | Expand `@aegis/ui` to full design system                           |
| `apps/web/package.json`, `layout.tsx`, `page.tsx`, `next.config.ts`, `tsconfig.json`, `vitest.config.ts` | Tailwind, Storybook, Playwright, globals                           |
| `packages/contracts-ts/src/versioning.ts`, `packages/contracts-python/src/aegis_contracts/versioning.py` | Bump `WORKSPACE_VERSION` to `0.0.0-phase03`                        |
| `package.json`                                                                                           | Add `test:e2e`, `test:storybook`, format paths for `docs/frontend` |
| `pnpm-workspace.yaml`                                                                                    | Allow `@tailwindcss/oxide` builds                                  |
| `eslint.config.mjs`                                                                                      | Ignore Storybook/postcss config paths                              |
| `.gitignore`                                                                                             | Ignore `storybook-static/`, Playwright artifacts                   |

## Files removed

None.

## Contracts introduced or changed

| Contract                   | Version         | Description                                                                        |
| -------------------------- | --------------- | ---------------------------------------------------------------------------------- |
| `WORKSPACE_VERSION`        | `0.0.0-phase03` | Workspace metadata constant                                                        |
| UI presentation types      | v1 (UI-local)   | `StatusPresentation`, `RiskPresentation`, component prop interfaces in `@aegis/ui` |
| Design token CSS variables | v1              | `--aegis-*` variables in `tokens.css` / `motion.css`                               |
| Tailwind preset            | v1              | `packages/ui/tailwind.preset.ts`                                                   |

No durable cross-language domain contracts were changed. Phase 01 `NodeStatus` is imported, not redefined.

## Database migrations

None.

## Environment and configuration changes

- `pnpm-workspace.yaml`: `allowBuilds['@tailwindcss/oxide'] = true`
- New dev dependencies in `@aegis/ui` and `@aegis/web` (Radix, Tailwind, Storybook, Playwright, Testing Library, vitest-axe)

## Generated artifacts and fixtures

- `apps/web/storybook-static/` (gitignored; regenerate: `pnpm --filter @aegis/web build-storybook`)
- Updated `pnpm-lock.yaml`

## Tests added

| Test                                               | Proves                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| `packages/ui/tests/tokens.test.ts`                 | Token completeness for surfaces, risk, status, motion              |
| `packages/ui/tests/semantic-status.test.ts`        | Every `NodeStatus` has label, icon, shape, aria label              |
| `packages/ui/tests/motion.test.ts`                 | `useReducedMotion` respects preference changes                     |
| `packages/ui/tests/components/primitives.test.tsx` | Keyboard activation, dialog focus trap, badge a11y labels          |
| `packages/ui/tests/a11y/design-system.test.tsx`    | axe violations = 0; loading state preserves text                   |
| `tests/a11y/design-system.test.tsx`                | Handoff traceability copy of a11y suite                            |
| `tests/e2e/design-system.spec.ts`                  | Playwright path through `/design-system` with keyboard dialog/menu |

## Commands executed and results

| Command                                    | Result                                           |
| ------------------------------------------ | ------------------------------------------------ |
| `pnpm format:check`                        | PASS                                             |
| `pnpm lint`                                | PASS (ESLint + dependency-cruiser: 0 violations) |
| `pnpm typecheck`                           | PASS                                             |
| `pnpm test`                                | PASS (81 tests: 60 contracts + 20 ui + 1 web)    |
| `pnpm build`                               | PASS (Next.js production build)                  |
| `pnpm --filter @aegis/web test:e2e`        | PASS (3 Playwright tests)                        |
| `pnpm --filter @aegis/web build-storybook` | PASS                                             |

## Architecture decisions and ADRs

- **ADR 0004** (`docs/AEGIS-v1.0-Agent-Specs/adrs/0004-command-centre-design-system.md`): token ownership in `@aegis/ui`, Tailwind v4 integration, Radix primitive baseline, motion policy, Phase 04 deferral for TanStack Query/Zustand.
- No changes to `architecture.md` non-negotiable rules.

## Known limitations

- Playwright webServer uses `next start` with standalone output warning (works for e2e; Docker production uses standalone server separately).
- Storybook build emits benign `"use client"` bundling warnings for Radix modules.
- `tests/a11y/design-system.test.tsx` at repo root is a traceability copy; executable suite runs via `@aegis/ui` vitest.
- Dialog test warns when `Description` is omitted (showcase dialogs include descriptions).

## Deferred work

- TanStack Query / Zustand (Phase 04)
- Application shell routes and panel docking (Phase 04)
- Sigma.js graph controls (Phase 06)
- CI job for Playwright e2e (not added; tests run locally and documented)

## Risks for dependent phases

- Phase 04 must import `@aegis/ui` primitives; do not create parallel component libraries.
- Global styles must continue importing `@aegis/ui` token CSS before Tailwind.
- Feature screens should use `getNodeStatusPresentation()` for status styling.

## Acceptance criteria evidence

1. **Keyboard + automated a11y tests** — `packages/ui/tests/components/primitives.test.tsx` (Enter/Escape), `packages/ui/tests/a11y/design-system.test.tsx` (axe), `tests/e2e/design-system.spec.ts` (keyboard dialog/menu).
2. **Reduced motion preserves information** — `motion.css` zeroes durations under `prefers-reduced-motion`; `useReducedMotion` tested in `motion.test.ts`; `LoadingState` test verifies text remains visible.
3. **Later screens assemble without new primitives** — `/design-system` showcase composes Panel, Rail, Badge, DataTable, MetricTile, TimelineMark, state shells; `docs/frontend/design-system.md` composition rules.
4. **Tokens and contracts documented and typed** — `docs/frontend/design-system.md`, typed exports in `packages/ui/src/tokens/` and component prop interfaces in `packages/ui/src/index.ts`.

## Prohibited-shortcut confirmation

- No scaffolding-only or TODO-only implementations for in-scope components.
- No duplicate domain types; `NodeStatus` imported from `@aegis/contracts-ts`.
- No TanStack Query, Zustand, graph renderer, or Phase 04+ features implemented.
- All listed validation commands were executed in the current tree with results recorded above.
- No tests were deleted or weakened.
