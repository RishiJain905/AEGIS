# contracts-ts

TypeScript workspace contracts for AEGIS v1.0.

## Ownership

Phase 00: environment validation schemas and workspace metadata only.
Phase 01+: shared domain contracts (events, graph, API types).

## Allowed dependencies

- `zod` and other validation libraries approved for this package.
- Must not depend on `apps/*`, `services/*`, or framework-specific UI packages.

## Consumers

- `apps/web`
- Future TypeScript packages and tests
