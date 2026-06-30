# Accessibility tests

Phase 03 automated accessibility suites live in this directory.

The canonical executable suite is mirrored at:

- [`packages/ui/tests/a11y/design-system.test.tsx`](../packages/ui/tests/a11y/design-system.test.tsx)

Run via:

```bash
pnpm --filter @aegis/ui test
```

The root-level file [`design-system.test.tsx`](./design-system.test.tsx) documents the same acceptance coverage for handoff traceability.
