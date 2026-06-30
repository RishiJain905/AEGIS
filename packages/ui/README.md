# ui

Shared UI primitives and design-system components for the AEGIS command centre.

## Ownership

Phase 03+: design system tokens, primitives, composed components, semantic presentation, motion policy.

## Module map

```text
packages/ui/src/
├── tokens/           # Typed token exports
├── styles/           # tokens.css, motion.css
├── lib/cn.ts         # Class composition utility
├── semantic/         # NodeStatus/risk presentation + icons
├── motion/           # useReducedMotion hook
├── primitives/       # Button, Badge, Dialog, etc.
└── composed/         # Panel, Rail, Card, DataTable, state shells
```

## Allowed dependencies

- `@aegis/contracts-ts`
- React (peer)
- Radix UI primitives, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`

## Must not depend on

- `apps/*`, `services/*`, FastAPI, or domain service internals.

## Consumer usage

```tsx
import { Button, Badge, Panel } from '@aegis/ui';
import '@aegis/ui/styles/tokens.css';
```

See [`docs/frontend/design-system.md`](../../docs/frontend/design-system.md) for token tables and composition rules.
