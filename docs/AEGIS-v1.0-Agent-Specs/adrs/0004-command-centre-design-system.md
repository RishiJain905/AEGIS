# ADR 0004: Command-Centre Design System

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 03 requires a shared command-centre design system: tokens, accessible primitives, semantic status presentation, motion policy, Storybook catalogue, and tests. The repository had only a Phase 00 `@aegis/ui` scaffold.

Architecture mandates Tailwind CSS, Radix-style accessible primitives, and a shared UI package. Phase 04 will add TanStack Query and Zustand; those must not be introduced early in the design-system phase.

## Decision

1. **Token ownership:** CSS custom properties live in `packages/ui/src/styles/tokens.css` and `motion.css`, with typed TS exports in `packages/ui/src/tokens/`.
2. **Component ownership:** All reusable primitives and composed command-centre components live in `@aegis/ui`. App-specific Storybook stories and the `/design-system` showcase live in `apps/web`.
3. **Tailwind integration:** Tailwind CSS v4 scans `packages/ui` and `apps/web` from `apps/web/src/app/globals.css` using `@source` directives. A Tailwind preset is exported from `packages/ui/tailwind.preset.ts`.
4. **Radix baseline:** Interactive overlays (dialog, drawer, menu, tooltip, tabs) use `@radix-ui/*` primitives with AEGIS token styling.
5. **Semantic status:** Presentation maps Phase 01 `NodeStatus` from `@aegis/contracts-ts` via `getNodeStatusPresentation()`. Icons and shapes ensure status is never color-only.
6. **Motion policy:** CSS variables for durations/easings; `prefers-reduced-motion` zeroes transitions; `useReducedMotion()` hook for JS-driven behavior.
7. **Phase 04 deferral:** TanStack Query and Zustand are explicitly out of Phase 03 scope.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| App-local shadcn without `@aegis/ui` package | Violates architecture package boundaries and Phase 03 contract ownership |
| Inline styles per screen | Prevents consistent tokens and blocks later-phase assembly |
| TanStack Query in Phase 03 for demo data | Out of scope; would commit Phase 04 shell semantics early |
| Tailwind v3 | Tailwind v4 aligns with current toolchain and CSS-first token workflow |

## Consequences

- `apps/web` depends on `@aegis/ui` and must import globals.css in the root layout.
- Later phases import `@aegis/ui` rather than duplicating primitives.
- Storybook builds from `apps/web` with PostCSS Tailwind processing.
- Presentation types remain UI-local; durable domain contracts stay in `@aegis/contracts-ts`.

## Security and reliability

- No architecture non-negotiable rules are changed.
- No offensive capability, unrestricted agent execution, or production remediation is introduced.
- Accessibility and reduced-motion requirements are enforced in components and tests.

## Approval

- [ ] Project owner
