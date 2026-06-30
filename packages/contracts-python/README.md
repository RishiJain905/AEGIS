# contracts-python

Python workspace contracts for AEGIS v1.0.

## Ownership

Canonical Pydantic domain contracts shared across API, services, and workers.

| Module       | Contents                                                               |
| ------------ | ---------------------------------------------------------------------- |
| `primitives` | IDs, timestamps, sequence, revision, trace fields                      |
| `errors`     | `ContractValidationError`, `ApiErrorEnvelopeV1`                        |
| `events`     | `DomainEventEnvelopeV1`, `EventTypeRegistry`                           |
| `graph`      | Graph node/edge/snapshot/delta/path contracts                          |
| `entities`   | Scenario, run, incident, evidence, agent, proposal, model base records |
| `api`        | Pagination, idempotency, protocol version                              |
| `versioning` | Schema version constants and guards                                    |
| `settings`   | Environment validation (Phase 00)                                      |
| `fixtures`   | Fixture name → model map for cross-language tests                      |

## Allowed dependencies

Pydantic and pydantic-settings only. Must not import apps or services.

## Consumers

- `apps/api`
- `services/*`
- `packages/graph-domain`, `packages/scenario-sdk`, `packages/policy`, `packages/observability` (Phase 02+)

See [`docs/contracts/versioning.md`](../../docs/contracts/versioning.md) for compatibility policy.
