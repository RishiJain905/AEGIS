# AEGIS Shared Contract Versioning

The v1.0.0 release identifier is `1.0.0` in the root/workspace package metadata and
the canonical Python and TypeScript `WORKSPACE_VERSION` constants. Integer schema
versions and the `ProtocolVersion` remain independent compatibility identifiers; a
release-version bump does not by itself change a wire schema.

> Phase 01 baseline — canonical cross-language contracts for AEGIS v1.0.

## Ownership

All durable domain contracts live in exactly two packages:

| Package               | Language          | Path                                                          |
| --------------------- | ----------------- | ------------------------------------------------------------- |
| `aegis-contracts`     | Python (Pydantic) | [`packages/contracts-python/`](../packages/contracts-python/) |
| `@aegis/contracts-ts` | TypeScript (Zod)  | [`packages/contracts-ts/`](../packages/contracts-ts/)         |

Do not redefine event envelopes, graph payloads, entity base records, or API error shapes in apps, services, or feature packages.

## Schema versions

Every durable contract includes an integer `schemaVersion` field (JSON wire name). Version `1` is the Phase 01 baseline for:

- Domain event envelope
- Graph node, edge, snapshot, delta, path query/result
- API error envelope, cursor pagination, idempotency metadata
- Base records: scenario, scenario version, run, alert, incident, evidence, hypothesis, agent session, action proposal, approval, executed action, model manifest, model score

HTTP protocol versioning uses `ProtocolVersion` (`major.minor`) separate from per-payload `schemaVersion`.

## Wire format

- **JSON (HTTP, fixtures, streams):** camelCase field names per [`docs/architecture.md`](../architecture.md)
- **Python models:** snake_case attributes with Pydantic aliases for JSON
- **Timestamps:** UTC ISO-8601 with `Z` suffix; timezone-naive values are rejected
- **Simulation time:** distinct `simTime` field; never substitute wall-clock time for ordering

## Identifier rules

### Authored IDs (`namespace:identifier`)

Stable scenario/platform identifiers. Allowed namespaces:

`asset`, `incident`, `alert`, `evidence`, `agent-session`, `business-unit`, `edge`, `scenario`, `scenario-version`, `relationship`, `service`, `user`, `device`, `identity`, `database`, `control`

Pattern: `namespace` + `:` + identifier starting with `[a-z0-9]`, up to 127 characters total.

Examples:

- `asset:svc-api-gateway`
- `incident:inc_synthetic_001`
- `scenario-version:v1.0.0-synthetic`

### Runtime IDs (`prefix_ULID`)

Generated at execution time. Prefixes: `evt`, `run`, `trc`, `prp`, `apr`, `act`, `mdl`, `hyp`, etc.

Pattern: `prefix_` + 26-character Crockford base32 string.

Examples:

- `evt_01ARZ3NDEKTSV4RRFFQ69G5FAW`
- `run_01ARZ3NDEKTSV4RRFFQ69G5FAV`

Display labels are never used as identity.

## Compatibility policy

| Change type                           | Action                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Add optional field, same semantics    | Same `schemaVersion`; update golden fixtures + manifest                                           |
| New required field or semantic change | Bump `schemaVersion`; add migration notes; update Python, TypeScript, fixtures, schemas, manifest |
| Remove or rename field                | Breaking — bump version or ADR                                                                    |
| Fixture content change                | Update `compatibility-manifest.json` hashes; bump `schemaVersion` if breaking                     |

Breaking changes are detected by `pnpm check-contracts`, which verifies:

1. SHA-256 hashes in [`tests/contract/fixtures/compatibility-manifest.json`](../tests/contract/fixtures/compatibility-manifest.json)
2. Python parsing of all valid golden fixtures
3. TypeScript parsing via Vitest cross-language tests

## Error codes

Contract boundary failures use `ContractValidationError` / `ContractValidationError` (TS) with stable codes:

| Code                         | Meaning                                                     |
| ---------------------------- | ----------------------------------------------------------- |
| `SCHEMA_VERSION_UNSUPPORTED` | Unknown or retired `schemaVersion`                          |
| `INVALID_IDENTIFIER`         | ID failed namespace/prefix validation                       |
| `VALIDATION_FAILED`          | General schema validation failure                           |
| `STALE_REVISION`             | Optimistic concurrency conflict (reserved for later phases) |
| `DUPLICATE_EVENT`            | Idempotent replay detected duplicate (reserved)             |

API HTTP errors use `ApiErrorEnvelopeV1`: `code`, `message`, `details`, `traceId`.

## Regenerating artifacts

```bash
# JSON Schemas from Pydantic (canonical)
uv run python scripts/generate_contract_schemas.py

# After intentional fixture changes, regenerate manifest hashes:
python3 -c "..."  # see scripts/check_contract_compatibility.py header

# Full compatibility gate
pnpm check-contracts
```

## Golden fixtures

Valid fixtures: [`tests/contract/fixtures/valid/`](../tests/contract/fixtures/valid/)

Invalid fixtures (failure-path tests): [`tests/contract/fixtures/invalid/`](../tests/contract/fixtures/invalid/)

Fixtures use synthetic IDs only — no Operation Silent Relay scenario content in platform code.

## Consumers

- **Phase 02+:** ORM models store validated JSONB; repositories return `aegis_contracts` types
- **Phase 04+ web:** import `@aegis/contracts-ts` only
- **Phase 05 graph-domain:** consume `GraphSnapshotV1` / `GraphDeltaV1` without redefining shapes
