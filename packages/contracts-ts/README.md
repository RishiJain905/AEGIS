# contracts-ts

TypeScript workspace contracts for AEGIS v1.0.

## Ownership

Canonical Zod domain contracts mirroring `aegis-contracts` Python semantics.

| Module          | Contents                                    |
| --------------- | ------------------------------------------- |
| `primitives.ts` | ID and timestamp validators                 |
| `errors.ts`     | `ContractValidationError`, API error schema |
| `events.ts`     | Domain event envelope and registry          |
| `graph.ts`      | Graph contracts                             |
| `entities.ts`   | Base entity schemas                         |
| `api.ts`        | Pagination and idempotency                  |
| `versioning.ts` | Schema version constants                    |
| `index.ts`      | Public exports + `FIXTURE_SCHEMA_MAP`       |

## Allowed dependencies

- `zod` only (runtime)
- Must not depend on `apps/*`, `services/*`, or UI frameworks

## Consumers

- `apps/web`
- `packages/ui`
- Cross-language contract tests

See [`docs/contracts/versioning.md`](../../docs/contracts/versioning.md) for compatibility policy.
