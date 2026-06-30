# ADR 0002: Shared Contract Versioning and Identifiers

## Status

Proposed — awaiting project-owner approval.

## Context

Phase 01 introduces canonical cross-language contracts consumed by API, services, web, graph, simulation, agents, and ML packages. `architecture.md` defines event, graph, and entity semantics but leaves implementation details for:

- Exact ID namespace validation rules
- JSON Schema generation source of truth
- Cross-language breaking-change detection
- Structured contract error codes

Phase 00 established `aegis-contracts` (Python) and `@aegis/contracts-ts` (TypeScript) for environment validation only.

## Decision

1. **Single source per language:** All domain contracts live in `packages/contracts-python` and `packages/contracts-ts`. Feature packages import; they do not redefine shapes.

2. **JSON Schema generation:** Pydantic models are canonical. JSON Schemas are generated via `scripts/generate_contract_schemas.py` into `tests/contract/fixtures/schemas/`.

3. **Wire format:** camelCase JSON; Python uses snake_case with Pydantic aliases. UTC timestamps require timezone awareness; serialized with `Z` suffix.

4. **Identifier validation:**
   - Authored IDs: `namespace:identifier` with an allowlisted namespace set and `[a-z0-9][a-z0-9._-]*` identifier body
   - Runtime IDs: `prefix_` + 26-character Crockford base32 (ULID-style)

5. **Compatibility manifest:** `tests/contract/fixtures/compatibility-manifest.json` stores SHA-256 hashes of fixtures and schemas. `scripts/check_contract_compatibility.py` fails CI on unapproved hash changes.

6. **Error catalog:** Contract boundaries raise `ContractValidationError` with codes `SCHEMA_VERSION_UNSUPPORTED`, `INVALID_IDENTIFIER`, `VALIDATION_FAILED`, and reserved codes for later phases.

7. **Schema versioning:** Integer `schemaVersion` per contract family. Additive optional fields within v1 are compatible; required-field or semantic changes require a version bump.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| TypeScript as schema source | Python owns API/simulation persistence; Pydantic aligns with FastAPI and SQLAlchemy boundaries |
| Hand-written JSON Schema | Drifts from code; Pydantic generation is reproducible |
| No hash manifest | Breaking changes would rely on manual review only |
| Permissive ID strings | Architecture requires explicit namespaces; labels must not be IDs |

## Consequences

- Contract changes require updating Python, TypeScript, fixtures, schemas, manifest, and tests together.
- `pnpm check-contracts` is mandatory in Phase 01+ validation.
- New ID namespaces require ADR or explicit versioning doc update.
- dependency-cruiser allows intra-package module splits in `contracts-ts`; cross-package imports must use package entry points.

## Security and reliability

- Durable models use `extra="forbid"` to reject unknown fields at boundaries.
- No secrets, provider types, or ORM types in contract packages.
- Invalid identifiers and schema versions fail closed with structured errors.

## Approval

- [ ] Project owner
